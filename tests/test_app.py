"""Kiểm thử giao diện bằng Streamlit AppTest (chạy app không cần trình duyệt)."""
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from conftest import MAU_FAQ, ROOT
from nhat_ky import NhatKyCSV, tao_dong
from router import KetQua


@pytest.fixture(autouse=True)
def cau_hinh_test(monkeypatch, thu_muc_model):
    monkeypatch.setattr(config, "MODEL_DIR", thu_muc_model)
    monkeypatch.setattr(config, "FAQ_PATH", MAU_FAQ)
    monkeypatch.setattr(config, "TRA_LOI_TU_DONG", False)
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def _app(tep, tmp_path, **secrets):
    at = AppTest.from_file(str(ROOT / tep), default_timeout=180)
    at.secrets["log_backend"] = "csv"
    at.secrets["log_csv_path"] = str(tmp_path / "log.csv")
    for k, v in secrets.items():
        at.secrets[k] = v
    return at.run()


def _doc_log(tmp_path):
    return pd.read_csv(tmp_path / "log.csv", dtype=str, keep_default_na=False)


def test_gd1_phan_loai_chuyen_phong_ban_va_danh_gia(tmp_path):
    at = _app("app.py", tmp_path)
    assert not at.exception
    at.text_area[0].input("Khi nào có lịch thi lại môn Giải tích 1 ạ?")
    at.button[0].click().run()
    assert not at.exception
    pb = config.phong_ban("LICH_THI")
    assert any(f"Chuyển đến: {pb}" in m.value for m in at.markdown)
    assert any(config.lien_he(pb) in c.value for c in at.caption), "phải hiện phòng, điện thoại, website"
    assert any("3 ngày làm việc" in c.value and config.QUY_TRINH in c.value for c in at.caption), "phải hiện thời hạn theo QT_11_CTSV"
    assert at.info and not at.success
    log = _doc_log(tmp_path)
    assert len(log) == 1 and log.hanh_dong[0] == "chuyen_tiep" and log.chu_de[0] == "LICH_THI"

    [b for b in at.button if b.label.startswith("👍")][0].click().run()
    assert _doc_log(tmp_path).danh_gia[0] == "huu_ich"
    assert any(m.value.startswith("Lưu lại mã yêu cầu") for m in at.caption), "phải nhắc sinh viên lưu mã yêu cầu"


def test_gd2_tra_loi_tu_dong(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TRA_LOI_TU_DONG", True)
    at = _app("app.py", tmp_path)
    # Câu có trong dữ liệu mẫu: bài test kiểm tra luồng hiển thị, không kiểm tra độ chính xác của model
    at.text_area[0].input("Em bị ốm không đi thi được thì xin hoãn thi thế nào ạ?")
    at.button[0].click().run()
    assert not at.exception
    assert at.success, "giai đoạn 2 phải hiển thị câu trả lời từ kho FAQ"
    assert _doc_log(tmp_path).hanh_dong[0] == "tra_loi"


def test_dau_vao_khong_hop_le_khong_ghi_nhat_ky(tmp_path):
    at = _app("app.py", tmp_path)
    at.text_area[0].input("???")
    at.button[0].click().run()
    assert at.warning and not (tmp_path / "log.csv").exists()


def test_quan_tri_can_mat_khau(tmp_path):
    nk = NhatKyCSV(tmp_path / "log.csv")
    for ma, hanh_dong, chu_de, pb in [("a1", "chuyen_tiep", "HOC_PHI", "Phòng Kế hoạch - Tài chính"),
                                      ("a2", "chuyen_tiep", "KHAC", "Phòng Công tác sinh viên"),
                                      ("a3", "can_phan_loai", "QUY_CHE", "Phòng Công tác sinh viên")]:
        nk.ghi(tao_dong(ma, f"câu hỏi {ma}", KetQua(hanh_dong=hanh_dong, chu_de=chu_de, do_tin_cay=0.5,
                                                     phong_ban=pb), "test"))
    at = _app("pages/1_Quan_tri.py", tmp_path, admin_password="mk-test")
    assert not at.metric
    at.text_input[0].input("sai")
    at.button[0].click().run()
    assert at.error and not at.metric
    at.text_input[0].input("mk-test")
    at.button[0].click().run()
    assert not at.exception
    chi_so = {m.label: m.value for m in at.metric}
    assert chi_so["Tổng số câu hỏi"] == "3"
    assert chi_so["Phân loại tự động"] == "67%"
    assert chi_so["Cần phân loại thủ công"] == "1"


def test_quan_tri_chua_cau_hinh_mat_khau(tmp_path):
    at = _app("pages/1_Quan_tri.py", tmp_path)
    assert at.error and "admin_password" in at.error[0].value


def test_quan_tri_quy_doi_ten_phong_ban_cu(tmp_path):
    """Nhật ký cũ ghi "Phòng Khảo thí": trang Quản trị gộp về tên phòng ban hiện tại."""
    nk = NhatKyCSV(tmp_path / "log.csv")
    for ma, pb in [("b1", "Phòng Khảo thí"), ("b2", "Phòng Đào tạo và Bảo đảm chất lượng"),
                   ("b3", "Phòng Công tác Sinh viên")]:
        nk.ghi(tao_dong(ma, f"câu hỏi {ma}", KetQua(hanh_dong="chuyen_tiep", chu_de="LICH_THI", do_tin_cay=0.9,
                                                     phong_ban=pb), "test"))
    at = _app("pages/1_Quan_tri.py", tmp_path, admin_password="mk")
    at.text_input[0].input("mk")
    at.button[0].click().run()
    assert not at.exception
    assert set(at.multiselect[0].options) == {"Phòng Đào tạo và Bảo đảm chất lượng", "Phòng Công tác sinh viên"}


def _log_tra_cuu(tmp_path):
    nk = NhatKyCSV(tmp_path / "log.csv")
    nk.ghi(tao_dong("0a1b2c3d", "Hạn đóng học phí kỳ này?", KetQua(hanh_dong="chuyen_tiep", chu_de="HOC_PHI",
                                                                    do_tin_cay=0.9, phong_ban="Phòng Kế hoạch - Tài chính"), "test"))
    nk.ghi(tao_dong("1a2b3c4d", "Gần trường có quán cơm nào ngon?", KetQua(hanh_dong="chuyen_tiep", chu_de="KHAC",
                                                                          do_tin_cay=0.9, phong_ban="Phòng Công tác Sinh viên"), "test"))
    nk.cap_nhat("0a1b2c3d", phan_hoi="Hạn đóng học phí là ngày 15/12.", thoi_gian_phan_hoi="2026-11-23 10:00:00")


@pytest.mark.parametrize("ma, mong_doi", [
    ("0A1B2C3D", "success"),   # đã có phản hồi (mã nhập chữ hoa vẫn tìm được)
    ("1a2b3c4d", "info"),      # chưa có phản hồi -> báo đang xử lý + thời hạn
    ("ffffffff", "error"),     # không có mã này
    ("abc", "warning"),        # sai định dạng
])
def test_tra_cuu_phan_hoi(tmp_path, ma, mong_doi):
    _log_tra_cuu(tmp_path)
    at = _app("pages/0_Tra_cuu_phan_hoi.py", tmp_path)
    assert not at.exception
    at.text_input[0].input(ma)
    at.button[0].click().run()
    assert not at.exception
    assert getattr(at, mong_doi), f"phải hiện {mong_doi}"
    if mong_doi == "success":
        assert "15/12" in at.success[0].value
    if mong_doi == "info":
        assert config.THOI_HAN_PHAN_HOI_KHAC in at.info[0].value
        assert any("Phòng Công tác sinh viên" in m.value for m in at.markdown), "tên phòng ban cũ phải được quy đổi"


def test_tra_cuu_tu_link_co_ma(tmp_path):
    _log_tra_cuu(tmp_path)
    at = AppTest.from_file(str(ROOT / "pages/0_Tra_cuu_phan_hoi.py"), default_timeout=180)
    at.secrets["log_backend"] = "csv"
    at.secrets["log_csv_path"] = str(tmp_path / "log.csv")
    at.query_params["ma"] = "0a1b2c3d"
    at.run()
    assert not at.exception and at.success and "15/12" in at.success[0].value
