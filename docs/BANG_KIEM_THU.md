# Bảng kiểm thử

Sinh tự động bởi `run_tests.py` lúc 12/11/2026 09:10. Tổng: 30 ca, đạt: 30.

| Mã | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|
| TC01 | Email 'a@b.vn' và 'abc@' | 'a@b.vn' hợp lệ; 'abc@' báo ValidationError | Đúng như mong đợi | Đạt |
| TC02 | SĐT '0912345678', '+84912345678', '091234567' (thiếu số) | hai số đầu hợp lệ, số cuối bị từ chối | Đúng như mong đợi | Đạt |
| TC03 | Ngày '31/02/2026', '25/12/2026', '2026-12-25' | 31/02 và sai định dạng bị từ chối; 25/12 hợp lệ | Đúng như mong đợi | Đạt |
| TC04 | Tiêu đề 4, 5, 120, 121 ký tự | 4 và 121 bị từ chối; 5 và 120 được chấp nhận | Đúng như mong đợi | Đạt |
| TC05 | Mô tả rỗng / toàn khoảng trắng | báo 'không được để trống', không tạo ticket | Đúng như mong đợi | Đạt |
| TC06 | admin/Admin@123 và admin/sai | đúng: đăng nhập; sai: AuthError | Đúng như mong đợi | Đạt |
| TC07 | Nhập sai mật khẩu 5 lần liên tiếp rồi nhập đúng | tài khoản bị khóa tạm, lần đúng vẫn bị từ chối | Đúng như mong đợi | Đạt |
| TC08 | Đăng ký trùng tên 'user'; mật khẩu '123456' (không có chữ) | cả hai bị từ chối | Đúng như mong đợi | Đạt |
| TC09 | Đọc users.json sau khi tạo tài khoản | không chứa mật khẩu gốc, có salt + hash | Đúng như mong đợi | Đạt |
| TC10 | Người dùng thường xóa ticket / quản lý tài khoản | PermissionDenied | Đúng như mong đợi | Đạt |
| TC11 | Tạo -> đọc lại từ file -> sửa -> xóa ticket | dữ liệu khớp ở từng bước, xóa xong không còn trong file | Đúng như mong đợi | Đạt |
| TC12 | Tìm 'wifi' + lọc ưu tiên + chưa phân công + khoảng ngày | chỉ trả đúng ticket khớp tất cả tiêu chí | Đúng như mong đợi | Đạt |
| TC13 | Tìm gần đúng 'wifii'; khoảng ngày từ > đến | tìm gần đúng thấy ticket; khoảng ngày sai báo lỗi | Đúng như mong đợi | Đạt |
| TC14 | Hai người dùng cùng tạo ticket | mỗi người chỉ thấy và chỉ truy cập được ticket của mình | Đúng như mong đợi | Đạt |
| TC15 | new -> resolved (nhảy cóc); new -> in_progress -> resolved -> closed | nhảy cóc bị từ chối, quy trình đúng được chấp nhận | Đúng như mong đợi | Đạt |
| TC16 | Xóa ticket đang xử lý; xóa nhóm đang có ticket | cả hai bị từ chối (ràng buộc dữ liệu) | Đúng như mong đợi | Đạt |
| TC17 | Kỹ thuật viên ghi chú nội bộ; người dùng xem ticket | người dùng không thấy ghi chú nội bộ và không được tạo | Đúng như mong đợi | Đạt |
| TC18 | Đính kèm tệp 6MB và tệp không tồn tại | cả hai bị từ chối, không tạo ticket | Đúng như mong đợi | Đạt |
| TC19 | Ticket high (SLA 8h) ở 1h, 7h, 8h01 sau khi tạo; đã giải quyết đúng/trễ hạn | ok, warning, breached, met, missed | Đúng như mong đợi | Đạt |
| TC20 | File JSON chưa tồn tại / rỗng | tự tạo dữ liệu mặc định, không báo lỗi | Đúng như mong đợi | Đạt |
| TC21 | Ghi hỏng tickets.json khi đã có bản sao lưu | tự khôi phục từ backup, giữ file hỏng (.corrupt), có cảnh báo | Đúng như mong đợi | Đạt |
| TC22 | File hỏng không có backup; file có 1 bản ghi sai trong 2 bản ghi | không crash; bản ghi sai bị bỏ qua và đếm | Đúng như mong đợi | Đạt |
| TC23 | Ghi 15 lần; sau đó khôi phục | giữ tối đa 10 bản sao lưu; khôi phục thành công | Đúng như mong đợi | Đạt |
| TC24 | Thư mục dữ liệu bị thay bằng file (không ghi được) khi tạo ticket | báo StorageError, bộ nhớ không giữ ticket lỗi | Đúng như mong đợi | Đạt |
| TC25 | API trả 5 bản ghi (1 PR, 1 tiêu đề ngắn, 1 thiếu số hiệu) | lọc còn 2, lưu JSON, nhập 2 ticket; nhập lại bị bỏ qua (trùng) | Đúng như mong đợi | Đạt |
| TC26 | Mất mạng, hết thời gian, HTTP 404, HTTP 403, JSON hỏng, repo sai định dạng | mỗi trường hợp ném ApiError với thông báo rõ ràng | Đúng như mong đợi | Đạt |
| TC27 | Thống kê khi chưa có ticket; sau khi sinh 40 ticket mẫu (seed 3) | rỗng: không chia cho 0; mẫu: tổng các nhóm = 40 | Đúng như mong đợi | Đạt |
| TC28 | Sinh 20 ticket với cùng seed ở hai thư mục khác nhau; số lượng 0 và 501 | cùng seed -> cùng tiêu đề; số lượng ngoài 1-500 bị từ chối | Đúng như mong đợi | Đạt |
| TC29 | Xóa/khóa quản trị viên cuối cùng; tự đổi vai trò của mình | bị từ chối (BusinessError) | Đúng như mong đợi | Đạt |
| TC30 | Xóa người dùng còn ticket mở; đổi mật khẩu sai mật khẩu cũ / đúng | xóa bị từ chối; đổi sai báo lỗi, đổi đúng đăng nhập được bằng mật khẩu mới | Đúng như mong đợi | Đạt |
