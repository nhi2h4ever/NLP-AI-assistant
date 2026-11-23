"""Nhật ký câu hỏi: ghi vào file CSV (chạy trên máy) hoặc Google Sheets (khi triển khai).
Chọn bằng khóa `log_backend` trong .streamlit/secrets.toml."""
import re
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd

import config
from preprocess import an_danh

COT = ["id", "thoi_gian", "cau_hoi", "chu_de", "do_tin_cay", "hanh_dong", "faq_id", "phong_ban",
       "thoi_gian_xu_ly_ms", "phien_ban_model", "danh_gia", "nhan_dung",
       # QT_11_CTSV bước 3: chuyên viên P.CTSV nhập câu trả lời; sinh viên tra cứu bằng mã yêu cầu.
       # Cột mới luôn thêm vào CUỐI để nhật ký cũ vẫn đúng thứ tự cột.
       "phan_hoi", "thoi_gian_phan_hoi"]
_KHOA = threading.Lock()
_MA_YEU_CAU = re.compile(r"^[0-9a-f]{8}$")


def tao_dong(ma: str, cau_hoi: str, kq, phien_ban: str) -> dict:
    """Một dòng nhật ký. Câu hỏi được ẩn MSSV/SĐT/email trước khi lưu."""
    return {
        "id": ma, "thoi_gian": bay_gio(),
        "cau_hoi": an_danh(cau_hoi.strip()), "chu_de": kq.chu_de, "do_tin_cay": round(kq.do_tin_cay, 4),
        "hanh_dong": kq.hanh_dong, "faq_id": kq.faq_id, "phong_ban": kq.phong_ban,
        "thoi_gian_xu_ly_ms": round(kq.thoi_gian_ms, 1), "phien_ban_model": phien_ban,
        "danh_gia": "", "nhan_dung": "", "phan_hoi": "", "thoi_gian_phan_hoi": "",
    }


def bay_gio() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def chuan_ma(ma: str) -> str | None:
    """Mã yêu cầu sinh viên nhập (bỏ khoảng trắng, chữ thường); None nếu sai định dạng (8 ký tự 0-9, a-f)."""
    ma = str(ma).strip().lower()
    return ma if _MA_YEU_CAU.match(ma) else None


def tim_theo_ma(df: pd.DataFrame, ma: str):
    """Dòng nhật ký có mã yêu cầu `ma` (dạng dict), hoặc None."""
    ma = chuan_ma(ma)
    if ma is None:
        return None
    dong = df[df["id"] == ma]
    return dong.iloc[0].to_dict() if len(dong) else None


def _chuan_kieu(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reindex(columns=COT).astype(object).fillna("")
    for c in ["do_tin_cay", "thoi_gian_xu_ly_ms"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in COT:
        if c not in ("do_tin_cay", "thoi_gian_xu_ly_ms"):
            df[c] = df[c].astype(str)
    return df


class NhatKyCSV:
    def __init__(self, path):
        self.path = Path(path)
        self.mo_ta = f"file CSV trên máy ({self.path}) — chỉ phù hợp khi chạy trên máy"

    def _nang_cap(self):
        """Nhật ký tạo từ phiên bản cũ thiếu cột mới: viết lại file với đủ cột (giữ nguyên dữ liệu)."""
        if self.path.exists():
            cu = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            if list(cu.columns) != COT:
                cu.reindex(columns=COT).astype(object).fillna("").to_csv(self.path, index=False, encoding="utf-8")

    def ghi(self, dong: dict):
        with _KHOA:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._nang_cap()
            pd.DataFrame([dong], columns=COT).to_csv(
                self.path, mode="a", header=not self.path.exists(), index=False, encoding="utf-8")

    def doc(self) -> pd.DataFrame:
        if not self.path.exists():
            return _chuan_kieu(pd.DataFrame(columns=COT))
        return _chuan_kieu(pd.read_csv(self.path, dtype=str, keep_default_na=False))

    def cap_nhat_nhieu(self, thay_doi: dict):
        """thay_doi: {id: {tên cột: giá trị}}"""
        with _KHOA:
            self._nang_cap()
            df = pd.read_csv(self.path, dtype=str, keep_default_na=False)
            for ma, cot_gia_tri in thay_doi.items():
                for cot, gia_tri in cot_gia_tri.items():
                    df.loc[df["id"] == ma, cot] = str(gia_tri)
            df.to_csv(self.path, index=False, encoding="utf-8")

    def cap_nhat(self, ma: str, **cot_gia_tri):
        self.cap_nhat_nhieu({ma: cot_gia_tri})


class NhatKyGoogleSheets:
    def __init__(self, thong_tin_tai_khoan: dict, sheet_url: str, ten_trang: str = "nhat_ky"):
        import gspread

        gc = gspread.service_account_from_dict(thong_tin_tai_khoan)
        bang = gc.open_by_url(sheet_url)
        try:
            self.ws = bang.worksheet(ten_trang)
        except gspread.WorksheetNotFound:
            self.ws = bang.add_worksheet(ten_trang, rows=1000, cols=len(COT))
            self.ws.append_row(COT)
        self._nang_cap()
        self.mo_ta = f"Google Sheets (trang “{ten_trang}”)"

    def _nang_cap(self):
        """Sheet tạo từ phiên bản cũ: bổ sung tên các cột mới vào cuối dòng tiêu đề."""
        tieu_de = self.ws.row_values(1)
        if tieu_de != COT and tieu_de == COT[:len(tieu_de)]:
            if self.ws.col_count < len(COT):
                self.ws.add_cols(len(COT) - self.ws.col_count)
            self.ws.update([COT], "A1")

    def ghi(self, dong: dict):
        self.ws.append_row([dong[c] for c in COT], value_input_option="RAW")

    def doc(self) -> pd.DataFrame:
        gia_tri = self.ws.get_all_values()
        if len(gia_tri) <= 1:
            return _chuan_kieu(pd.DataFrame(columns=COT))
        return _chuan_kieu(pd.DataFrame(gia_tri[1:], columns=gia_tri[0]))

    def cap_nhat_nhieu(self, thay_doi: dict):
        from gspread.utils import rowcol_to_a1

        hang_theo_id = {ma: i + 1 for i, ma in enumerate(self.ws.col_values(1))}
        cap_nhat = []
        for ma, cot_gia_tri in thay_doi.items():
            if ma not in hang_theo_id:
                raise KeyError(f"Không tìm thấy id {ma} trong Google Sheets")
            for cot, gia_tri in cot_gia_tri.items():
                cap_nhat.append({"range": rowcol_to_a1(hang_theo_id[ma], COT.index(cot) + 1),
                                 "values": [[str(gia_tri)]]})
        if cap_nhat:
            self.ws.batch_update(cap_nhat)

    def cap_nhat(self, ma: str, **cot_gia_tri):
        self.cap_nhat_nhieu({ma: cot_gia_tri})


def doc_secrets() -> dict:
    """Đọc st.secrets; trả về {} khi chưa có file secrets (chạy trên máy lần đầu)."""
    import streamlit as st

    try:
        return {k: st.secrets[k] for k in st.secrets}
    except FileNotFoundError:  # StreamlitSecretNotFoundError là lớp con của FileNotFoundError
        return {}


def tao_nhat_ky(secrets: dict):
    loai = secrets.get("log_backend", "csv")
    if loai == "csv":
        return NhatKyCSV(secrets.get("log_csv_path", config.LOG_DIR / "nhat_ky.csv"))
    if loai == "sheets":
        return NhatKyGoogleSheets(dict(secrets["gcp_service_account"]), secrets["sheet_url"])
    raise ValueError(f"log_backend không hợp lệ: {loai!r} (chỉ nhận 'csv' hoặc 'sheets')")


def ban_ghi_phan_hoi(bang_moi: pd.DataFrame, df: pd.DataFrame, thoi_gian: str) -> dict:
    """So bảng phản hồi chuyên viên vừa sửa với nhật ký; trả về {id: {phan_hoi, thoi_gian_phan_hoi}} cho
    các câu thay đổi. Xóa phản hồi thì xóa luôn thời gian phản hồi."""
    moi = bang_moi[["id", "phan_hoi"]].merge(df[["id", "phan_hoi"]], on="id", suffixes=("", "_cu"))
    moi["phan_hoi"] = moi.phan_hoi.fillna("").astype(str).str.strip()
    moi = moi[moi.phan_hoi != moi.phan_hoi_cu.str.strip()]
    return {r.id: {"phan_hoi": r.phan_hoi, "thoi_gian_phan_hoi": thoi_gian if r.phan_hoi else ""}
            for r in moi.itertuples()}


def du_lieu_huan_luyen_lai(df: pd.DataFrame) -> pd.DataFrame:
    """Các câu đã được cán bộ/nhóm điền nhãn đúng -> định dạng questions.csv (source = 'log')."""
    da_gan = df[df["nhan_dung"].isin(list(config.NHAN))]
    return pd.DataFrame({
        "id": "LOG_" + da_gan["id"], "text": da_gan["cau_hoi"], "label": da_gan["nhan_dung"],
        "source": "log", "multi_intent": 0, "annotator": "quan_tri", "faq_id": "",
    })
