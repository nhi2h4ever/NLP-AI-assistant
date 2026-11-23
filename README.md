# Student FAQ Router – Nhóm 7, môn Trí tuệ nhân tạo

Hệ thống AI dùng **Machine Learning** (TF-IDF + Naive Bayes / Logistic Regression / Linear SVM) để **phân loại câu hỏi học vụ tiếng Việt** của sinh viên và **chuyển về đúng phòng ban** phụ trách.

| Giai đoạn | `config.TRA_LOI_TU_DONG` | Hệ thống làm gì |
|---|---|---|
| **1 (hiện tại)** | `False` | Phân loại câu hỏi vào 7 chủ đề → chuyển đến phòng ban phụ trách. Câu mô hình chưa chắc chắn (độ tin cậy < τ) được chuyển về Phòng Công tác sinh viên phân loại thủ công. |
| 2 | `True` | Thêm trả lời tự động bằng kho FAQ (cosine similarity trên TF-IDF). Cần file `data/faq.csv`. |

**Chủ đề → phòng ban** của Trường Đại học Bách khoa – ĐH Đà Nẵng, theo danh bạ chính thức [dut.udn.vn/Danhba](https://dut.udn.vn/Danhba). Công tác khảo thí (lịch thi, phúc khảo) thuộc Phòng Đào tạo và Bảo đảm chất lượng. Thông tin liên hệ (phòng, điện thoại, email, website) hiển thị cho sinh viên được khai báo trong `config.PHONG_BAN`. Với Văn phòng Khoa, sinh viên được chỉ tới danh bạ của Trường để tìm khoa mình:

| Mã | Chủ đề | Phòng ban |
|---|---|---|
| `LICH_HOC` | Lịch học & đăng ký học phần | Phòng Đào tạo và Bảo đảm chất lượng |
| `LICH_THI` | Lịch thi & điểm thi | Phòng Đào tạo và Bảo đảm chất lượng |
| `HOC_PHI` | Học phí (mức thu, hạn đóng, cách đóng, hoàn tiền) | Phòng Kế hoạch - Tài chính |
| `HOC_BONG` | Học bổng, miễn giảm học phí, trợ cấp | Phòng Công tác sinh viên |
| `DO_AN` | Đồ án, khóa luận & thực tập | Văn phòng Khoa |
| `QUY_CHE` | Quy chế & tốt nghiệp | Phòng Đào tạo và Bảo đảm chất lượng |
| `KHAC` | Ngoài phạm vi | Phòng Công tác sinh viên |

## Căn cứ: Quy trình QT_11_CTSV

Hệ thống bám theo Quy trình *Tiếp nhận và giải quyết thắc mắc cho sinh viên* (QT_11_CTSV) của Trường. Phòng Công tác sinh viên **chủ trì** cả 3 bước, các Khoa và Phòng ban **phối hợp**:

| Bước | Quy trình hiện tại (thủ công) | Thời gian | Trong hệ thống |
|---|---|---|---|
| 1. Tiếp nhận | Trực tiếp tại bộ phận một cửa, email, trang fr.dut.udn.vn | Trong ngày | Trang Hỏi đáp nhận câu hỏi, ghi nhật ký |
| 2. Tổng hợp, phân loại | Chuyên viên P.CTSV đọc, phân loại theo đơn vị liên quan, chuyển tiếp | 1 ngày sau khi nhận | **Mô hình ML phân loại và chuyển ngay**; câu chưa chắc chắn → chuyên viên P.CTSV |
| 3. Thông báo kết quả | Chuyên viên trả lời qua email / fr.dut.udn.vn | 1–3 ngày | Sinh viên nhận **mã yêu cầu**, phòng ban, liên hệ và thời hạn phản hồi (3 ngày làm việc; câu ngoài phạm vi 1–2 ngày). Chuyên viên nhập câu trả lời trên trang Quản trị; sinh viên xem câu trả lời ở trang **Tra cứu phản hồi** bằng mã yêu cầu |

**Vì sao không hỏi họ tên, MSSV?**
- Câu hỏi được ghi nhật ký, hiển thị trên trang Quản trị và dùng để huấn luyện lại. Vì vậy hệ thống không thu thập thông tin cá nhân, và tự ẩn MSSV, số điện thoại, email nếu sinh viên lỡ nhập (theo tinh thần Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân).
- Sinh viên nhận câu trả lời bằng **mã yêu cầu** ngẫu nhiên (8 ký tự) hiện ra sau khi gửi câu hỏi. Trang Hỏi đáp có sẵn đường dẫn tới trang Tra cứu phản hồi cho đúng mã đó.

## Dữ liệu

`data/questions.csv` (2.815 câu, 7 nhãn) được tạo bằng `scripts/tao_du_lieu.py` từ dữ liệu gốc trong `data/raw/`:

| `source` | Nguồn | Số câu | Vào tập test? |
|---|---|---|---|
| `web` | Câu hỏi **thật** của sinh viên trên trang hỏi đáp công khai: [tuvan.vhu.edu.vn](https://tuvan.vhu.edu.vn/van-de-quan-tam/dao-tao-hoc-vu.html) (ĐH Văn Hiến), [forum.uit.edu.vn](https://forum.uit.edu.vn/latest) (ĐH CNTT – ĐHQG TP.HCM), [hlu.edu.vn/qa](https://hlu.edu.vn/qa) (ĐH Luật Hà Nội). Gồm 1.973 ticket VHU, 285 tiêu đề UIT forum (cả chuyên mục đời sống làm ví dụ ngoài phạm vi) và 1 câu HLU | 2.259 | Có |
| `faq` | `1_Bo_cau_hoi_chuan_co_nguon.docx`: hỏi–đáp công khai của UEF, PTIT, ULAW (đã diễn đạt lại) | 74 | Không |
| `noise` | `2_Bo_cau_hoi_nhieu_co_nguon.docx`: 3 biến thể nhiễu (không dấu, teencode, sai chính tả) của mỗi câu `faq` | 222 | Không |
| `generated` | `Dataset_300_QA_DUT_co_nguon.docx`: câu mô phỏng về DUT (30 ý × 10 cách hỏi) | 260 | Không |

- **Gán nhãn:**
  - Câu trong file Word đã có nhãn gốc: ánh xạ sang 7 nhãn theo bảng `data/raw/bang_anh_xa_nhan.csv`, cộng thêm vài câu sửa riêng.
  - Ticket trên web chưa có nhãn: gán theo từ khóa (cụm dài được so trước, ví dụ "khóa luận tốt nghiệp" → `DO_AN` chứ không phải `QUY_CHE`).
  - Câu mơ hồ ("Tìm hiểu thông tin"), câu nhiều chủ đề và câu không phải của sinh viên (doanh nghiệp, tuyển dụng) bị loại. Danh sách và lý do ở `data/raw/web_bi_loai.csv`.
  - Câu trong chuyên mục đời sống của UIT forum (tán gẫu, chỗ trọ, việc làm thêm) không khớp từ khóa học vụ nào được gán `KHAC`.
  - Mỗi nhãn lấy tối đa 400 ticket VHU (chọn theo mã băm của id, nên ổn định giữa các lần chạy) để các nhãn không chênh lệch quá nhiều.
- **Rà nhãn (Kappa):**
  - Hai thành viên gán nhãn **độc lập** 100 câu trong `data/kappa_can_gan.csv`: người thứ nhất điền cột `label_a`, người thứ hai điền cột `label_b`, không xem nhãn của nhau và không xem `questions.csv`.
  - Lưu file thành `data/kappa_check.csv`, rồi chạy lại notebook. Notebook tính Cohen's Kappa giữa hai người, và độ khớp giữa nhãn người gán với nhãn theo từ khóa.
- **Ẩn danh:**
  - Câu có tên người, số điện thoại, email hoặc MSSV bị loại khỏi `data/raw/`.
  - Không lưu câu trả lời của trường (có thể chứa số điện thoại phụ huynh).
- **Cột `nhom`:** các biến thể của cùng một câu gốc có chung `nhom`. Kiểm định chéo giữ chúng trong cùng một fold.
- **Hạn chế cần nêu trong báo cáo:**
  - Câu hỏi thật đến từ trường khác (VHU, UIT, HLU), chưa phải sinh viên DUT.
  - Ticket VHU là bản tóm tắt do cán bộ ghi lại ("SV muốn…").
  - Nhãn web được gán theo từ khóa nên cần rà lại.
  - `DO_AN` ít câu (59, chủ yếu về thực tập). Nhóm nên thu thêm câu hỏi thật về đồ án qua Google Form.

Chạy lại bước tạo dữ liệu (không cần mạng):

```bash
.venv/bin/python scripts/tao_du_lieu.py
```

## Cấu trúc thư mục

```
config.py              nhãn, phòng ban, giai đoạn, phiên bản model
preprocess.py          tiền xử lý tiếng Việt (dùng chung cho huấn luyện và app)
training.py            các hàm ML pipeline (Step 1–2)
router.py              mô hình + chính sách quyết định (+ tìm FAQ ở giai đoạn 2)
nhat_ky.py             nhật ký câu hỏi: CSV trên máy hoặc Google Sheets
app.py                 Trang Hỏi đáp cho sinh viên (Streamlit)
pages/0_Tra_cuu_phan_hoi.py  Trang Tra cứu phản hồi: sinh viên nhập mã yêu cầu để xem câu trả lời
pages/1_Quan_tri.py    Trang Quản trị cho chuyên viên Phòng Công tác sinh viên
notebooks/train.ipynb  notebook huấn luyện: dữ liệu → so sánh mô hình → tinh chỉnh → đánh giá → lưu model
scripts/kiem_thu_kich_ban.py  13 kịch bản kiểm thử hệ thống (Step 3)
scripts/tao_du_lieu.py        tạo data/questions.csv từ data/raw/ (ánh xạ nhãn, gán nhãn theo từ khóa)
tests/                 kiểm thử tự động (pytest)
data/raw/              dữ liệu gốc đã ẩn danh: câu hỏi trích từ file Word, ticket từ trang hỏi đáp
data/splits/           danh sách id tập test đã đóng băng
data/templates/        mẫu file dữ liệu
data/sample/           dữ liệu MẪU chỉ để chạy thử code — KHÔNG dùng cho báo cáo
models/<phiên bản>/    model.joblib + metadata.json
reports/<phiên bản>/   biểu đồ, bảng kết quả cho báo cáo
```

## Cài đặt

Cần Python 3.12.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements-dev.txt
```

## Chạy thử ngay với dữ liệu mẫu (chế độ demo)

Dữ liệu mẫu trong `data/sample/` chỉ để kiểm tra code chạy được; **kết quả demo không dùng cho báo cáo**.

```bash
FAQ_ROUTER_DEMO=1 .venv/bin/jupyter nbconvert --to notebook --execute notebooks/train.ipynb --output /tmp/train_demo.ipynb
```

```bash
FAQ_ROUTER_DEMO=1 .venv/bin/streamlit run app.py
```

## Quy trình làm với dữ liệu thật

1. **Thu thập và gán nhãn** thêm câu hỏi thật (Google Form, nhóm Facebook, câu hỏi P.CTSV đã nhận qua email / fr.dut.udn.vn…) vào `data/questions.csv` theo mẫu `data/templates/questions_template.csv`. Nếu chạy lại `scripts/tao_du_lieu.py` thì thêm các câu này vào sau, vì script ghi đè file:
   - `id`: mã duy nhất; `text`: câu hỏi; `label`: một trong 7 mã nhãn. Câu về **miễn giảm học phí** gán `HOC_BONG` (do Phòng Công tác sinh viên xét), không gán `HOC_PHI`.
   - `source`: `form` / `facebook` / `staff` / `web` (câu hỏi thật, được vào tập test), hoặc `team` (nhóm tự viết), `faq`, `noise`, `generated` — các loại sau chỉ dùng để huấn luyện.
   - `multi_intent` (0/1), `annotator`, `faq_id` (chỉ cần ở giai đoạn 2), `nhom` (để trống nếu câu không phải biến thể của câu khác).
2. **Đo độ đồng thuận gán nhãn:** 2 người gán độc lập 100 câu trong `data/kappa_can_gan.csv` rồi lưu thành `data/kappa_check.csv` (xem mục *Dữ liệu*).
3. **Huấn luyện:** mở `notebooks/train.ipynb`, giữ `VERSION = "v1"`, chạy *Restart & Run All*. Kết quả: `models/v1/` và `reports/v1/`.
   - Lần chạy đầu tiên, danh sách câu hỏi của tập test được **đóng băng** ở `data/splits/test_ids.txt`. Các lần sau dùng lại đúng tập test này. Chỉ xoá file đó nếu muốn chia lại tập test, và chỉ làm trước khi chốt kết quả cho báo cáo.
4. **Kiểm thử hệ thống:**

```bash
.venv/bin/python scripts/kiem_thu_kich_ban.py
```

```bash
.venv/bin/python -m pytest -q tests
```

5. **Chạy app trên máy:** sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`, đổi `admin_password`, rồi chạy:

```bash
.venv/bin/streamlit run app.py
```

## Triển khai lên Streamlit Community Cloud (Step 4)

1. Đưa thư mục lên GitHub. File `.gitignore` đã loại `secrets.toml`, `logs/` và các file demo. Nhớ đưa lên cả `models/v1/`.
2. Tại share.streamlit.io: tạo app mới, chọn repo và file `app.py`, chọn Python 3.12.
3. Ở mục **Secrets**, dán nội dung theo `.streamlit/secrets.toml.example` với `log_backend = "sheets"`:
   - Tạo Google Sheet và một service account trên Google Cloud.
   - Chia sẻ Sheet (quyền Editor) cho email của service account.
   - Dán `sheet_url` và khóa JSON vào mục `[gcp_service_account]`.
   - Phải dùng Google Sheets vì file ghi trên máy chủ Streamlit Cloud có thể mất khi app khởi động lại.
4. Gửi link app cho sinh viên dùng thử. Chuyên viên P.CTSV vào trang **Quan tri** để xem câu hỏi theo phòng ban, xử lý các câu cần phân loại thủ công, nhập **phản hồi** cho sinh viên và điền "Nhãn đúng". Sinh viên xem phản hồi ở trang **Tra cuu phan hoi** bằng mã yêu cầu.

## Huấn luyện lại (v1 → v2)

1. Trang Quản trị → **Dữ liệu huấn luyện lại** → tải `log_labeled.csv`, lưu vào `data/log_labeled.csv`.
2. Trong notebook đặt `VERSION = "v2"`, `PREV_VERSION = "v1"`, rồi chạy lại.
   - Một nửa số câu trong nhật ký được bổ sung vào train, nửa còn lại làm tập test thực tế.
   - Mục 2.8 của notebook so sánh v1 và v2 trên cùng các tập test.
3. Nếu v2 không kém hơn v1: sửa `MODEL_VERSION = "v2"` trong `config.py` rồi đưa lên GitHub. Giữ `models/v1/` để có thể quay lại.

## Chuyển sang giai đoạn 2 (trả lời tự động)

1. Soạn `data/faq.csv` theo `data/templates/faq_template.csv`: câu trả lời lấy từ tài liệu chính thức của trường, có nguồn và ngày cập nhật.
2. Ghi `faq_id` cho khoảng 50 câu trong `data/questions.csv` (câu FAQ đúng của câu hỏi đó).
3. Đặt `TRA_LOI_TU_DONG = True` trong `config.py`, chạy lại notebook. Mục 2.7 sẽ chọn ngưỡng tương đồng `s_min`.
