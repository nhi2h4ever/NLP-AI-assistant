"""Các hàm của ML pipeline (Step 1 – Step 2), được gọi từ notebooks/train.ipynb."""
import json
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, cohen_kappa_score, f1_score, recall_score
from sklearn.model_selection import ParameterGrid, StratifiedGroupKFold, StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

import config
from preprocess import bo_dau, chuan_hoa, tien_xu_ly
from router import Router

COT_BAT_BUOC = ["id", "text", "label", "source"]
MO_HINH = ["Naive Bayes", "Logistic Regression", "Linear SVM"]

# Lưới tham số khi tinh chỉnh
LUOI_DAC_TRUNG = [
    {"tfidf__analyzer": ["word"], "tfidf__ngram_range": [(1, 1), (1, 2)],
     "tfidf__min_df": [1, 2], "tfidf__sublinear_tf": [True, False]},
    {"tfidf__analyzer": ["char_wb"], "tfidf__ngram_range": [(2, 4), (2, 5)],
     "tfidf__min_df": [1, 2], "tfidf__sublinear_tf": [True, False]},
]
LUOI_MO_HINH = {
    "Naive Bayes": {"clf__alpha": [0.01, 0.1, 0.5, 1.0]},
    "Logistic Regression": {"clf__C": [0.1, 1, 10, 100]},
    "Linear SVM": {"clf__C": [0.01, 0.1, 1, 10]},
}


# ---------------------------------------------------------------- 1. Dữ liệu
def doc_du_lieu(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    thieu = [c for c in COT_BAT_BUOC if c not in df.columns]
    if thieu:
        raise ValueError(f"{path} thiếu cột bắt buộc: {thieu}")
    sai = sorted(set(df.label) - set(config.NHAN) - {""})
    if sai:
        raise ValueError(f"{path} có nhãn không hợp lệ: {sai}. Nhãn hợp lệ: {list(config.NHAN)}")
    trung = df.id[df.id.duplicated()].tolist()
    if trung:
        raise ValueError(f"{path} có id bị trùng: {trung[:10]}")
    for c in ["multi_intent", "annotator", "faq_id", "nhom"]:
        if c not in df.columns:
            df[c] = ""
    # nhom: các câu là biến thể của cùng một câu gốc có chung nhóm; trống = mỗi câu một nhóm
    df["nhom"] = df.nhom.where(df.nhom != "", df.id)
    return df


def lam_sach(df: pd.DataFrame):
    """Trả về (dữ liệu sạch, bảng thống kê, các câu trùng nhưng khác nhãn cần rà lại)."""
    tk = []
    df = df.copy()
    df["text"] = df.text.map(lambda s: " ".join(unicodedata.normalize("NFC", s).split()))
    bo = (df.text == "") | (df.label == "")
    tk.append(("Bỏ câu rỗng hoặc chưa gán nhãn", int(bo.sum())))
    df = df[~bo]
    df["_khoa"] = df.text.map(chuan_hoa)
    nhom = df.groupby("_khoa").label.nunique()
    xung_dot = df[df._khoa.isin(nhom[nhom > 1].index)].sort_values("_khoa")[["id", "text", "label"]]
    trung = df._khoa.duplicated()
    tk.append(("Bỏ câu trùng (sau chuẩn hóa)", int(trung.sum())))
    df = df[~trung]
    ngan = (df._khoa.str.split().str.len() < 3) & (df.label != config.NHAN_KHAC)
    tk.append(("Bỏ câu quá ngắn (< 3 từ, trừ lớp KHAC)", int(ngan.sum())))
    df = df[~ngan]
    bang = pd.DataFrame(tk, columns=["Bước làm sạch", "Số câu bị loại"])
    return df.drop(columns="_khoa").reset_index(drop=True), bang, xung_dot


def tinh_kappa(path):
    """Đo độ đồng thuận giữa 2 người gán nhãn (file có cột text, label_a, label_b).
    Bỏ qua các dòng chưa gán đủ hai nhãn."""
    k = pd.read_csv(path, dtype=str, keep_default_na=False)
    k = k[(k.label_a.str.strip() != "") & (k.label_b.str.strip() != "")]
    if k.empty:
        raise ValueError(f"{path} chưa có dòng nào được gán đủ label_a và label_b.")
    kappa = cohen_kappa_score(k.label_a, k.label_b)
    return kappa, k[k.label_a != k.label_b]


def do_khop_nhan_tu_dong(path, df: pd.DataFrame):
    """Nếu file Kappa có cột id: so nhãn trong dữ liệu (gán theo từ khóa) với nhãn người gán (label_a)
    trên các câu người gán đồng ý với nhau. Trả về (tỉ lệ khớp, các câu không khớp) hoặc None."""
    k = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "id" not in k.columns:
        return None
    k = k[(k.label_a != "") & (k.label_a == k.label_b)].merge(df[["id", "label"]], on="id")
    if k.empty:
        return None
    return (k.label == k.label_a).mean(), k[k.label != k.label_a][["id", "text", "label", "label_a"]]


def chia_tap(df: pd.DataFrame, thu_muc_chia: Path, ti_le_test=0.2, seed=42):
    """Tập test chỉ gồm câu hỏi thật (config.NGUON_TEST) và được ĐÓNG BĂNG: lần đầu chạy, danh sách
    id của tập test được lưu vào thu_muc_chia/test_ids.txt; các lần sau dùng lại đúng danh sách đó."""
    path = Path(thu_muc_chia) / "test_ids.txt"
    if path.exists():
        ids = set(path.read_text(encoding="utf-8").split())
        thong_bao = f"Dùng lại tập test đã đóng băng ({path}, {len(ids)} id)."
    else:
        du_dieu_kien = df[df.source.isin(config.NGUON_TEST)]
        _, test = train_test_split(du_dieu_kien, test_size=ti_le_test, stratify=du_dieu_kien.label,
                                   random_state=seed)
        ids = set(test.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(sorted(ids)), encoding="utf-8")
        thong_bao = f"Đã tạo và đóng băng tập test mới ({path}, {len(ids)} id)."
    la_test = df.id.isin(ids)
    return df[~la_test].reset_index(drop=True), df[la_test].reset_index(drop=True), thong_bao


def chia_nhat_ky(df_log: pd.DataFrame, thu_muc_chia: Path, seed=42):
    """Câu hỏi thật từ nhật ký (đã gán nhãn): một nửa bổ sung vào train, một nửa làm tập test thực tế.
    Danh sách id của tập test thực tế cũng được đóng băng."""
    path = Path(thu_muc_chia) / "online_test_ids.txt"
    if path.exists():
        ids = set(path.read_text(encoding="utf-8").split())
    else:
        dem = df_log.label.value_counts()
        phan_tang = df_log.label if (dem >= 2).all() else None
        _, test = train_test_split(df_log, test_size=0.5, stratify=phan_tang, random_state=seed)
        ids = set(test.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(sorted(ids)), encoding="utf-8")
    la_test = df_log.id.isin(ids)
    return df_log[~la_test].reset_index(drop=True), df_log[la_test].reset_index(drop=True)


def them_cot_xu_ly(df: pd.DataFrame) -> pd.DataFrame:
    """Tiền xử lý một lần cho cả câu gốc và bản không dấu, có/không tách từ."""
    df = df.copy()
    df["co_dau"] = df.text.map(lambda s: bo_dau(s) != unicodedata.normalize("NFC", s))
    df["x"] = df.text.map(tien_xu_ly)
    df["x_bodau"] = df.text.map(lambda s: tien_xu_ly(bo_dau(s)))
    df["x_khong_tach"] = df.text.map(lambda s: tien_xu_ly(s, tach_tu=False))
    df["x_bodau_khong_tach"] = df.text.map(lambda s: tien_xu_ly(bo_dau(s), tach_tu=False))
    return df


def _cot(tach_tu: bool):
    return ("x", "x_bodau") if tach_tu else ("x_khong_tach", "x_bodau_khong_tach")


def tap_huan_luyen(df: pd.DataFrame, tang_cuong=True, tach_tu=True):
    """X, y để huấn luyện; nếu tang_cuong thì thêm bản không dấu của các câu có dấu."""
    cot, cot_bd = _cot(tach_tu)
    X, y = list(df[cot]), list(df.label)
    if tang_cuong:
        co_dau = df[df.co_dau]
        X += list(co_dau[cot_bd])
        y += list(co_dau.label)
    return X, y


# ---------------------------------------------------------------- 2. Mô hình
def tao_pipeline(ten: str, tham_so: dict = None, xac_suat=False) -> Pipeline:
    """Pipeline TF-IDF -> bộ phân loại. xac_suat=True: Linear SVM được bọc CalibratedClassifierCV
    để có predict_proba (độ tin cậy)."""
    tham_so = tham_so or {}
    tf = {k.split("__", 1)[1]: v for k, v in tham_so.items() if k.startswith("tfidf__")}
    cl = {k.split("__", 1)[1]: v for k, v in tham_so.items() if k.startswith("clf__")}
    tfidf = TfidfVectorizer(**{"ngram_range": (1, 2), "sublinear_tf": True, **tf})
    if ten == "Naive Bayes":
        clf = MultinomialNB(**cl)
    elif ten == "Logistic Regression":
        clf = LogisticRegression(class_weight="balanced", max_iter=3000, **cl)
    elif ten == "Linear SVM":
        clf = LinearSVC(class_weight="balanced", **cl)
        if xac_suat:
            clf = CalibratedClassifierCV(clf, cv=3)
    else:
        raise ValueError(f"Mô hình không hỗ trợ: {ten}")
    return Pipeline([("tfidf", tfidf), ("clf", clf)])


def chia_fold(df: pd.DataFrame, so_fold=5, seed=42):
    """Các fold của kiểm định chéo, giữ tỉ lệ nhãn. Nếu có cột `nhom`, các câu cùng nhóm (biến thể của
    cùng một câu gốc) luôn nằm chung một fold, để không đánh giá trên câu gần giống câu đã học."""
    if "nhom" in df.columns and df.nhom.duplicated().any():
        return StratifiedGroupKFold(so_fold, shuffle=True, random_state=seed).split(df, df.label, df.nhom)
    return StratifiedKFold(so_fold, shuffle=True, random_state=seed).split(df, df.label)


def danh_gia_cheo(df: pd.DataFrame, ten: str, tham_so: dict = None, tang_cuong=True, tach_tu=True,
                  xac_suat=False, so_fold=5, seed=42) -> dict:
    """Kiểm định chéo stratified k-fold (theo nhóm nếu có cột `nhom`). Trong mỗi fold: chỉ tăng cường
    phần train của fold, đánh giá trên câu GỐC của fold (và trên bản không dấu để đo độ bền)."""
    cot, cot_bd = _cot(tach_tu)
    lop = np.array(sorted(df.label.unique()))
    oof = np.zeros((len(df), len(lop))) if xac_suat else None
    f1, acc, f1_bd, giay = [], [], [], []
    for tr, va in chia_fold(df, so_fold, seed):
        X, y = tap_huan_luyen(df.iloc[tr], tang_cuong, tach_tu)
        t0 = time.perf_counter()
        model = tao_pipeline(ten, tham_so, xac_suat).fit(X, y)
        giay.append(time.perf_counter() - t0)
        val = df.iloc[va]
        du_doan = model.predict(val[cot])
        f1.append(f1_score(val.label, du_doan, average="macro"))
        acc.append(accuracy_score(val.label, du_doan))
        f1_bd.append(f1_score(val.label, model.predict(val[cot_bd]), average="macro"))
        if xac_suat:
            p = model.predict_proba(val[cot])
            for j, c in enumerate(model.classes_):
                oof[va, np.searchsorted(lop, c)] = p[:, j]
    return {"f1_macro": np.mean(f1), "f1_std": np.std(f1), "accuracy": np.mean(acc),
            "f1_khong_dau": np.mean(f1_bd), "giay_huan_luyen": np.mean(giay), "oof": oof, "lop": lop}


def so_sanh_mo_hinh(df: pd.DataFrame, **kw) -> pd.DataFrame:
    hang = []
    for ten in MO_HINH:
        r = danh_gia_cheo(df, ten, **kw)
        hang.append({"Mô hình": ten, "Macro-F1 (CV)": r["f1_macro"], "Độ lệch chuẩn": r["f1_std"],
                     "Accuracy (CV)": r["accuracy"], "Macro-F1 câu không dấu": r["f1_khong_dau"],
                     "Thời gian huấn luyện (giây/fold)": r["giay_huan_luyen"]})
    return pd.DataFrame(hang)


def chon_mo_hinh(bang: pd.DataFrame):
    """Chọn mô hình có Macro-F1 (CV) cao nhất. Nếu là Linear SVM thì xác suất (độ tin cậy) lấy qua
    hiệu chỉnh CalibratedClassifierCV khi huấn luyện mô hình cuối (tao_pipeline(..., xac_suat=True))."""
    bang = bang.sort_values("Macro-F1 (CV)", ascending=False).reset_index(drop=True)
    tot_nhat, nhi = bang.loc[0], bang.loc[1]
    return tot_nhat["Mô hình"], (
        f"{tot_nhat['Mô hình']} có Macro-F1 (CV) cao nhất ({tot_nhat['Macro-F1 (CV)']:.3f}), "
        f"hơn {nhi['Mô hình']} {tot_nhat['Macro-F1 (CV)'] - nhi['Macro-F1 (CV)']:.3f}.")


def thi_nghiem_nho(df: pd.DataFrame, ten: str, tham_so: dict = None) -> pd.DataFrame:
    """Ablation: mỗi lần bỏ một yếu tố, so với cấu hình đầy đủ."""
    cau_hinh = [("Đầy đủ (tách từ + tăng cường không dấu)", True, True),
                ("Không tách từ", False, True),
                ("Không tăng cường không dấu", True, False)]
    hang = []
    for mo_ta, tach_tu, tang_cuong in cau_hinh:
        r = danh_gia_cheo(df, ten, tham_so, tang_cuong=tang_cuong, tach_tu=tach_tu)
        hang.append({"Cấu hình": mo_ta, "Macro-F1 (CV)": r["f1_macro"],
                     "Macro-F1 câu không dấu": r["f1_khong_dau"]})
    return pd.DataFrame(hang)


def tim_tham_so(df: pd.DataFrame, ten: str, **kw):
    """Tìm kiếm lưới (grid search) với kiểm định chéo; trả về (tham số tốt nhất, bảng kết quả)."""
    luoi = ParameterGrid([{**g, **LUOI_MO_HINH[ten]} for g in LUOI_DAC_TRUNG])
    hang = []
    for tham_so in luoi:
        r = danh_gia_cheo(df, ten, tham_so, **kw)
        hang.append({**tham_so, "Macro-F1 (CV)": r["f1_macro"], "Độ lệch chuẩn": r["f1_std"]})
    bang = pd.DataFrame(hang).sort_values("Macro-F1 (CV)", ascending=False).reset_index(drop=True)
    tot_nhat = {k: bang.loc[0, k] for k in luoi.param_grid[0] if k in bang.columns}
    tot_nhat = {k: (tuple(v) if isinstance(v, (list, tuple, np.ndarray)) else v.item() if hasattr(v, "item") else v)
                for k, v in tot_nhat.items()}
    return tot_nhat, bang


def _dung(du_doan, y, theo_phong_ban: bool):
    """So sánh dự đoán với nhãn đúng theo chủ đề, hoặc theo phòng ban (giai đoạn 1: hai chủ đề cùng
    một phòng ban, ví dụ LICH_HOC và QUY_CHE, vẫn tính là chuyển đúng)."""
    if theo_phong_ban:
        pb = np.vectorize(config.phong_ban)
        return pb(du_doan) == pb(y)
    return du_doan == y


def chon_nguong(oof: np.ndarray, lop: np.ndarray, y, muc_tieu=0.9, theo_phong_ban=True):
    """Chọn τ nhỏ nhất sao cho precision của các câu được xử lý tự động (độ tin cậy ≥ τ, chủ đề ≠ KHAC)
    đạt ≥ muc_tieu. Câu có độ tin cậy < τ sẽ được chuyển Phòng Công tác sinh viên phân loại thủ công."""
    y = np.asarray(y)
    du_doan, tin_cay = lop[oof.argmax(1)], oof.max(1)
    dung = _dung(du_doan, y, theo_phong_ban)
    hang = []
    for t in np.round(np.arange(0.20, 0.951, 0.05), 2):
        tu_dong = (tin_cay >= t) & (du_doan != config.NHAN_KHAC)
        prec = dung[tu_dong].mean() if tu_dong.any() else np.nan
        hang.append({"tau": t, "coverage": tu_dong.mean(), "precision": prec})
    bang = pd.DataFrame(hang)
    dat = bang[bang.precision >= muc_tieu]
    if len(dat):
        tau = float(dat.tau.min())
        ghi_chu = f"τ = {tau:.2f} là ngưỡng nhỏ nhất đạt precision ≥ {muc_tieu:.0%}."
    else:
        tau = float(bang.loc[bang.precision.idxmax(), "tau"])
        ghi_chu = (f"Không ngưỡng nào đạt precision ≥ {muc_tieu:.0%}; chọn τ = {tau:.2f} có precision cao "
                   "nhất. Cần thêm dữ liệu hoặc xem lại nhãn.")
    return tau, bang, ghi_chu


def huan_luyen_cuoi(df: pd.DataFrame, ten: str, tham_so: dict, tang_cuong=True, tach_tu=True):
    X, y = tap_huan_luyen(df, tang_cuong, tach_tu)
    return tao_pipeline(ten, tham_so, xac_suat=True).fit(X, y)


def danh_gia_tap(model, df: pd.DataFrame, tau: float, ten_tap="test", theo_phong_ban=True) -> dict:
    """Đánh giá trên một tập (đã có cột x, x_bodau từ them_cot_xu_ly)."""
    proba = model.predict_proba(df.x)
    lop = model.classes_
    du_doan, tin_cay = lop[proba.argmax(1)], proba.max(1)
    y = df.label.to_numpy()
    tu_dong = (tin_cay >= tau) & (du_doan != config.NHAN_KHAC)
    co_khac = (y == config.NHAN_KHAC).any()
    dung = _dung(du_doan, y, theo_phong_ban)
    kq = {
        "Tập": ten_tap, "Số câu": len(df),
        "Accuracy": accuracy_score(y, du_doan),
        "Macro-F1": f1_score(y, du_doan, average="macro"),
        "Accuracy theo phòng ban": _dung(du_doan, y, True).mean(),
        "Recall lớp KHAC": recall_score(y == config.NHAN_KHAC, du_doan == config.NHAN_KHAC) if co_khac else np.nan,
        "Tỉ lệ xử lý tự động": tu_dong.mean(),
        "Precision xử lý tự động": dung[tu_dong].mean() if tu_dong.any() else np.nan,
        "Macro-F1 câu không dấu": f1_score(y, model.predict(df.x_bodau), average="macro"),
    }
    loi = df.assign(du_doan=du_doan, tin_cay=tin_cay)[du_doan != y][["id", "text", "label", "du_doan", "tin_cay"]]
    bao_cao = classification_report(y, du_doan, digits=3, zero_division=0)
    return {"chi_so": kq, "du_doan": du_doan, "bao_cao": bao_cao, "loi": loi}


def do_thoi_gian(model, cau_hoi: list, so_lan=50) -> float:
    """Thời gian trung bình (ms) để tiền xử lý + dự đoán một câu."""
    cau_hoi = (list(cau_hoi) * so_lan)[:so_lan]
    t0 = time.perf_counter()
    for c in cau_hoi:
        model.predict_proba([tien_xu_ly(c)])
    return (time.perf_counter() - t0) * 1000 / len(cau_hoi)


def tu_dac_trung(model, so_tu=8) -> pd.DataFrame:
    """Các từ/cụm từ có trọng số cao nhất của mỗi chủ đề (giải thích mô hình)."""
    ten_dt = model.named_steps["tfidf"].get_feature_names_out()
    clf = model.named_steps["clf"]
    if isinstance(clf, CalibratedClassifierCV):
        trong_so = np.mean([c.estimator.coef_ for c in clf.calibrated_classifiers_], axis=0)
    elif isinstance(clf, MultinomialNB):
        trong_so = clf.feature_log_prob_ - clf.feature_log_prob_.mean(axis=0)
    else:
        trong_so = clf.coef_
    return pd.DataFrame({c: [ten_dt[i] for i in trong_so[k].argsort()[::-1][:so_tu]]
                         for k, c in enumerate(clf.classes_)})


def danh_gia_faq(model, faq: pd.DataFrame, df: pd.DataFrame, muc_tieu=0.9):
    """Đánh giá bước chọn câu FAQ trên các câu có cột faq_id (đáp án đúng) và chọn ngưỡng s_min.
    Đi đúng đường của hệ thống: dự đoán chủ đề -> tìm FAQ giống nhất trong chủ đề đó."""
    co_dap_an = df[df.faq_id != ""]
    if co_dap_an.empty:
        return None, None, "Chưa có câu nào ghi faq_id nên chưa đánh giá được bước chọn FAQ."
    r = Router(model, faq, nguong_tin_cay=0, nguong_tuong_dong=0)
    nhan = model.predict(co_dap_an.x)
    kq = [r.tim_faq(q, n) for q, n in zip(co_dap_an.x, nhan)]
    dung = np.array([d is not None and d.faq_id == f for (d, _), f in zip(kq, co_dap_an.faq_id)])
    sim = np.array([s for _, s in kq])
    hang = []
    for s in np.round(np.arange(0.0, 0.61, 0.05), 2):
        giu = sim >= s
        hang.append({"s_min": s, "coverage": giu.mean(), "precision": dung[giu].mean() if giu.any() else np.nan})
    bang = pd.DataFrame(hang)
    dat = bang[bang.precision >= muc_tieu]
    s_min = float(dat.s_min.min()) if len(dat) else float(bang.loc[bang.precision.idxmax(), "s_min"])
    ghi_chu = (f"Top-1 chọn đúng FAQ: {dung.mean():.1%} trên {len(dung)} câu. "
               f"Chọn s_min = {s_min:.2f}" + ("." if len(dat) else f" (không ngưỡng nào đạt {muc_tieu:.0%})."))
    return s_min, bang, ghi_chu


def luu_model(model, thu_muc: Path, metadata: dict):
    thu_muc = Path(thu_muc)
    thu_muc.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, thu_muc / "model.joblib")
    metadata = {**metadata, "ngay_huan_luyen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "scikit_learn": sklearn.__version__}
    (thu_muc / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return thu_muc
