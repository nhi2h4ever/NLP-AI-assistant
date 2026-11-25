import numpy as np
import pandas as pd

import config
import training as T


def test_chia_tap_dong_bang_va_chi_cau_that(du_lieu_mau, tmp_path):
    df = du_lieu_mau.copy()
    df.loc[df.index[:10], "source"] = "team"
    train1, test1, _ = T.chia_tap(df, tmp_path)
    assert set(test1.source) <= config.NGUON_TEST
    assert not set(train1.id) & set(test1.id)
    train2, test2, thong_bao = T.chia_tap(df, tmp_path)
    assert "đóng băng" in thong_bao and set(test1.id) == set(test2.id)


def test_tang_cuong_chi_them_ban_khong_dau(du_lieu_mau):
    X, y = T.tap_huan_luyen(du_lieu_mau)
    assert len(X) == len(du_lieu_mau) + int(du_lieu_mau.co_dau.sum()) == len(y)
    X0, _ = T.tap_huan_luyen(du_lieu_mau, tang_cuong=False)
    assert len(X0) == len(du_lieu_mau)


def test_danh_gia_cheo_xac_suat(du_lieu_mau):
    r = T.danh_gia_cheo(du_lieu_mau, "Linear SVM", xac_suat=True)
    assert 0 <= r["f1_macro"] <= 1
    assert np.allclose(r["oof"].sum(1), 1)


def test_chon_nguong():
    lop = np.array(["HOC_PHI", "KHAC", "LICH_THI"])
    oof = np.array([[0.9, 0.05, 0.05], [0.6, 0.1, 0.3], [0.3, 0.1, 0.6], [0.1, 0.8, 0.1]])
    y = ["HOC_PHI", "LICH_THI", "LICH_THI", "KHAC"]
    tau, bang, _ = T.chon_nguong(oof, lop, y, muc_tieu=0.9)
    # τ = 0.6 thì câu thứ 2 (dự đoán sai, tin cậy 0.6) vẫn được trả lời; cần τ > 0.6
    assert tau == 0.65
    assert bang.set_index("tau").loc[0.65, "precision"] == 1.0


def test_chon_mo_hinh_cao_nhat():
    bang = pd.DataFrame({"Mô hình": T.MO_HINH, "Macro-F1 (CV)": [0.80, 0.85, 0.86]})
    ten, ly_do = T.chon_mo_hinh(bang)
    assert ten == "Linear SVM" and "Logistic Regression" in ly_do
    bang.loc[1, "Macro-F1 (CV)"] = 0.90
    assert T.chon_mo_hinh(bang)[0] == "Logistic Regression"


def test_kiem_dinh_cheo_giu_bien_the_cung_nhom_trong_mot_fold(du_lieu_mau):
    df = du_lieu_mau.copy()
    df["nhom"] = [f"g{i // 3}" for i in range(len(df))]  # mỗi nhóm 3 câu
    for tr, va in T.chia_fold(df, so_fold=5, seed=1):
        assert not set(df.nhom.iloc[tr]) & set(df.nhom.iloc[va])


def test_doc_du_lieu_nhom_trong_thi_moi_cau_mot_nhom(tmp_path):
    pd.DataFrame({"id": ["a", "b"], "text": ["học phí bao nhiêu", "lịch thi khi nào"],
                  "label": ["HOC_PHI", "LICH_THI"], "source": ["form", "form"]}).to_csv(tmp_path / "q.csv", index=False)
    df = T.doc_du_lieu(tmp_path / "q.csv")
    assert list(df.nhom) == ["a", "b"]


def test_kappa_bo_dong_chua_gan_va_so_voi_nhan_tu_dong(tmp_path):
    pd.DataFrame({"id": ["a", "b", "c", "d"], "text": ["1", "2", "3", "4"],
                  "label_a": ["HOC_PHI", "LICH_THI", "KHAC", ""],
                  "label_b": ["HOC_PHI", "LICH_THI", "HOC_PHI", ""]}).to_csv(tmp_path / "k.csv", index=False)
    kappa, bat_dong = T.tinh_kappa(tmp_path / "k.csv")
    assert list(bat_dong.id) == ["c"] and 0 < kappa < 1
    df = pd.DataFrame({"id": ["a", "b"], "label": ["HOC_PHI", "LICH_HOC"]})
    ti_le, khong_khop = T.do_khop_nhan_tu_dong(tmp_path / "k.csv", df)
    assert ti_le == 0.5 and list(khong_khop.id) == ["b"]
