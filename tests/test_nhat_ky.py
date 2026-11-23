import pytest

import pandas as pd

from nhat_ky import COT, NhatKyCSV, ban_ghi_phan_hoi, chuan_ma, du_lieu_huan_luyen_lai, tao_dong, tao_nhat_ky, tim_theo_ma
from router import KetQua


def _kq(**kw):
    mac_dinh = dict(hanh_dong="chuyen_tiep", chu_de="HOC_PHI", do_tin_cay=0.42, phong_ban="Phòng Kế hoạch - Tài chính")
    return KetQua(**{**mac_dinh, **kw})


def test_tao_dong_an_danh():
    dong = tao_dong("abc", "Em MSSV 21520001 hỏi học phí", _kq(), "v1")
    assert "21520001" not in dong["cau_hoi"] and "<mssv>" in dong["cau_hoi"]
    assert dong["phien_ban_model"] == "v1" and dong["danh_gia"] == ""


def test_csv_ghi_doc_cap_nhat(tmp_path):
    nk = NhatKyCSV(tmp_path / "log.csv")
    assert nk.doc().empty
    nk.ghi(tao_dong("a1", "Hạn đóng học phí?", _kq(), "v1"))
    nk.ghi(tao_dong("a2", "quán cơm nào ngon", _kq(chu_de="KHAC"), "v1"))
    nk.cap_nhat("a1", danh_gia="huu_ich")
    nk.cap_nhat_nhieu({"a1": {"nhan_dung": "HOC_PHI"}, "a2": {"nhan_dung": "KHAC"}})
    df = nk.doc()
    assert list(df.id) == ["a1", "a2"]
    assert df.set_index("id").loc["a1", "danh_gia"] == "huu_ich"
    assert df.do_tin_cay.dtype.kind == "f"

    lai = du_lieu_huan_luyen_lai(df)
    assert list(lai.id) == ["LOG_a1", "LOG_a2"] and set(lai.source) == {"log"}
    assert list(lai.label) == ["HOC_PHI", "KHAC"]


def test_backend_khong_hop_le():
    with pytest.raises(ValueError, match="log_backend"):
        tao_nhat_ky({"log_backend": "excel"})


def test_nang_cap_nhat_ky_cu_thieu_cot_phan_hoi(tmp_path):
    """Nhật ký tạo trước khi có cột phản hồi: ghi tiếp và cập nhật vẫn đúng cột, dữ liệu cũ giữ nguyên."""
    cu = tao_dong("aaaa1111", "Hạn đóng học phí?", _kq(), "v1")
    pd.DataFrame([{k: cu[k] for k in COT[:12]}]).to_csv(tmp_path / "log.csv", index=False)
    nk = NhatKyCSV(tmp_path / "log.csv")
    nk.ghi(tao_dong("bbbb2222", "lịch thi lại", _kq(chu_de="LICH_THI"), "v1"))
    nk.cap_nhat("aaaa1111", phan_hoi="Hạn đóng là 15/12.", thoi_gian_phan_hoi="2026-11-23 10:00:00")
    df = nk.doc()
    assert list(pd.read_csv(tmp_path / "log.csv").columns) == COT
    assert list(df.id) == ["aaaa1111", "bbbb2222"] and df.loc[0, "chu_de"] == "HOC_PHI"
    assert df.loc[0, "phan_hoi"] == "Hạn đóng là 15/12." and df.loc[1, "phan_hoi"] == ""


def test_tim_theo_ma_yeu_cau(tmp_path):
    nk = NhatKyCSV(tmp_path / "log.csv")
    nk.ghi(tao_dong("0a1b2c3d", "Hạn đóng học phí?", _kq(), "v1"))
    df = nk.doc()
    assert tim_theo_ma(df, "  0A1B2C3D ")["cau_hoi"] == "Hạn đóng học phí?"
    assert tim_theo_ma(df, "ffffffff") is None
    assert chuan_ma("abc") is None and chuan_ma("0a1b2c3d' or 1=1") is None


def test_ban_ghi_phan_hoi_chi_lay_cau_thay_doi():
    df = pd.DataFrame({"id": ["a", "b", "c"], "phan_hoi": ["", "Đã có", "Cũ"]})
    moi = pd.DataFrame({"id": ["a", "b", "c"], "phan_hoi": ["  Hạn đóng 15/12. ", "Đã có", None]})
    kq = ban_ghi_phan_hoi(moi, df, "2026-11-23 10:00:00")
    assert kq == {"a": {"phan_hoi": "Hạn đóng 15/12.", "thoi_gian_phan_hoi": "2026-11-23 10:00:00"},
                  "c": {"phan_hoi": "", "thoi_gian_phan_hoi": ""}}
