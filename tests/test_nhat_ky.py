import pytest

from nhat_ky import NhatKyCSV, du_lieu_huan_luyen_lai, tao_dong, tao_nhat_ky
from router import KetQua


def _kq(**kw):
    mac_dinh = dict(hanh_dong="chuyen_tiep", chu_de="HOC_PHI", do_tin_cay=0.42, phong_ban="Phòng Tài chính")
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
