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

# Mã nhãn -> (tên hiển thị, phòng ban mặc định khi chuyển tiếp).
# Thay tên phòng ban cho đúng cơ cấu của trường.
NHAN = {
    "LICH_HOC": ("Lịch học & đăng ký học phần", "Phòng Đào tạo"),
    "LICH_THI": ("Lịch thi & điểm thi", "Phòng Khảo thí"),
    "HOC_PHI": ("Học phí", "Phòng Tài chính"),
    # Gồm cả MIỄN GIẢM học phí và trợ cấp — do Phòng Công tác Sinh viên xét, không phải Phòng Tài chính.
    "HOC_BONG": ("Học bổng & miễn giảm học phí", "Phòng Công tác Sinh viên"),
    "DO_AN": ("Đồ án & khóa luận", "Văn phòng Khoa"),
    "QUY_CHE": ("Quy chế & tốt nghiệp", "Phòng Đào tạo"),
    "KHAC": ("Khác (ngoài phạm vi)", "Trợ lý khoa"),
}
NHAN_KHAC = "KHAC"

# Câu hỏi mô hình CHƯA CHẮC CHẮN (độ tin cậy < τ) được chuyển về đây để phân loại thủ công,
# thay vì đoán phòng ban và có thể chuyển nhầm.
PHONG_BAN_XEM_LAI = "Trợ lý khoa"


def phong_ban(nhan: str) -> str:
    """Phòng ban phụ trách một chủ đề."""
    return NHAN[nhan][1]

# Nguồn dữ liệu được phép đưa vào tập test (chỉ câu hỏi thật).
# "team" (nhóm tự viết), "faq" (câu hỏi lấy từ kho FAQ) và "log" (nhật ký) không vào tập test gốc.
NGUON_TEST = {"form", "facebook", "staff", "demo"}
