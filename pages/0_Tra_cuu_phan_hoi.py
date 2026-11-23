"""Trang Tra cứu phản hồi cho sinh viên (QT_11_CTSV, bước 3 – Thông báo kết quả).
Sinh viên nhập mã yêu cầu nhận được khi gửi câu hỏi để xem câu trả lời của phòng ban.
Không cần họ tên hay MSSV: mã yêu cầu ngẫu nhiên là cách duy nhất để xem phản hồi của một câu hỏi."""
import streamlit as st

import config
from nhat_ky import chuan_ma, doc_secrets, tao_nhat_ky, tim_theo_ma
from router import CAN_PHAN_LOAI

st.set_page_config(page_title="Tra cứu phản hồi – Trợ lý học vụ", page_icon="🔎", layout="centered")
st.title("🔎 Tra cứu phản hồi")
st.write("Nhập **mã yêu cầu** bạn nhận được khi gửi câu hỏi để xem phòng ban đã phản hồi chưa.")
st.caption("Mã yêu cầu gồm 8 ký tự (chữ a–f và chữ số), ví dụ b0ba4f36. "
           "Ai có mã đều xem được phản hồi, nên bạn hãy giữ mã cho riêng mình.")


@st.cache_resource
def lay_nhat_ky():
    return tao_nhat_ky(doc_secrets())


try:
    nhat_ky = lay_nhat_ky()
except (FileNotFoundError, ValueError, KeyError) as e:
    st.error(str(e))
    st.stop()

ma_tren_link = st.query_params.get("ma", "")
with st.form("tra_cuu"):
    ma = st.text_input("Mã yêu cầu", value=ma_tren_link, max_chars=20, placeholder="Ví dụ: b0ba4f36")
    tim = st.form_submit_button("Tra cứu", type="primary")

if tim or ma_tren_link:
    if chuan_ma(ma) is None:
        st.warning("Mã yêu cầu chưa đúng định dạng: cần đúng 8 ký tự gồm chữ a–f và chữ số.")
        st.stop()
    dong = tim_theo_ma(nhat_ky.doc(), ma)
    if dong is None:
        st.error("Không tìm thấy câu hỏi có mã này. Bạn kiểm tra lại mã yêu cầu nhé.")
        st.stop()

    phong_ban = config.ten_hien_tai(dong["phong_ban"])
    st.caption(f"Mã yêu cầu {dong['id']} · gửi lúc {dong['thoi_gian']}")
    st.markdown("**Câu hỏi của bạn**")
    st.text(dong["cau_hoi"])
    st.markdown(f"**Phòng ban xử lý:** {phong_ban}")

    if dong["phan_hoi"].strip():
        st.success(dong["phan_hoi"])
        st.caption(f"Phản hồi lúc {dong['thoi_gian_phan_hoi']}")
    else:
        ngoai_pham_vi = dong["chu_de"] == config.NHAN_KHAC and dong["hanh_dong"] != CAN_PHAN_LOAI
        thoi_han = config.THOI_HAN_PHAN_HOI_KHAC if ngoai_pham_vi else config.THOI_HAN_PHAN_HOI
        st.info(f"⏳ Câu hỏi đang được xử lý. Thời hạn phản hồi: {thoi_han} "
                f"(theo Quy trình {config.QUY_TRINH}).")
        lien_he = config.lien_he(phong_ban)
        if lien_he:
            st.caption(f"Nếu quá thời hạn mà chưa có phản hồi, bạn liên hệ trực tiếp: {lien_he}")
