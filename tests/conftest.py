import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import training as T  # noqa: E402
from router import Router, doc_faq  # noqa: E402

MAU_CAU_HOI = ROOT / "data" / "sample" / "questions_sample.csv"
MAU_FAQ = ROOT / "data" / "sample" / "faq_sample.csv"


@pytest.fixture(scope="session")
def du_lieu_mau():
    df, _, _ = T.lam_sach(T.doc_du_lieu(MAU_CAU_HOI))
    return T.them_cot_xu_ly(df)


@pytest.fixture(scope="session")
def model(du_lieu_mau):
    return T.huan_luyen_cuoi(du_lieu_mau, "Logistic Regression", {"clf__C": 10})


@pytest.fixture(scope="session")
def faq():
    return doc_faq(MAU_FAQ)


@pytest.fixture
def router(model, faq):
    return Router(model, faq, nguong_tin_cay=0.0, nguong_tuong_dong=0.0, phien_ban="test")


@pytest.fixture(scope="session")
def thu_muc_model(model, tmp_path_factory):
    thu_muc = tmp_path_factory.mktemp("model_test")
    T.luu_model(model, thu_muc, {"phien_ban": "test", "nguong_tin_cay": 0.3, "nguong_tuong_dong": 0.0})
    return thu_muc
