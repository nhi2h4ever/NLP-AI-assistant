"""Chạy các kịch bản kiểm thử hệ thống (Step 3 – System testing) với model đang dùng.
Chạy: python scripts/kiem_thu_kich_ban.py   (thêm FAQ_ROUTER_DEMO=1 để chạy với model demo)
Kết quả lưu ở reports/<MODEL_VERSION>/kiem_thu_kich_ban.csv để đưa vào báo cáo."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from nhat_ky import tao_dong  # noqa: E402
from router import CAN_PHAN_LOAI, LOI_DAU_VAO, Router  # noqa: E402

XEM_LAI = config.PHONG_BAN_XEM_LAI


def den(nhan):
    """Kiểm tra: đúng chủ đề `nhan` VÀ được chuyển đến phòng ban phụ trách chủ đề đó."""
    return lambda k: k.chu_de == nhan and k.hanh_dong != CAN_PHAN_LOAI and k.phong_ban == config.phong_ban(nhan)

DOAN_DAI = ("Dạ em chào thầy cô ạ. Em đang làm đồ án tốt nghiệp nhưng giảng viên hướng dẫn của em đi công tác "
            "dài ngày nên em không liên lạc được. Em muốn hỏi là em có thể đổi sang giảng viên khác hướng dẫn "
            "được không và thủ tục như thế nào ạ? Em cảm ơn ạ.")

KICH_BAN = [
    ("Câu chuẩn có dấu", "Khi nào có lịch thi lại môn Giải tích 1?",
     f"LICH_THI → {config.phong_ban('LICH_THI')}", den("LICH_THI")),
    ("Không dấu", "khi nao co lich thi lai mon giai tich 1",
     f"LICH_THI → {config.phong_ban('LICH_THI')}", den("LICH_THI")),
    ("Teencode, viết tắt", "hp ki nay dong tre dc ko ad",
     f"HOC_PHI → {config.phong_ban('HOC_PHI')}", den("HOC_PHI")),
    ("Miễn giảm học phí (không phải HOC_PHI)", "Em là con thương binh thì xin miễn giảm học phí thế nào ạ?",
     f"HOC_BONG → {config.phong_ban('HOC_BONG')}", den("HOC_BONG")),
    ("Câu dài, nhiều câu", DOAN_DAI,
     f"DO_AN → {config.phong_ban('DO_AN')}", den("DO_AN")),
    ("Câu có hai ý", "Học phí bao nhiêu và khi nào thi?",
     "HOC_PHI hoặc LICH_THI, hoặc chuyển P.CTSV nếu chưa chắc",
     lambda k: k.chu_de in {"HOC_PHI", "LICH_THI"} or k.hanh_dong == CAN_PHAN_LOAI),
    ("Ngoài phạm vi", "Gần trường có quán cơm nào ngon?", f"KHAC → {XEM_LAI}",
     lambda k: k.chu_de == "KHAC" and k.phong_ban == XEM_LAI),
    ("Học vụ chưa hỗ trợ", "Làm lại thẻ sinh viên ở đâu?", f"KHAC → {XEM_LAI}",
     lambda k: k.chu_de == "KHAC" and k.phong_ban == XEM_LAI),
    ("Tiếng Anh", "When is the retake exam?", f"Không chuyển nhầm phòng ban (→ {XEM_LAI})",
     lambda k: k.phong_ban == XEM_LAI),
    ("Input rỗng / ký tự lạ", "???", "Thông báo lỗi đầu vào",
     lambda k: k.hanh_dong == LOI_DAU_VAO),
    ("Input rất dài", "a" * 5000, "Báo vượt giới hạn",
     lambda k: k.hanh_dong == LOI_DAU_VAO),
]


def main():
    router = Router.tu_thu_muc(config.MODEL_DIR, config.FAQ_PATH if config.TRA_LOI_TU_DONG else None)
    hang = []
    for i, (ten, cau_hoi, mong_doi, kiem_tra) in enumerate(KICH_BAN, 1):
        k = router.xu_ly(cau_hoi)
        thuc_te = (k.thong_bao if k.hanh_dong == LOI_DAU_VAO
                   else f"{k.chu_de} ({k.do_tin_cay:.0%}) → {k.phong_ban}")
        hang.append((i, ten, cau_hoi[:60] + ("…" if len(cau_hoi) > 60 else ""), mong_doi, thuc_te, kiem_tra(k)))

    cau = "Em MSSV 21520001 hỏi học phí kỳ này"
    dong = tao_dong("x", cau, router.xu_ly(cau), router.phien_ban)
    hang.append((len(hang) + 1, "Có thông tin cá nhân", cau, "Nhật ký đã thay MSSV bằng <mssv>", dong["cau_hoi"],
                 "<mssv>" in dong["cau_hoi"] and "21520001" not in dong["cau_hoi"]))

    cau_hoi = [kb[1] for kb in KICH_BAN[:9]] * 6
    t0 = time.perf_counter()
    for c in cau_hoi[:50]:
        router.xu_ly(c)
    tb = (time.perf_counter() - t0) * 1000 / 50
    hang.append((len(hang) + 1, "Thời gian phản hồi", "50 câu liên tiếp", "Trung bình < 1000 ms/câu", f"{tb:.1f} ms/câu", tb < 1000))

    bang = pd.DataFrame(hang, columns=["#", "Kịch bản", "Input", "Mong đợi", "Thực tế", "Đạt"])
    bang["Đạt"] = bang["Đạt"].map({True: "Đạt", False: "Không đạt"})
    thu_muc = config.REPORT_ROOT / config.MODEL_VERSION
    thu_muc.mkdir(parents=True, exist_ok=True)
    bang.to_csv(thu_muc / "kiem_thu_kich_ban.csv", index=False)
    with pd.option_context("display.max_colwidth", 45, "display.width", 200):
        print(bang.to_string(index=False))
    print(f"\nĐạt {int((bang['Đạt'] == 'Đạt').sum())}/{len(bang)} kịch bản — model {router.phien_ban}. "
          f"Đã lưu {thu_muc / 'kiem_thu_kich_ban.csv'}")


if __name__ == "__main__":
    main()
