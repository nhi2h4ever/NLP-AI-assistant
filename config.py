"""Cấu hình chung của hệ thống Student FAQ Router."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MODEL_ROOT = ROOT / "models"
REPORT_ROOT = ROOT / "reports"
LOG_DIR = ROOT / "logs"

# Chế độ demo: chạy với dữ liệu MẪU trong data/sample và model "demo".
# Bật bằng biến môi trường FAQ_ROUTER_DEMO=1. Kết quả demo KHÔNG dùng cho báo cáo.
DEMO = os.environ.get("FAQ_ROUTER_DEMO") == "1"

# Phiên bản model ứng dụng đang dùng (thư mục models/<phiên bản>/).
# Sau khi huấn luyện lại và quyết định thay model, sửa giá trị này (ví dụ "v2").
MODEL_VERSION = "demo" if DEMO else "v1"
MODEL_DIR = MODEL_ROOT / MODEL_VERSION

# GIAI ĐOẠN của hệ thống:
#   False -> giai đoạn 1: chỉ PHÂN LOẠI câu hỏi và CHUYỂN về đúng phòng ban (không cần kho FAQ).
#   True  -> giai đoạn 2: thêm TRẢ LỜI TỰ ĐỘNG bằng kho FAQ (cần file FAQ_PATH).
TRA_LOI_TU_DONG = False

# Kho câu trả lời (chỉ dùng khi TRA_LOI_TU_DONG = True)
FAQ_PATH = (DATA_DIR / "sample" / "faq_sample.csv") if DEMO else (DATA_DIR / "faq.csv")

# Độ dài tối đa của một câu hỏi (ký tự)
MAX_LEN = 500

# Phòng ban của Trường Đại học Bách khoa – Đại học Đà Nẵng (theo website dut.udn.vn).
# Tên phòng ban -> thông tin liên hệ hiển thị cho sinh viên khi câu hỏi được chuyển đến.
PHONG_BAN = {
    "Phòng Đào tạo": {"phong": "A123", "dien_thoai": "0236.3842145", "web": "http://dut.udn.vn/Phong/DaoTao"},
    "Phòng Khảo thí và Đảm bảo chất lượng giáo dục": {
        "phong": "S03", "dien_thoai": "0236.3737931", "web": "http://dut.udn.vn/Phong/QualityAssurance"},
    "Phòng Kế hoạch - Tài chính": {"phong": "A120", "dien_thoai": "0236.3841660", "web": "http://dut.udn.vn/Phong/TaiChinh"},
    "Phòng Công tác sinh viên": {"phong": "A108", "dien_thoai": "0236.3738268", "web": "http://dut.udn.vn/Phong/Sinhvien"},
    # Thuộc từng khoa — nhóm điền phòng/điện thoại của khoa mình.
    "Văn phòng Khoa": {"phong": "", "dien_thoai": "", "web": ""},
}

# Theo Quy trình QT_11_CTSV "Tiếp nhận và giải quyết thắc mắc cho sinh viên":
# Phòng Công tác sinh viên CHỦ TRÌ tiếp nhận, tổng hợp, phân loại câu hỏi và chuyển đến đơn vị chức năng;
# các Khoa, Phòng ban PHỐI HỢP trả lời. Hệ thống tự động hóa bước 2 (tổng hợp, phân loại).
DON_VI_CHU_TRI = "Phòng Công tác sinh viên"
QUY_TRINH = "QT_11_CTSV"

# Mã nhãn -> (tên hiển thị, phòng ban phụ trách — phải là một khóa trong PHONG_BAN).
NHAN = {
    "LICH_HOC": ("Lịch học & đăng ký học phần", "Phòng Đào tạo"),
    "LICH_THI": ("Lịch thi & điểm thi", "Phòng Khảo thí và Đảm bảo chất lượng giáo dục"),
    "HOC_PHI": ("Học phí", "Phòng Kế hoạch - Tài chính"),
    # Gồm cả MIỄN GIẢM học phí và trợ cấp — do Phòng Công tác sinh viên xét, không phải Phòng Kế hoạch - Tài chính.
    "HOC_BONG": ("Học bổng & miễn giảm học phí", "Phòng Công tác sinh viên"),
    "DO_AN": ("Đồ án & khóa luận", "Văn phòng Khoa"),
    "QUY_CHE": ("Quy chế & tốt nghiệp", "Phòng Đào tạo"),
    # QT_11_CTSV: thắc mắc không liên quan thủ tục hành chính / học tập do chuyên viên P.CTSV tư vấn, hướng dẫn.
    "KHAC": ("Khác (ngoài phạm vi)", DON_VI_CHU_TRI),
}
NHAN_KHAC = "KHAC"

# Câu hỏi mô hình CHƯA CHẮC CHẮN (độ tin cậy < τ) được chuyển về đơn vị chủ trì để chuyên viên
# phân loại thủ công và chuyển tiếp (đúng bước 2 của QT_11_CTSV), thay vì đoán và có thể chuyển nhầm.
PHONG_BAN_XEM_LAI = DON_VI_CHU_TRI

# Thời hạn phản hồi hiển thị cho sinh viên (QT_11_CTSV, bước 3): câu hỏi gửi qua trang trực tuyến
# được phản hồi trong 3 ngày làm việc; thắc mắc không liên quan thủ tục hành chính / học tập: 1–2 ngày làm việc.
THOI_HAN_PHAN_HOI = "trong 3 ngày làm việc"
THOI_HAN_PHAN_HOI_KHAC = "trong 1–2 ngày làm việc"

_thieu = ({pb for _, pb in NHAN.values()} | {PHONG_BAN_XEM_LAI}) - set(PHONG_BAN)
if _thieu:
    raise ValueError(f"Phòng ban chưa khai báo trong PHONG_BAN: {_thieu}")


def phong_ban(nhan: str) -> str:
    """Phòng ban phụ trách một chủ đề."""
    return NHAN[nhan][1]


def lien_he(ten_phong_ban: str) -> str:
    """Chuỗi liên hệ của phòng ban, ví dụ 'Phòng A123 · ĐT 0236.3842145 · http://...'.
    Rỗng nếu chưa có thông tin."""
    tt = PHONG_BAN.get(ten_phong_ban, {})
    phan = [f"Phòng {tt['phong']}" if tt.get("phong") else "",
            f"ĐT {tt['dien_thoai']}" if tt.get("dien_thoai") else "", tt.get("web", "")]
    return " · ".join(p for p in phan if p)

# Nguồn dữ liệu được phép đưa vào tập test (chỉ câu hỏi thật).
# "team" (nhóm tự viết), "faq" (câu hỏi lấy từ kho FAQ) và "log" (nhật ký) không vào tập test gốc.
NGUON_TEST = {"form", "facebook", "staff", "demo"}
