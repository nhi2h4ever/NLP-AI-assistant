"""Tạo data/questions.csv (7 nhãn của dự án) từ dữ liệu gốc trong data/raw/.

Nguồn (xem README, mục "Dữ liệu"):
- data/raw/docx_cau_hoi.csv: câu hỏi trích từ 3 file Word có nguồn
    * kieu = chuan     : 76 câu hỏi–đáp công khai của UEF, PTIT, ULAW (đã diễn đạt lại)  -> source = faq
    * kieu = nhieu: …  : 228 biến thể nhiễu của 76 câu trên (do công cụ tạo)              -> source = noise
    * kieu = generated : 300 câu mô phỏng về DUT (30 ý × 10 cách hỏi)                       -> source = generated
- data/raw/web_ticket.csv: câu hỏi THẬT của sinh viên trên trang hỏi đáp công khai
    (tuvan.vhu.edu.vn – Trường ĐH Văn Hiến, hlu.edu.vn/qa – Trường ĐH Luật Hà Nội)          -> source = web

Gán nhãn:
- Câu trong file Word đã có nhãn gốc -> ánh xạ sang 7 nhãn bằng bảng ANH_XA (+ sửa riêng từng câu ở SUA_RIENG).
- Ticket trên web chưa có nhãn -> gán theo từ khóa (TU_KHOA), rồi nhóm rà lại. Câu không khớp từ khóa nào
  (quá mơ hồ, ví dụ "Tìm hiểu thông tin") hoặc khớp nhiều chủ đề ngang nhau (nhiều ý) bị loại.
- Câu trong chuyên mục đời sống của UIT forum không khớp từ khóa học vụ nào -> KHAC (ngoài phạm vi).
- Cột `nhom`: các câu là biến thể của cùng một câu gốc có chung `nhom`, để kiểm định chéo không chia
  chúng vào các fold khác nhau (tránh rò rỉ).

Chạy:  python scripts/tao_du_lieu.py
"""
import hashlib
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from preprocess import bo_dau  # noqa: E402

RAW = ROOT / "data" / "raw"
SEED = 42
TOI_DA_MOI_NHAN = 400  # số ticket VHU tối đa mỗi nhãn (lấy ngẫu nhiên), để các nhãn không chênh lệch quá nhiều

# ------------------------------------------------------------------ 1. File Word: ánh xạ nhãn gốc
BO = None  # loại khỏi dữ liệu (không thuộc chủ đề nào của dự án, cũng không phải câu hỏi ngoài phạm vi rõ ràng)
ANH_XA = {
    # file 1, 2 (UEF, PTIT, ULAW)
    "dang_ky_hoc_phan": "LICH_HOC", "nghi_hoc_hoc_bu": "LICH_HOC",
    "lich_thi": "LICH_THI", "phuc_khao": "LICH_THI", "diem_so": "LICH_THI",
    "hoc_phi": "HOC_PHI",
    "hoc_bong": "HOC_BONG", "mien_giam_hoc_phi": "HOC_BONG",
    "tot_nghiep": "QUY_CHE", "chuan_dau_ra": "QUY_CHE", "chuyen_nganh": "QUY_CHE", "dao_tao_khac": "QUY_CHE",
    "tuyen_sinh": "KHAC", "thu_vien": "KHAC", "giay_xac_nhan": "KHAC", "y_te_bhyt": "KHAC",
    "hoat_dong_doan_hoi": "KHAC", "nghien_cuu_khoa_hoc": "KHAC", "diem_ren_luyen": "KHAC", "the_sinh_vien": "KHAC",
    "lien_he_phong_ban": BO,
    # file DUT 300 câu
    "LICH_HOC": "LICH_HOC", "DANG_KY_HP": "LICH_HOC",
    "LICH_THI": "LICH_THI", "THI_BO_SUNG": "LICH_THI", "PHUC_KHAO": "LICH_THI",
    "HOC_PHI": "HOC_PHI", "HOC_BONG": "HOC_BONG",
    "DAO_TAO": "QUY_CHE", "CONG_NHAN_KQHT": "QUY_CHE", "TOT_NGHIEP": "QUY_CHE",
    "THU_TUC": "KHAC", "TAI_KHOAN": "KHAC", "BAO_HIEM": "KHAC", "THE_SV": "KHAC", "TUYEN_SINH": "KHAC",
    "LIEN_HE": BO, "HO_TRO": BO, "VAN_BAN": BO,
}
# Sửa riêng: câu mà nhãn gốc không khớp định nghĩa nhãn của dự án (theo mã câu gốc ở file 1)
SUA_RIENG = {
    "C043": "QUY_CHE",   # điểm trung bình tích lũy tính theo ngành -> quy chế
    "C046": "QUY_CHE",   # thang điểm (không có A+) -> quy chế
    "C033": "KHAC",      # học lên tiến sĩ -> ngoài phạm vi
    "C045": "LICH_HOC",  # xin đổi giảng viên -> đổi lớp học phần
    "C053": "QUY_CHE",   # học tích lũy chương trình song bằng -> quy chế
}
NHIEU_Y = {"C022", "C024", "C028", "C018"}  # câu hỏi hai ý (tín chỉ + học phí, điểm ưu tiên + học bổng)


def tu_docx() -> pd.DataFrame:
    d = pd.read_csv(RAW / "docx_cau_hoi.csv", dtype=str, keep_default_na=False)
    d["label"] = d.nhan_goc.map(ANH_XA)
    sua = d.ma_goc.map(SUA_RIENG)
    d.loc[sua.notna(), "label"] = sua[sua.notna()]
    chua_co = sorted(set(d.nhan_goc) - set(ANH_XA))
    if chua_co:
        raise ValueError(f"Nhãn gốc chưa có trong bảng ánh xạ: {chua_co}")
    d["source"] = d.kieu.map(lambda k: "faq" if k == "chuan" else "noise" if k.startswith("nhieu") else "generated")
    d["nguon"] = d.tep
    d["nhom"] = d.ma_goc
    d["multi_intent"] = d.ma_goc.isin(NHIEU_Y).astype(int)
    d["annotator"] = "anh_xa_nhan_goc"
    return d


# ------------------------------------------------------------------ 2. Ticket web: gán nhãn theo từ khóa
# (nhãn, mức, các cụm từ). Mức 2 = từ khóa rõ ràng; mức 1 = từ khóa chung, chỉ dùng khi không có từ khóa mức 2;
# mức 3 = trường hợp đặc biệt, thắng mọi từ khóa khác. Nhãn None = chỉ "che" cụm từ đi (ví dụ "địa điểm" không
# phải "điểm" thi). Nhãn "LOAI" = câu không phải của sinh viên đang học (doanh nghiệp, tuyển dụng...) -> loại.
# Cụm mức 3 được so trước, rồi đến cụm dài trước cụm ngắn; cụm đã khớp bị che lại, nên
# "khóa luận tốt nghiệp" chỉ tính DO_AN, không tính thêm "tốt nghiệp".
# Viết có dấu; câu không dấu được so với bản bỏ dấu của từ khóa.
TU_KHOA = [
    ("LOAI", 3, ["công ty", "cty", "cần tuyển", "tuyển thực tập", "tìm sinh viên", "hợp tác",
                 "đối tác", "khách hàng", "quảng cáo", "nhạc chờ", "tuyển dụng", "cuộc thi", "thi đấu", "hội thao"]),
    (None, 0, ["địa điểm", "thời điểm", "điểm chuẩn", "điểm ưu tiên", "điểm cộng", "điểm sàn", "điểm xét tuyển",
               "điểm thi đại học", "điểm thi tsđh", "thi đại học", "thi tuyển sinh", "lịch sinh hoạt",
               "lịch làm việc", "lịch công tác", "nghỉ học tạm thời", "thông tin", "ưu nhược điểm", "ưu điểm",
               "nhược điểm", "điểm mạnh", "điểm yếu", "du lịch", "dương lịch", "âm lịch", "lịch sử"]),
    ("KHAC", 3, ["thi b1", "thi b2", "thi c1", "thi a2", "thi tin học", "thi ngoại ngữ", "thi anh văn", "thi tin",
                 "thi chứng chỉ", "thi tiếng nhật", "thi toeic", "kết quả thi b1", "điểm thi c1", "điểm thi b1",
                 "lịch thi tin học", "lịch thi ngoại ngữ", "trung tâm ngoại ngữ", "xác minh văn bằng",
                 "xác nhận văn bằng", "điểm rèn luyện", "bảng điểm", "giấy xác nhận", "điểm thi anh văn",
                 "đăng ký thi tin", "lịch học tin học", "lịch học ngoại ngữ", "học tin học", "học ngoại ngữ",
                 "thi av", "av b1", "av b2", "nghiên cứu khoa học", "nckh", "học b1", "học b2"]),
    ("DO_AN", 2, ["đồ án", "khóa luận", "khoá luận", "luận văn", "thực tập", "kiến tập", "giảng viên hướng dẫn",
                  "gvhd", "giảng viên hd", "đề tài tốt nghiệp", "báo cáo tốt nghiệp", "đề tài", "bảo vệ khóa luận",
                  "đồ án tốt nghiệp", "khóa luận tốt nghiệp", "khoá luận tốt nghiệp", "thực tập tốt nghiệp",
                  "đề cương khóa luận", "kltn", "datn"]),
    ("HOC_BONG", 2, ["học bổng", "miễn giảm", "miễn học phí", "giảm học phí", "trợ cấp", "hộ nghèo", "cận nghèo",
                     "con thương binh", "con liệt sĩ", "chế độ chính sách", "đối tượng chính sách", "hỗ trợ học phí",
                     "ưu đãi học phí", "chính sách giảm", "được giảm", "giảm 10%", "giảm 20%", "giảm 30%",
                     "giảm 50%", "miễn giảm học phí", "mghp", "hb kkht", "kkht", "học phí được miễn",
                     "được miễn học phí", "giam hoc phi", "mien giam"]),
    ("HOC_PHI", 2, ["học phí", "tiền học", "đóng tiền", "nộp tiền", "đóng phí", "lệ phí", "phiếu đóng tiền",
                    "phiếu thu", "biên lai", "hóa đơn", "công nợ", "cấn trừ", "hoàn tiền", "rút tiền", "hoàn phí",
                    "chuyển khoản", "nợ phí", "mức thu", "đóng hp", "tiền hp", "thu tiền", "trả tiền",
                    "đóng học", "nộp học", "số tiền", "tiền dư", "đóng dư", "nợ tiền", "giấy nộp tiền",
                    "đóng tiên", "hp 1 năm", "hp mình", "hp kỳ", "hp kì", "hp học kỳ", "thanh toán"]),
    ("HOC_PHI", 1, ["số tài khoản", "stk", "tài khoản ngân hàng", "tiền"]),
    ("LICH_THI", 2, ["lịch thi", "thi lại", "thi cuối kỳ", "thi cuối kì", "thi giữa kỳ", "thi giữa kì",
                     "thi học kỳ", "thi học kì", "thi kết thúc", "kỳ thi", "kì thi", "hoãn thi", "vắng thi",
                     "phúc khảo", "chấm lại", "điểm thi", "kết quả thi", "phòng thi", "ca thi", "thi bổ sung",
                     "cấm thi", "dự thi", "điểm kết thúc", "điểm giữa kỳ", "điểm quá trình", "điểm học phần",
                     "nhập điểm", "sai điểm", "điểm môn", "chưa có điểm", "xem điểm", "thi vấn đáp", "lịch kiểm tra",
                     "kết quả học tập", "điểm trên portal", "thi tốt nghiệp", "trùng lịch thi", "thi phụ",
                     "ôn thi", "khiếu nại điểm", "công bố điểm", "phiếu điểm", "điểm tiểu luận", "nghỉ thi",
                     "đi thi", "điểm thực hành", "thi thực hành", "được thi"]),
    ("LICH_THI", 1, ["điểm", "thi"]),
    ("LICH_HOC", 2, ["lịch học", "thời khóa biểu", "thời khoá biểu", "tkb", "đăng ký học phần", "đăng kí học phần",
                     "đkhp", "đăng ký môn", "đăng kí môn", "lớp học phần", "học lại", "học cải thiện", "học vượt",
                     "học ghép", "rút môn", "rút học phần", "hủy học phần", "huỷ học phần", "hủy môn", "trùng lịch",
                     "trùng môn", "trùng học phần", "đổi lớp", "chuyển lớp", "giờ học", "ca học", "buổi học",
                     "học bù", "nghỉ dạy", "lịch khai giảng", "ngày đi học", "bắt đầu học", "học hè",
                     "học kỳ hè", "đăng ký học", "đăng kí học", "kế hoạch đào tạo", "kế hoạch học tập", "mở lớp",
                     "đk học phần", "đk hp", "đăng ký hp", "xóa học phần", "đăng ký thêm", "phòng học",
                     "lịch học bù", "học phần bổ sung", "học gdqp", "học quân sự", "học quốc phòng", "gdqp",
                     "điểm danh", "có nghỉ học không", "nghỉ học do", "được nghỉ học", "địa điểm học",
                     "vào học lại", "ngày vào học", "lịch học lại", "đăng kí hp", "đk môn", "dk hoc phan",
                     "học phần hè"]),
    ("LICH_HOC", 1, ["học phần", "môn học", "lớp học", "học kỳ", "học kì", "lịch"]),
    ("QUY_CHE", 2, ["tốt nghiệp", "chuẩn đầu ra", "đầu ra", "bảo lưu", "thôi học", "tạm ngưng", "tạm dừng",
                    "quy chế", "cảnh báo học vụ", "buộc thôi học", "chuyển ngành", "chuyển nghành", "chuyển trường",
                    "chuyển hệ", "song ngành", "văn bằng 2", "văn bằng hai", "học song song", "công nhận tín chỉ",
                    "chuyển điểm", "miễn học phần", "tín chỉ tích lũy", "trung bình tích lũy", "xếp loại",
                    "gpa", "chương trình đào tạo", "thời gian đào tạo", "ra trường", "học tiếp", "quay lại học",
                    "đi học lại", "nhập học lại", "xin nghỉ học", "chuyển chuyên ngành", "chuyển sang ngành",
                    "đổi ngành", "đổi chuyên ngành", "nhận bằng", "cấp bằng", "bằng cử nhân", "văn bằng",
                    "số tín chỉ", "tín chỉ tối thiểu", "tối thiểu", "điểm trung bình", "tính điểm", "phân ngành",
                    "chuyển đổi ngành", "môn bắt buộc", "bắt buộc", "học vụ", "tiếp tục học", "nghỉ học", "lễ phục",
                    "học tối đa", "thời gian tối đa"]),
    ("QUY_CHE", 1, ["tín chỉ"]),
    ("KHAC", 2, ["thẻ sinh viên", "thẻ sv", "bhyt", "bảo hiểm", "xác nhận sinh viên",
                 "giấy chứng nhận", "ký túc xá", "ktx", "chỗ ở", "nhà trọ", "phòng trọ", "mật khẩu", "password",
                 "reset pass", "đoàn viên", "sổ đoàn", "hội sinh viên", "câu lạc bộ", "clb", "rèn luyện",
                 "thư viện", "đồng phục", "nghĩa vụ quân sự", "nvqs", "xe buýt", "gửi xe", "giữ xe", "việc làm",
                 "tuyển sinh", "xét tuyển", "học bạ", "hồ sơ nhập học", "nhập học", "trích lục", "sao y", "balo",
                 "sinh hoạt công dân", "tư vấn tâm lý", "y tế", "khám sức khỏe", "tình nguyện", "ngoại khóa",
                 "chứng chỉ", "ngoại ngữ", "tin học", "email", "wifi", "căn tin", "đồ thất lạc", "mất đồ",
                 "vay vốn", "ngân hàng chính sách", "hồ sơ sinh viên", "cập nhật thông tin", "sai thông tin",
                 "lý lịch", "sinh hoạt đầu khóa", "cơ sở", "địa chỉ trường", "giờ làm việc", "liên hệ phòng",
                 "hạnh kiểm", "ngoại trú", "nội trú", "chọn ngành", "nguyện vọng", "tân sinh viên", "thí sinh",
                 "tài khoản", "đăng nhập", "toeic", "ielts", "anh văn"]),
    ("KHAC", 1, ["portal", "xác nhận", "hồ sơ"]),
]
# Khi khớp nhiều chủ đề cùng mức: nhãn trước thắng nhãn sau (ví dụ "học bổng đã cấn trừ" -> HOC_BONG)
UU_TIEN = [("HOC_BONG", "HOC_PHI"), ("DO_AN", "LICH_HOC"), ("QUY_CHE", "LICH_HOC"), ("KHAC", "QUY_CHE")]
# Mức 2 của QUY_CHE thắng KHAC mức 2 khi câu chứa các cụm này (ví dụ "chứng chỉ anh văn để tốt nghiệp")
QUY_CHE_THANG_KHAC = ["tốt nghiệp", "đầu ra", "ra trường", "cấp bằng"]
# Thứ tự so: cụm mức 3 trước, sau đó cụm dài trước cụm ngắn
_CUM = sorted(((c, nhan, muc) for nhan, muc, ds in TU_KHOA for c in ds), key=lambda x: (x[2] != 3, -len(x[0])))


def _tim(text: str, cum: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(cum) + r"(?!\w)", text) is not None


def _che(text: str, cum: str) -> str:
    return re.sub(r"(?<!\w)" + re.escape(cum) + r"(?!\w)", " ¤ ", text)


def gan_nhan(text: str):
    """Trả về (nhãn, ghi chú). Nhãn None = loại."""
    t = " ".join(unicodedata.normalize("NFC", text).lower().split())
    co_dau = bo_dau(t) != t
    khop = {}
    for cum, nhan, muc in _CUM:
        c = cum if co_dau else bo_dau(cum)
        if _tim(t, c):
            t = _che(t, c)
            if nhan is not None:
                khop[nhan] = max(khop.get(nhan, 0), muc)
    if "LOAI" in khop:
        return None, "không phải câu hỏi của sinh viên"
    if not khop:
        return None, "không khớp từ khóa"
    cao = max(khop.values())
    ung_vien = {n for n, m in khop.items() if m == cao}
    goc = " ".join(unicodedata.normalize("NFC", text).lower().split())
    if {"QUY_CHE", "KHAC"} <= ung_vien and any(_tim(goc if co_dau else bo_dau(goc), c if co_dau else bo_dau(c))
                                               for c in QUY_CHE_THANG_KHAC):
        ung_vien.discard("KHAC")
    for thang, thua in UU_TIEN:
        if thang in ung_vien and thua in ung_vien:
            ung_vien.discard(thua)
    if len(ung_vien) > 1:
        return None, "nhiều chủ đề: " + "+".join(sorted(ung_vien))
    nhan = ung_vien.pop()
    if cao == 1 and nhan != "KHAC" and len(goc.split()) < 4:
        return None, "mơ hồ"
    return nhan, ""


# Chuyên mục đời sống của UIT forum (tán gẫu, tâm sự, chỗ trọ, việc làm thêm): câu không khớp từ khóa học vụ
# nào là câu hỏi NGOÀI PHẠM VI thật của sinh viên -> KHAC. Câu khớp từ khóa học vụ vẫn gán theo từ khóa.
CHUYEN_MUC_NGOAI_PHAM_VI = {"uit-linh-tinh", "uit-tam-su", "uit-cho-tro", "uit-viec-lam-them"}
# Chỉ giới hạn số câu của VHU (nguồn chiếm đa số); câu của UIT, HLU giữ hết.
TRUONG_GIOI_HAN = {"VHU"}


def tu_web():
    w = pd.read_csv(RAW / "web_ticket.csv", dtype=str, keep_default_na=False)
    kq = w.text.map(gan_nhan)
    w["label"] = [k[0] for k in kq]
    w["ghi_chu"] = [k[1] for k in kq]
    doi_song = w.chuyen_muc.isin(CHUYEN_MUC_NGOAI_PHAM_VI) & (w.ghi_chu == "không khớp từ khóa")
    w.loc[doi_song, ["label", "ghi_chu"]] = ["KHAC", ""]
    bi_loai = w[w.label.isna()]
    w = w[w.label.notna()].copy()
    so_gan = len(w)
    w["source"] = "web"
    w["nguon"] = w.url
    w["nhom"] = w.ma
    w["multi_intent"] = 0
    w["annotator"] = "tu_khoa"
    w.loc[doi_song[w.index], "annotator"] = "chuyen_muc"
    # Giới hạn số câu mỗi nhãn: chọn theo mã băm của id (ngẫu nhiên nhưng ỔN ĐỊNH — sửa nhãn vài câu
    # chỉ ảnh hưởng đúng các câu đó, không làm xáo trộn cả tập, nên tập test đã đóng băng vẫn giữ nguyên)
    w["_bam"] = w.ma.map(lambda m: hashlib.md5(f"{SEED}-{m}".encode()).hexdigest())
    gioi_han = w[w.truong.isin(TRUONG_GIOI_HAN)]
    gioi_han = gioi_han.sort_values("_bam").groupby("label", group_keys=False).head(TOI_DA_MOI_NHAN)
    w = pd.concat([gioi_han, w[~w.truong.isin(TRUONG_GIOI_HAN)]]).drop(columns="_bam").sort_values("ma")
    return w, bi_loai, so_gan


def main():
    d, (w, bi_loai, so_gan) = tu_docx(), tu_web()
    d = d[d.label.notna()]
    cot = ["id", "text", "label", "source", "multi_intent", "annotator", "faq_id", "nhom", "nguon"]
    d = d.assign(id=d.ma, faq_id="")
    w = w.assign(id=w.ma, faq_id="")
    tat_ca = pd.concat([d[cot], w[cot]], ignore_index=True)
    sai = set(tat_ca.label) - set(config.NHAN)
    assert not sai, sai
    tat_ca.to_csv(ROOT / "data" / "questions.csv", index=False)
    bi_loai[["ma", "chuyen_muc", "text", "ghi_chu"]].to_csv(RAW / "web_bi_loai.csv", index=False)

    anh_xa = (pd.read_csv(RAW / "docx_cau_hoi.csv", dtype=str, keep_default_na=False)
              .assign(nhan_moi=lambda x: x.nhan_goc.map(ANH_XA).fillna("(loại)"))
              .groupby(["tep", "nhan_goc", "nhan_moi"]).size().rename("so_cau").reset_index())
    anh_xa.to_csv(RAW / "bang_anh_xa_nhan.csv", index=False)

    print(pd.crosstab(tat_ca.label, tat_ca.source, margins=True, margins_name="Tổng"))
    print(f"\nWeb: gán được {so_gan} ticket, giữ {len(w)} sau khi giới hạn {TOI_DA_MOI_NHAN} ticket VHU/nhãn; "
          f"loại {len(bi_loai)} (lý do: "
          + ", ".join(f"{k} {v}" for k, v in bi_loai.ghi_chu.str.split(":").str[0].value_counts().items()) + ")")
    print(f"Đã lưu data/questions.csv ({len(tat_ca)} câu), data/raw/web_bi_loai.csv, data/raw/bang_anh_xa_nhan.csv")


if __name__ == "__main__":
    main()
