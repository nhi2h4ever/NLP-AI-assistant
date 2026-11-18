import time

import pytest

import config
from router import CAN_PHAN_LOAI, CHUYEN_TIEP, LOI_DAU_VAO, TRA_LOI, Router, doc_faq, kiem_tra_dau_vao


@pytest.fixture
def router_gd1(model):
    """Giai đoạn 1: chỉ phân loại và chuyển phòng ban."""
    return Router(model, nguong_tin_cay=0.0, phien_ban="test")


# ---------------- Đầu vào
@pytest.mark.parametrize("cau_hoi", ["", "   ", "???", "😀😀", "a" * (config.MAX_LEN + 1)])
def test_dau_vao_khong_hop_le(router_gd1, cau_hoi):
    assert kiem_tra_dau_vao(cau_hoi)
    kq = router_gd1.xu_ly(cau_hoi)
    assert kq.hanh_dong == LOI_DAU_VAO and kq.chu_de == ""


def test_dau_vao_hop_le():
    assert kiem_tra_dau_vao("Lịch thi lại khi nào ạ?") is None


# ---------------- Giai đoạn 1: phân loại và chuyển phòng ban
@pytest.mark.parametrize("cau_hoi, nhan", [
    ("Khi nào có lịch thi lại môn Giải tích 1 ạ?", "LICH_THI"),
    ("Hạn đóng học phí học kỳ này là ngày mấy ạ?", "HOC_PHI"),
    ("Học bổng khuyến khích học tập xét theo điểm trung bình bao nhiêu?", "HOC_BONG"),
    ("Em muốn đổi giảng viên hướng dẫn đồ án có được không ạ", "DO_AN"),
])
def test_gd1_chuyen_dung_phong_ban(router_gd1, cau_hoi, nhan):
    kq = router_gd1.xu_ly(cau_hoi)
    assert kq.chu_de == nhan and kq.hanh_dong == CHUYEN_TIEP
    assert kq.phong_ban == config.phong_ban(nhan) and kq.phong_ban in kq.thong_bao
    assert kq.cau_tra_loi == ""


def test_gd1_khac_chuyen_pctsv(router_gd1):
    """QT_11_CTSV: thắc mắc ngoài thủ tục hành chính / học tập do chuyên viên P.CTSV tư vấn trong 1–2 ngày."""
    kq = router_gd1.xu_ly("Gần trường có quán cơm nào ngon không mọi người")
    assert kq.chu_de == config.NHAN_KHAC and kq.hanh_dong == CHUYEN_TIEP
    assert kq.phong_ban == config.DON_VI_CHU_TRI == "Phòng Công tác sinh viên"
    assert kq.thoi_han == config.THOI_HAN_PHAN_HOI_KHAC


def test_do_tin_cay_thap_thi_pctsv_phan_loai_thu_cong(router_gd1):
    """QT_11_CTSV bước 2: P.CTSV tổng hợp, phân loại khi hệ thống chưa chắc chắn."""
    router_gd1.nguong_tin_cay = 1.01
    kq = router_gd1.xu_ly("Hạn đóng học phí học kỳ này là ngày mấy ạ?")
    assert kq.hanh_dong == CAN_PHAN_LOAI
    assert kq.phong_ban == config.DON_VI_CHU_TRI
    assert kq.thoi_han == config.THOI_HAN_PHAN_HOI


def test_chuyen_phong_ban_co_thoi_han_3_ngay(router_gd1):
    kq = router_gd1.xu_ly("Khi nào có lịch thi lại môn Giải tích 1 ạ?")
    assert kq.hanh_dong == CHUYEN_TIEP and kq.thoi_han == "trong 3 ngày làm việc"


def test_top3_giam_dan(router_gd1):
    kq = router_gd1.xu_ly("Khi nào có lịch thi lại môn Giải tích 1?")
    xac_suat = [p for _, p in kq.top3]
    assert len(kq.top3) == 3 and xac_suat == sorted(xac_suat, reverse=True)
    assert kq.top3[0] == (kq.chu_de, kq.do_tin_cay)


def test_thoi_gian_phan_hoi_duoi_1_giay(router_gd1):
    t0 = time.perf_counter()
    for _ in range(20):
        router_gd1.xu_ly("hp ki nay dong tre dc ko ad")
    assert (time.perf_counter() - t0) / 20 < 1.0


# ---------------- Giai đoạn 2: trả lời tự động bằng kho FAQ
def test_gd2_tra_loi_lay_faq_cung_chu_de(router, faq):
    kq = router.xu_ly("Xin hoãn thi như thế nào ạ?")
    assert kq.hanh_dong == TRA_LOI
    dong = faq.set_index("faq_id").loc[kq.faq_id]
    assert dong.label == kq.chu_de
    assert kq.cau_tra_loi == dong.answer and kq.phong_ban == dong.department


def test_gd2_khong_co_faq_du_giong_thi_chuyen_phong_ban(router):
    router.nguong_tuong_dong = 1.01
    kq = router.xu_ly("Xin hoãn thi như thế nào ạ?")
    assert kq.hanh_dong == CHUYEN_TIEP and "Chưa có câu trả lời sẵn" in kq.thong_bao
    assert kq.phong_ban == config.phong_ban(kq.chu_de)


def test_gd2_can_nguong_tuong_dong(model, faq):
    with pytest.raises(ValueError, match="ngưỡng tương đồng"):
        Router(model, faq, nguong_tin_cay=0.5)


# ---------------- Tải model / FAQ
def test_thieu_model_bao_loi_ro_rang(tmp_path):
    with pytest.raises(FileNotFoundError, match="Chưa có model"):
        Router.tu_thu_muc(tmp_path)


def test_tai_tu_thu_muc_gd1_va_gd2(thu_muc_model, faq, tmp_path):
    r1 = Router.tu_thu_muc(thu_muc_model)
    assert not r1.tra_loi_tu_dong and r1.nguong_tin_cay == 0.3 and r1.phien_ban == "test"
    faq.to_csv(tmp_path / "faq.csv", index=False)
    assert Router.tu_thu_muc(thu_muc_model, tmp_path / "faq.csv").tra_loi_tu_dong


def test_faq_nhan_sai_bao_loi(faq, tmp_path):
    sai = faq.copy()
    sai.loc[0, "label"] = "LICH_AN"
    sai.to_csv(tmp_path / "faq.csv", index=False)
    with pytest.raises(ValueError, match="nhãn không hợp lệ"):
        doc_faq(tmp_path / "faq.csv")
