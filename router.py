"""Bộ xử lý câu hỏi: mô hình ML phân loại + chính sách quyết định + tìm câu FAQ."""
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

import config
from preprocess import tien_xu_ly

COT_FAQ = ["faq_id", "label", "question", "variants", "answer", "source", "updated_at", "department"]
_CO_CHU = re.compile(r"[^\W\d_]")  # có ít nhất một chữ cái

# Hành động của hệ thống với một câu hỏi
CHUYEN_TIEP = "chuyen_tiep"        # đủ tin cậy: chuyển đến phòng ban phụ trách chủ đề (KHAC -> trợ lý khoa)
CAN_PHAN_LOAI = "can_phan_loai"    # chưa đủ tin cậy: chuyển trợ lý khoa phân loại thủ công
TRA_LOI = "tra_loi"                # giai đoạn 2: trả lời tự động bằng kho FAQ
LOI_DAU_VAO = "loi_dau_vao"        # câu hỏi rỗng / quá dài / không có chữ


@dataclass
class KetQua:
    hanh_dong: str                      # một trong các hằng số ở trên
    thong_bao: str = ""
    chu_de: str = ""
    ten_chu_de: str = ""
    do_tin_cay: float = 0.0
    top3: list = field(default_factory=list)   # [(mã nhãn, xác suất), ...]
    phong_ban: str = ""
    cau_tra_loi: str = ""
    nguon: str = ""
    cap_nhat: str = ""
    faq_id: str = ""
    do_tuong_dong: float = 0.0
    thoi_gian_ms: float = 0.0


def kiem_tra_dau_vao(cau_hoi: str):
    """Trả về thông báo lỗi nếu câu hỏi không hợp lệ, None nếu hợp lệ."""
    cau_hoi = (cau_hoi or "").strip()
    if not cau_hoi:
        return "Bạn chưa nhập câu hỏi."
    if len(cau_hoi) > config.MAX_LEN:
        return f"Câu hỏi dài {len(cau_hoi)} ký tự, vượt giới hạn {config.MAX_LEN} ký tự. Bạn vui lòng rút gọn câu hỏi."
    if not _CO_CHU.search(cau_hoi):
        return "Câu hỏi chưa có nội dung chữ. Bạn vui lòng nhập câu hỏi bằng tiếng Việt."
    return None


def doc_faq(path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy kho FAQ: {path}. Tạo file này theo mẫu data/templates/faq_template.csv.")
    faq = pd.read_csv(path, dtype=str).fillna("")
    thieu = [c for c in COT_FAQ if c not in faq.columns]
    if thieu:
        raise ValueError(f"Kho FAQ {path} thiếu cột: {thieu}")
    sai = sorted(set(faq.label) - set(config.NHAN))
    if sai:
        raise ValueError(f"Kho FAQ {path} có nhãn không hợp lệ: {sai}")
    pb_sai = sorted(set(faq.department) - set(config.PHONG_BAN) - {""})
    if pb_sai:
        raise ValueError(f"Kho FAQ {path} có phòng ban không có trong config.PHONG_BAN: {pb_sai}")
    return faq


class Router:
    """faq = None  -> giai đoạn 1: chỉ phân loại và chuyển phòng ban.
    faq = bảng FAQ -> giai đoạn 2: thêm trả lời tự động bằng câu FAQ giống nhất."""

    def __init__(self, model, faq: pd.DataFrame = None, nguong_tin_cay: float = 0.5,
                 nguong_tuong_dong: float = None, phien_ban: str = ""):
        self.model = model
        self.nguong_tin_cay = float(nguong_tin_cay)
        self.phien_ban = phien_ban
        self.tra_loi_tu_dong = faq is not None
        self._faq_theo_nhan = {}
        if self.tra_loi_tu_dong:
            if nguong_tuong_dong is None:
                raise ValueError("Cần ngưỡng tương đồng FAQ (nguong_tuong_dong) khi bật trả lời tự động.")
            self.nguong_tuong_dong = float(nguong_tuong_dong)
            self.faq = faq.reset_index(drop=True)
            # Vector TF-IDF của mỗi câu FAQ (câu hỏi chuẩn + các cách hỏi khác), tính sẵn theo từng chủ đề
            vec = model.named_steps["tfidf"]
            mau = (self.faq.question + " ; " + self.faq.variants.str.replace(";", " ; ")).map(tien_xu_ly)
            for nhan, nhom in self.faq.groupby("label"):
                self._faq_theo_nhan[nhan] = (nhom.index.to_numpy(), vec.transform(mau.loc[nhom.index]))

    @classmethod
    def tu_thu_muc(cls, model_dir, faq_path=None):
        """faq_path = None: giai đoạn 1 (không dùng kho FAQ)."""
        model_dir = Path(model_dir)
        if not (model_dir / "model.joblib").exists():
            raise FileNotFoundError(
                f"Chưa có model tại {model_dir}. Hãy chạy notebooks/train.ipynb để huấn luyện "
                f"(hoặc sửa MODEL_VERSION trong config.py).")
        meta = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
        faq, nguong_faq = None, None
        if faq_path is not None:
            if meta.get("nguong_tuong_dong") is None:
                raise ValueError(f"Model {model_dir.name} chưa có ngưỡng tương đồng FAQ. Huấn luyện lại với "
                                 "TRA_LOI_TU_DONG = True để notebook chọn ngưỡng này.")
            faq, nguong_faq = doc_faq(faq_path), meta["nguong_tuong_dong"]
        return cls(joblib.load(model_dir / "model.joblib"), faq, meta["nguong_tin_cay"], nguong_faq,
                   meta.get("phien_ban", model_dir.name))

    def tim_faq(self, q_da_xu_ly: str, nhan: str):
        """Câu FAQ giống nhất trong chủ đề `nhan`. Trả về (dòng FAQ, độ tương đồng) hoặc (None, 0)."""
        if nhan not in self._faq_theo_nhan:
            return None, 0.0
        chi_so, ma_tran = self._faq_theo_nhan[nhan]
        vec_q = self.model.named_steps["tfidf"].transform([q_da_xu_ly])
        sim = cosine_similarity(vec_q, ma_tran)[0]
        j = int(sim.argmax())
        return self.faq.loc[chi_so[j]], float(sim[j])

    def xu_ly(self, cau_hoi: str) -> KetQua:
        bat_dau = time.perf_counter()
        loi = kiem_tra_dau_vao(cau_hoi)
        if loi:
            return KetQua(hanh_dong=LOI_DAU_VAO, thong_bao=loi)

        q = tien_xu_ly(cau_hoi)
        proba = self.model.predict_proba([q])[0]
        lop = self.model.classes_
        thu_tu = proba.argsort()[::-1]
        nhan, tin_cay = str(lop[thu_tu[0]]), float(proba[thu_tu[0]])
        ten, phong_ban = config.NHAN[nhan]
        kq = KetQua(hanh_dong=CHUYEN_TIEP, chu_de=nhan, ten_chu_de=ten, do_tin_cay=tin_cay,
                    top3=[(str(lop[i]), float(proba[i])) for i in thu_tu[:3]], phong_ban=phong_ban)

        # Chính sách quyết định
        if tin_cay < self.nguong_tin_cay:
            kq.hanh_dong = CAN_PHAN_LOAI
            kq.phong_ban = config.PHONG_BAN_XEM_LAI
            kq.thong_bao = (f"Hệ thống chưa chắc chắn câu hỏi thuộc chủ đề nào. Câu hỏi đã được chuyển đến "
                            f"{config.PHONG_BAN_XEM_LAI} để phân loại và hỗ trợ.")
        elif nhan == config.NHAN_KHAC:
            kq.thong_bao = (f"Câu hỏi nằm ngoài các chủ đề học vụ hệ thống hỗ trợ, đã được chuyển đến "
                            f"{phong_ban}. Cán bộ sẽ phản hồi cho bạn.")
        elif not self.tra_loi_tu_dong:
            kq.thong_bao = f"Câu hỏi đã được chuyển đến {phong_ban}. Cán bộ sẽ phản hồi cho bạn."
        else:
            dong, sim = self.tim_faq(q, nhan)
            kq.do_tuong_dong = sim
            if dong is not None and sim >= self.nguong_tuong_dong:
                kq.hanh_dong = TRA_LOI
                kq.cau_tra_loi, kq.nguon, kq.cap_nhat = dong.answer, dong.source, dong.updated_at
                kq.faq_id = dong.faq_id
                kq.phong_ban = dong.department or phong_ban
            else:
                kq.thong_bao = (f"Chưa có câu trả lời sẵn cho câu hỏi này. Câu hỏi đã được chuyển đến "
                                f"{phong_ban} để hỗ trợ.")
        kq.thoi_gian_ms = (time.perf_counter() - bat_dau) * 1000
        return kq
