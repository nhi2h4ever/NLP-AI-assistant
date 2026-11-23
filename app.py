"""Trang Hỏi đáp cho sinh viên — chạy: streamlit run app.py
Giai đoạn 1 (config.TRA_LOI_TU_DONG = False): phân loại câu hỏi và chuyển về đúng phòng ban.
Giai đoạn 2 (True): thêm trả lời tự động bằng kho FAQ."""
import uuid

import streamlit as st

import config
from nhat_ky import doc_secrets, tao_dong, tao_nhat_ky
from router import CAN_PHAN_LOAI, LOI_DAU_VAO, TRA_LOI, Router

st.set_page_config(page_title="Trợ lý học vụ", page_icon="🎓", layout="centered")


@st.cache_resource
def lay_router(model_dir, faq_path):
    return Router.tu_thu_muc(model_dir, faq_path)


@st.cache_resource
def lay_nhat_ky():
    return tao_nhat_ky(doc_secrets())


try:
    router = lay_router(config.MODEL_DIR, config.FAQ_PATH if config.TRA_LOI_TU_DONG else None)
    nhat_ky = lay_nhat_ky()
except (FileNotFoundError, ValueError) as e:
    st.error(str(e))
    st.stop()

with st.sidebar:
    st.header("Giới thiệu")
    if router.tra_loi_tu_dong:
        st.write("Trợ lý tự động phân loại câu hỏi học vụ, trả lời các câu hỏi thường gặp "
                 "và chuyển các câu còn lại đến đúng phòng ban.")
    else:
        st.write("Trợ lý tự động phân loại câu hỏi học vụ và chuyển đến đúng phòng ban phụ trách.")
    st.markdown("**Chủ đề → phòng ban phụ trách:**\n" + "\n".join(
        f"- {ten} → {pb}" for ma, (ten, pb) in config.NHAN.items() if ma != config.NHAN_KHAC))
    st.caption("Vui lòng không nhập họ tên, MSSV, số điện thoại; nếu có, hệ thống tự ẩn trước khi lưu. "
               "Bạn xem câu trả lời bằng mã yêu cầu ở trang “Tra cuu phan hoi”.")
    st.caption(f"Phiên bản model: {router.phien_ban}")

st.title("🎓 Trợ lý học vụ")
st.write("Gửi câu hỏi về lịch học, đăng ký học phần, lịch thi, học phí, học bổng, đồ án hoặc quy chế. "
         "Hệ thống sẽ xác định chủ đề và chuyển câu hỏi đến phòng ban phụ trách.")
if config.DEMO:
    st.warning("Chế độ DEMO: model được huấn luyện trên dữ liệu mẫu, chỉ để kiểm tra hệ thống.")

with st.form("hoi_dap"):
    cau_hoi = st.text_area("Câu hỏi của bạn", max_chars=config.MAX_LEN,
                           placeholder="Ví dụ: Khi nào có lịch thi lại môn Giải tích 1 ạ?")
    gui = st.form_submit_button("Gửi câu hỏi", type="primary")

if gui:
    kq = router.xu_ly(cau_hoi)
    ma = None
    if kq.hanh_dong != LOI_DAU_VAO:
        ma = uuid.uuid4().hex[:8]
        nhat_ky.ghi(tao_dong(ma, cau_hoi, kq, router.phien_ban))
    st.session_state.ket_qua = (ma, kq)

if "ket_qua" in st.session_state:
    ma, kq = st.session_state.ket_qua
    if kq.hanh_dong == LOI_DAU_VAO:
        st.warning(kq.thong_bao)
    else:
        st.metric("Chủ đề", kq.ten_chu_de if kq.hanh_dong != CAN_PHAN_LOAI else "Chưa xác định")
        st.progress(min(kq.do_tin_cay, 1.0), text=f"Độ tin cậy: {kq.do_tin_cay:.0%}")
        st.markdown(f"#### 📨 Chuyển đến: {kq.phong_ban}")
        lien_he = config.lien_he(kq.phong_ban)
        if lien_he:
            st.caption(f"📍 Liên hệ trực tiếp: {lien_he}")
        if kq.hanh_dong == TRA_LOI:
            st.success(kq.cau_tra_loi)
            st.caption(f"Nguồn: {kq.nguon} · Cập nhật: {kq.cap_nhat}")
        else:
            st.info(f"{kq.thong_bao} Mã yêu cầu: **{ma}**")
            st.caption(f"⏱ Thời hạn phản hồi: {kq.thoi_han} "
                       f"(theo Quy trình {config.QUY_TRINH} – Tiếp nhận và giải quyết thắc mắc cho sinh viên).")
            st.caption("Lưu lại mã yêu cầu: khi phòng ban trả lời, bạn xem phản hồi bằng mã này "
                       "(không cần họ tên hay MSSV).")
            st.page_link("pages/0_Tra_cuu_phan_hoi.py", label="Tra cứu phản hồi cho mã này", icon="🔎",
                         query_params={"ma": ma})

        danh_gia = st.session_state.setdefault("da_danh_gia", {})
        if kq.hanh_dong == CAN_PHAN_LOAI:
            pass  # chưa có chủ đề để sinh viên đánh giá; chuyên viên P.CTSV sẽ phân loại
        elif ma in danh_gia:
            st.caption("Cảm ơn bạn đã đánh giá!")
        else:
            st.write("Câu trả lời có hữu ích không?" if kq.hanh_dong == TRA_LOI
                     else "Hệ thống phân loại đúng chủ đề câu hỏi của bạn không?")
            nut = ([("👍 Hữu ích", "huu_ich"), ("👎 Không hữu ích", "khong_huu_ich")] if kq.hanh_dong == TRA_LOI
                   else [("👍 Đúng", "huu_ich"), ("👎 Chưa đúng", "khong_huu_ich")])
            cot = st.columns([1, 1, 3])
            for (nhan, gia_tri), o in zip(nut, cot):
                if o.button(nhan, key=f"{gia_tri}_{ma}"):
                    nhat_ky.cap_nhat(ma, danh_gia=gia_tri)
                    danh_gia[ma] = gia_tri
                    st.rerun()

        with st.expander("Chi tiết dự đoán của mô hình"):
            st.table({"Chủ đề": [config.NHAN[n][0] for n, _ in kq.top3],
                      "Phòng ban": [config.phong_ban(n) for n, _ in kq.top3],
                      "Xác suất": [f"{p:.1%}" for _, p in kq.top3]})
            chi_tiet = f"Ngưỡng tin cậy τ = {router.nguong_tin_cay:.2f}"
            if router.tra_loi_tu_dong:
                chi_tiet += (f" · Độ tương đồng FAQ = {kq.do_tuong_dong:.2f} "
                             f"(ngưỡng {router.nguong_tuong_dong:.2f})")
            st.caption(f"{chi_tiet} · Thời gian xử lý: {kq.thoi_gian_ms:.0f} ms")
