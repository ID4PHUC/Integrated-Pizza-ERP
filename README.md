# Integrated Pizza ERP System (Odoo 18)

Giải pháp quản trị doanh nghiệp toàn diện (End-to-End) dành cho lĩnh vực F&B, quản lý toàn bộ chuỗi cung ứng từ khâu nhập nguyên liệu đến sản xuất và giao hàng cuối (Last-mile delivery).

## Giải pháp trọng tâm

*   **Sản xuất dựa trên định mức (BoM):** Quy trình sản xuất tự động hóa dựa trên định mức nguyên vật liệu (Bill of Materials), tích hợp kiểm tra chất lượng (QC) và quản lý phế phẩm/hỏng hóc (Scrap).
*   **Quản lý kho thông minh (FEFO):** Hệ thống quản trị kho tiên tiến áp dụng quy tắc **First-Expired-First-Out** (Hết hạn trước - Xuất trước) kèm cảnh báo hạn sử dụng theo thời gian thực.
*   **Vận hành Giao nhận & PoD:** Tự động hóa khâu điều phối tài xế theo tuyến đường. Ứng dụng xác thực giao hàng **Proof of Delivery (PoD)** tích hợp chữ ký số và hình ảnh thực tế.
*   **Phân tích dữ liệu chuyên sâu:** Thiết kế các **SQL Views** hiệu suất cao để trích xuất báo cáo đa chiều về Định giá tồn kho, Xu hướng bán hàng và Đối soát tài chính (COD).

## Bộ công nghệ 

*   **Framework:** Odoo 18 
*   **Language:** Python, XML 
*   **Database:** PostgreSQL

## Hướng dẫn cài đặt

1. Sao chép thư mục dự án vào thư mục `custom_addons` trong bộ mã nguồn Odoo của bạn.
2. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
