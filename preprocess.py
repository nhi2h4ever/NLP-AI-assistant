"""Tiền xử lý văn bản tiếng Việt — dùng CHUNG cho notebook huấn luyện và ứng dụng,
để lúc huấn luyện và lúc chạy thật xử lý giống hệt nhau."""
import re
import unicodedata

from underthesea import word_tokenize

# Từ điển teencode / viết tắt (áp dụng cho từng từ đứng riêng).
# "hp" cố ý KHÔNG có: có thể là "học phí" hoặc "học phần", để mô hình tự phân biệt theo ngữ cảnh.
TEENCODE = {
    "ko": "không", "k": "không", "kh": "không", "hok": "không", "hông": "không",
    "dc": "được", "đc": "được", "dk": "đăng ký", "đk": "đăng ký", "dky": "đăng ký", "đky": "đăng ký",
    "dkhp": "đăng ký học phần", "đkhp": "đăng ký học phần",
    "gv": "giảng viên", "gvhd": "giảng viên hướng dẫn", "sv": "sinh viên",
    "tkb": "thời khóa biểu", "tc": "tín chỉ", "hb": "học bổng", "ktx": "ký túc xá",
    "kltn": "khóa luận tốt nghiệp", "datn": "đồ án tốt nghiệp", "đatn": "đồ án tốt nghiệp",
    "ctđt": "chương trình đào tạo", "lm": "làm", "j": "gì", "z": "vậy", "ntn": "như thế nào",
    "bn": "bao nhiêu", "bh": "bao giờ", "mn": "mọi người", "e": "em",
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_SDT = re.compile(r"(?<!\d)(?:\+84|0)\d{9}(?!\d)")
_MSSV = re.compile(r"(?<![\w])(?:\d{8,10}|\d{2,3}[a-zA-Z]{1,2}\d{5,7})(?![\w])")  # 102210001, 161A080509
_URL = re.compile(r"https?://\S+|www\.\S+")
_KY_TU_LA = re.compile(r"[^\w\s]")  # dấu câu, emoji, ký hiệu


def an_danh(text: str) -> str:
    """Thay thông tin cá nhân bằng token. Dùng cả khi ghi nhật ký."""
    text = _EMAIL.sub("<email>", str(text))
    text = _SDT.sub("<sdt>", text)
    return _MSSV.sub("<mssv>", text)


def chuan_hoa(text: str) -> str:
    """Chuẩn hóa: Unicode NFC, chữ thường, ẩn danh, bỏ link/dấu câu/emoji, mở rộng teencode."""
    text = unicodedata.normalize("NFC", an_danh(text)).lower()
    text = _URL.sub(" ", text)
    text = _KY_TU_LA.sub(" ", text)
    return " ".join(TEENCODE.get(w, w) for w in text.split())


def tien_xu_ly(text: str, tach_tu: bool = True) -> str:
    """Chuẩn hóa rồi tách từ tiếng Việt: "đăng ký học phần" -> "đăng_ký học_phần"."""
    text = chuan_hoa(text)
    if tach_tu and text:
        return word_tokenize(text, format="text")
    return text


def bo_dau(text: str) -> str:
    """Bỏ dấu tiếng Việt — dùng để tăng cường dữ liệu (sinh viên hay gõ không dấu)."""
    text = unicodedata.normalize("NFD", str(text))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def khong_dau(text: str) -> bool:
    """True nếu câu có chữ cái nhưng không có dấu tiếng Việt nào."""
    text = str(text)
    return any(c.isalpha() for c in text) and bo_dau(text) == unicodedata.normalize("NFC", text)
