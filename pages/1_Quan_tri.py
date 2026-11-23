"""Trang Quản trị cho chuyên viên Phòng Công tác sinh viên (đơn vị chủ trì theo QT_11_CTSV): câu hỏi theo phòng ban, câu cần phân loại thủ công, thống kê,
sửa nhãn, xuất dữ liệu huấn luyện lại."""
import hmac

import pandas as pd
import streamlit as st

import config
from nhat_ky import doc_secrets, du_lieu_huan_luyen_lai, tao_nhat_ky
from router import CAN_PHAN_LOAI, TRA_LOI

st.set_page_config(page_title="Quản trị – Trợ lý học vụ", page_icon="🛠️", layout="wide")
st.title("🛠️ Trang Quản trị")

secrets = doc_secrets()
mat_khau = secrets.get("admin_password")
if not mat_khau:
    st.error("Chưa cấu hình `admin_password`. Tạo file .streamlit/secrets.toml theo mẫu "
             ".streamlit/secrets.toml.example (trên Streamlit Cloud: mục Secrets của app).")
    st.stop()

if not st.session_state.get("da_dang_nhap"):
    with st.form("dang_nhap"):
        nhap = st.text_input("Mật khẩu quản trị", type="password")
        if st.form_submit_button("Đăng nhập"):
            if hmac.compare_digest(nhap.encode(), str(mat_khau).encode()):
                st.session_state.da_dang_nhap = True
                st.rerun()
            st.error("Sai mật khẩu.")
    st.stop()


@st.cache_resource
def lay_nhat_ky():
    return tao_nhat_ky(doc_secrets())


nhat_ky = lay_nhat_ky()
st.caption(f"Nhật ký đang lưu tại: {nhat_ky.mo_ta}")
if st.button("🔄 Tải lại dữ liệu"):
    st.rerun()

df = nhat_ky.doc()
if df.empty:
    st.info("Chưa có câu hỏi nào trong nhật ký.")
    st.stop()

ten = {k: v[0] for k, v in config.NHAN.items()}
df["ten_chu_de"] = df.chu_de.map(ten).fillna(df.chu_de)
df["ngay"] = pd.to_datetime(df.thoi_gian, errors="coerce").dt.date
da_danh_gia = df[df.danh_gia != ""]

cot_bang = ["id", "thoi_gian", "cau_hoi", "ten_chu_de", "do_tin_cay", "phong_ban"]
TEN_COT = {"id": "Mã", "thoi_gian": "Thời gian", "cau_hoi": "Câu hỏi", "ten_chu_de": "Chủ đề dự đoán",
           "chu_de": "Chủ đề dự đoán", "phong_ban": "Chuyển đến", "hanh_dong": "Hành động", "faq_id": "FAQ"}
cau_hinh_cot = {**TEN_COT, "do_tin_cay": st.column_config.NumberColumn("Độ tin cậy", format="%.2f")}

# ---------------- Chỉ số tổng quan
c = st.columns(5)
c[0].metric("Tổng số câu hỏi", len(df))
c[1].metric("Phân loại tự động", f"{(df.hanh_dong != CAN_PHAN_LOAI).mean():.0%}",
            help="Tỉ lệ câu có độ tin cậy ≥ τ, được chuyển thẳng đến phòng ban")
c[2].metric("Cần phân loại thủ công", int((df.hanh_dong == CAN_PHAN_LOAI).sum()))
c[3].metric("Đánh giá tích cực", f"{(da_danh_gia.danh_gia == 'huu_ich').mean():.0%}" if len(da_danh_gia) else "—",
            help=f"Trên {len(da_danh_gia)} lượt đánh giá của sinh viên")
c[4].metric("Thời gian xử lý TB", f"{df.thoi_gian_xu_ly_ms.mean():.0f} ms")
if config.TRA_LOI_TU_DONG:
    st.caption(f"Trả lời tự động bằng kho FAQ: {(df.hanh_dong == TRA_LOI).mean():.0%} số câu.")

# ---------------- Thống kê
t1, t2, t3 = st.columns(3)
with t1:
    st.subheader("Theo phòng ban")
    st.bar_chart(df.phong_ban.value_counts())
with t2:
    st.subheader("Theo chủ đề")
    st.bar_chart(df.ten_chu_de.value_counts())
with t3:
    st.subheader("Theo ngày")
    st.line_chart(df.groupby("ngay").size().rename("Số câu"))

# ---------------- Câu cần phân loại thủ công
st.subheader("Câu hỏi cần phân loại thủ công")
st.caption("Mô hình chưa đủ tin cậy (độ tin cậy < τ). Chuyên viên P.CTSV xác định chủ đề, chuyển đến phòng ban "
           "phù hợp và điền “Nhãn đúng” ở bảng bên dưới.")
can = df[df.hanh_dong == CAN_PHAN_LOAI]
if can.empty:
    st.write("Không có câu nào.")
else:
    st.dataframe(can[cot_bang].sort_values("thoi_gian", ascending=False), hide_index=True, width="stretch",
                 column_config=cau_hinh_cot)

# ---------------- Câu hỏi theo phòng ban
st.subheader("Câu hỏi đã chuyển đến các phòng ban")
da_chuyen = df[df.hanh_dong != CAN_PHAN_LOAI]
phong = st.multiselect("Lọc theo phòng ban", sorted(da_chuyen.phong_ban.unique()), placeholder="Tất cả phòng ban")
if phong:
    da_chuyen = da_chuyen[da_chuyen.phong_ban.isin(phong)]
st.dataframe(da_chuyen[cot_bang].sort_values("thoi_gian", ascending=False), hide_index=True, width="stretch",
             column_config=cau_hinh_cot)

bi_che = df[df.danh_gia == "khong_huu_ich"]
if len(bi_che):
    st.subheader("Câu bị sinh viên đánh giá chưa đúng / không hữu ích")
    st.dataframe(bi_che[cot_bang + ["faq_id"]], hide_index=True, width="stretch", column_config=cau_hinh_cot)

# ---------------- Sửa nhãn
st.subheader("Gán nhãn đúng (dùng để huấn luyện lại)")
st.caption("Điền cột “Nhãn đúng” cho các câu đã xem xét — kể cả khi mô hình đoán đúng — rồi bấm Lưu.")
cot_sua = ["id", "thoi_gian", "cau_hoi", "chu_de", "do_tin_cay", "hanh_dong", "nhan_dung"]
bang = st.data_editor(
    df[cot_sua].sort_values("thoi_gian", ascending=False), hide_index=True, width="stretch",
    disabled=cot_sua[:-1], key="sua_nhan",
    column_config={**cau_hinh_cot,
                   "nhan_dung": st.column_config.SelectboxColumn("Nhãn đúng", options=[""] + list(config.NHAN))})
thay_doi = bang.merge(df[["id", "nhan_dung"]], on="id", suffixes=("", "_cu"))
thay_doi = thay_doi[thay_doi.nhan_dung.fillna("") != thay_doi.nhan_dung_cu]
if st.button(f"💾 Lưu nhãn ({len(thay_doi)} thay đổi)", disabled=thay_doi.empty):
    nhat_ky.cap_nhat_nhieu({r.id: {"nhan_dung": r.nhan_dung or ""} for r in thay_doi.itertuples()})
    st.success(f"Đã lưu {len(thay_doi)} nhãn.")
    st.rerun()

# ---------------- Xuất dữ liệu
st.subheader("Xuất dữ liệu")
d1, d2 = st.columns(2)
d1.download_button("⬇️ Toàn bộ nhật ký (CSV)", df.drop(columns=["ten_chu_de", "ngay"]).to_csv(index=False),
                   "nhat_ky.csv", "text/csv")
huan_luyen_lai = du_lieu_huan_luyen_lai(df)
d2.download_button(f"⬇️ Dữ liệu huấn luyện lại – {len(huan_luyen_lai)} câu (log_labeled.csv)",
                   huan_luyen_lai.to_csv(index=False), "log_labeled.csv", "text/csv",
                   disabled=huan_luyen_lai.empty,
                   help="Lưu file vào data/log_labeled.csv rồi chạy lại notebooks/train.ipynb với VERSION mới.")
