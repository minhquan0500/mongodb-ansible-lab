# Báo cáo Câu 1 — MongoDB 6.0 / Ansible / Docker

- Report_MongoDB_Ansible_Cau1.docx: báo cáo Word có thể chỉnh sửa, biên soạn theo mẫu Report.docx được cung cấp.
- Report_MongoDB_Ansible_Cau1.pdf: bản PDF 7 trang để xem và in.
- Minh_chung_Cau1.zip: 14 ảnh cùng đầu ra lệnh và manifest thời điểm chụp.

Giữ bìa UIT, thông tin môn học, GVHD, nhóm và danh sách thành viên của mẫu; thay nội dung thực hành bằng Câu 1. Điểm tự đánh giá để trống (—), không tự gán điểm hay xác nhận phân công chưa có dữ liệu.

Ảnh là screenshot bằng Chromium của trang hiển thị stdout thật, gồm các trường kết quả đã được trích và ghi nhãn; không phải screenshot một cửa sổ terminal desktop. Các lần gọi health, rs.status và deployment kiểm tra lại là thực tế. Nhật ký triển khai đầu tiên được ghi rõ là trích log trước đó. Không có secret trong ảnh/gói báo cáo.

Kiểm thử end-to-end dùng profile tiết kiệm đĩa trên Debian 13, cùng binaries MongoDB 6.0.26, 5 container với volume dữ liệu riêng. Chưa kiểm thử end-to-end cấu hình image mặc định trên Ubuntu. Báo cáo nêu rõ giới hạn này.

Chỉ Câu 1; không có nâng cấp 7.0, Câu 2 hoặc Câu 3.
