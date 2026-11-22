import unicodedata

from preprocess import an_danh, bo_dau, chuan_hoa, khong_dau, tien_xu_ly


def test_an_danh_thay_thong_tin_ca_nhan():
    kq = an_danh("Em MSSV 21520001, sđt 0912345678, mail sv.a@gmail.com hỏi học phí")
    assert "<mssv>" in kq and "<sdt>" in kq and "<email>" in kq
    assert "21520001" not in kq and "0912345678" not in kq and "gmail" not in kq


def test_an_danh_mssv_co_chu_va_khong_dong_cham_ma_lop():
    kq = an_danh("161A080509 đã đóng học phí, lớp 20TCLC_DT1, môn IT004.E22.1, năm 2016-2017")
    assert kq.startswith("<mssv>") and "20TCLC_DT1" in kq and "IT004.E22.1" in kq and "2016-2017" in kq


def test_chuan_hoa_unicode_nfc():
    to_hop = unicodedata.normalize("NFD", "học phí")
    assert chuan_hoa(to_hop) == "học phí"


def test_chuan_hoa_teencode_giu_nguyen_hp():
    assert chuan_hoa("ko dc dk hp") == "không được đăng ký hp"


def test_chuan_hoa_bo_dau_cau_emoji_link():
    assert chuan_hoa("Lịch thi??? 😀 https://example.com/abc") == "lịch thi"


def test_tien_xu_ly_tach_tu():
    assert "đăng_ký" in tien_xu_ly("Em muốn đăng ký học phần")
    assert "_" not in tien_xu_ly("Em muốn đăng ký học phần", tach_tu=False)


def test_bo_dau_va_khong_dau():
    assert bo_dau("Đăng ký học phần") == "Dang ky hoc phan"
    assert khong_dau("lich thi lai khi nao")
    assert not khong_dau("lịch thi")
    assert not khong_dau("???")
