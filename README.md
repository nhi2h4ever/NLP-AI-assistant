# Student FAQ Router – Nhóm 7, môn Trí tuệ nhân tạo

Hệ thống AI dùng **Machine Learning** (TF-IDF + Naive Bayes / Logistic Regression / Linear SVM) để **phân loại câu hỏi học vụ tiếng Việt** của sinh viên và **chuyển về đúng phòng ban** phụ trách.

| Giai đoạn | `config.TRA_LOI_TU_DONG` | Hệ thống làm gì |
|---|---|---|
| **1 (hiện tại)** | `False` | Phân loại câu hỏi vào 7 chủ đề → chuyển đến phòng ban phụ trách. Câu mô hình chưa chắc chắn (độ tin cậy < τ) được chuyển cho trợ lý khoa phân loại thủ công. |
| 2 | `True` | Thêm trả lời tự động bằng kho FAQ (cosine similarity trên TF-IDF). Cần file `data/faq.csv`. |

**Chủ đề → phòng ban** của Trường Đại học Bách khoa – ĐH Đà Nẵng. Tên phòng ban và thông tin liên hệ (phòng, điện thoại, website) hiển thị cho sinh viên được khai báo trong `config.PHONG_BAN`; nhóm điền thêm thông tin của Văn phòng Khoa và Trợ lý khoa:

| Mã | Chủ đề | Phòng ban |
|---|---|---|
| `LICH_HOC` | Lịch học & đăng ký học phần | Phòng Đào tạo |
| `LICH_THI` | Lịch thi & điểm thi | Phòng Khảo thí và Đảm bảo chất lượng giáo dục |
| `HOC_PHI` | Học phí (mức thu, hạn đóng, cách đóng, hoàn tiền) | Phòng Kế hoạch - Tài chính |
| `HOC_BONG` | Học bổng, miễn giảm học phí, trợ cấp | Phòng Công tác sinh viên |
| `DO_AN` | Đồ án & khóa luận | Văn phòng Khoa |
| `QUY_CHE` | Quy chế & tốt nghiệp | Phòng Đào tạo |
| `KHAC` | Ngoài phạm vi | Trợ lý khoa |

## Cấu trúc thư mục

```
config.py              nhãn, phòng ban, giai đoạn, phiên bản model
preprocess.py          tiền xử lý tiếng Việt (dùng chung cho huấn luyện và app)
training.py            các hàm ML pipeline (Step 1–2)
router.py              mô hình + chính sách quyết định (+ tìm FAQ ở giai đoạn 2)
nhat_ky.py             nhật ký câu hỏi: CSV trên máy hoặc Google Sheets
app.py                 Trang Hỏi đáp cho sinh viên (Streamlit)
pages/1_Quan_tri.py    Trang Quản trị cho trợ lý khoa
notebooks/train.ipynb  notebook huấn luyện: dữ liệu → so sánh mô hình → tinh chỉnh → đánh giá → lưu model
scripts/kiem_thu_kich_ban.py  13 kịch bản kiểm thử hệ thống (Step 3)
tests/                 kiểm thử tự động (pytest)
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

1. **Thu thập và gán nhãn** câu hỏi thật (Google Form, nhóm Facebook, trợ lý khoa…) vào `data/questions.csv` theo mẫu `data/templates/questions_template.csv`:
   - `id`: mã duy nhất; `text`: câu hỏi; `label`: một trong 7 mã nhãn. Câu về **miễn giảm học phí** gán `HOC_BONG` (do Phòng Công tác sinh viên xét), không gán `HOC_PHI`.
   - `source`: `form` / `facebook` / `staff` (câu hỏi thật, được vào tập test), `team` (nhóm tự viết) hoặc `faq` (lấy từ tài liệu trường) — hai loại sau chỉ dùng để huấn luyện.
   - `multi_intent` (0/1), `annotator`, `faq_id` (chỉ cần ở giai đoạn 2).
2. **Đo độ đồng thuận gán nhãn:** 2 người gán cùng khoảng 100 câu vào `data/kappa_check.csv` (mẫu `data/templates/kappa_template.csv`).
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
4. Gửi link app cho sinh viên dùng thử. Trợ lý khoa vào trang **Quan tri** để xem câu hỏi theo phòng ban, xử lý các câu cần phân loại thủ công và điền "Nhãn đúng".

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
