# Hệ thống quản lý sự cố công nghệ thông tin (Đề tài 25)

Ứng dụng Python + Tkinter tiếp nhận ticket hỗ trợ, phân loại, phân công, theo dõi thời gian xử lý và cảnh báo SLA giả lập. Dữ liệu lưu bằng JSON.

## Yêu cầu và chạy
- Python 3.8 trở lên, có Tkinter (bản cài từ python.org đã kèm sẵn). Không cần cài thư viện ngoài.
- Chạy: `python main.py`  (xem tùy chọn bằng `python main.py --help`)
- Tạo lại dữ liệu mẫu: `python main.py --sample 40 --seed 2026 --no-gui`
- Đặt lại dữ liệu (có sao lưu trước): `python main.py --reset-data --yes`
- Nếu xóa thư mục `data/`, ứng dụng tự tạo lại tài khoản và nhóm mặc định; dùng menu Quản trị > Dữ liệu để sinh ticket mẫu.

## Tài khoản demo
| Vai trò | Tên đăng nhập | Mật khẩu |
|---|---|---|
| Quản trị viên | admin | Admin@123 |
| Kỹ thuật viên | agent | Agent@123 |
| Người dùng thông thường | user | User@123 |

Hãy đổi mật khẩu sau khi đăng nhập (Tài khoản > Đổi mật khẩu). Người dùng có thể tự tạo tài khoản ở tab "Tạo tài khoản".

## Phân quyền
- **Quản trị viên**: toàn bộ chức năng, gồm quản lý tài khoản, nhóm hỗ trợ, xóa ticket, sao lưu/khôi phục, sinh dữ liệu mẫu, nhật ký.
- **Kỹ thuật viên**: xem mọi ticket, sửa, phân công (chỉ nhận cho chính mình), đổi trạng thái, ghi chú nội bộ, thống kê, xuất báo cáo.
- **Người dùng thông thường**: tạo ticket, chỉ xem ticket của mình, sửa khi còn "Mới", phản hồi, xác nhận đóng hoặc mở lại khi đã giải quyết.

## Chức năng chính
1. Tạo ticket kèm mô tả và tệp đính kèm  2. Phân loại và phân công nhóm/người xử lý  3. Đổi trạng thái theo quy trình (Mới -> Đang xử lý -> Chờ phản hồi -> Đã giải quyết -> Đã đóng)  4. Phản hồi và ghi chú nội bộ  5. Tính thời gian xử lý, cảnh báo SLA (trong hạn / sắp quá hạn / quá hạn)  6. Tìm kiếm, lọc nhiều tiêu chí, sắp xếp, tìm gần đúng  7. Thống kê lỗi theo nhóm và mức độ (Canvas)  8. Xuất CSV/JSON/báo cáo TXT  9. Nhập dữ liệu từ API  10. Sao lưu/khôi phục, nhật ký sự kiện.

SLA giả lập theo mức ưu tiên: Khẩn cấp 4h, Cao 8h, Trung bình 24h, Thấp 72h (cấu hình trong `config.py`).

## Nguồn API
GitHub REST API công khai: `https://api.github.com/repos/{owner}/{repo}/issues` (tài liệu: https://docs.github.com/en/rest/issues/issues). Không cần khóa, giới hạn 60 lượt/giờ/IP, ứng dụng chỉ lấy tối đa 30 issue mỗi lần và có gửi User-Agent. Issue được làm sạch, chuyển thành ticket, lưu `data/api_issues.json`. Menu: Tệp > Nhập dữ liệu từ API. Khi mất mạng có thể dùng "Dùng dữ liệu đã lưu".

## Cấu trúc thư mục
```
main.py            điểm khởi động (sys.argv, mã thoát)
config.py          hằng số, đường dẫn, SLA, giao diện
models/            lớp dữ liệu: User (AdminUser/AgentUser/EndUser), Ticket, Feedback, SupportGroup
services/          JsonStore, UserManager, GroupManager, TicketManager, AuthService,
                   ApiService, stats_service, report_service, sample_data, AppContext
views/             giao diện Tkinter: app, login, tickets_tab, dashboard_tab, admin_tab, dialogs, widgets
utils/             exceptions, validators (Regex), sys_info (module sys)
data/              users.json, groups.json, tickets.json, api_issues.json (dữ liệu mẫu)
tests/             30 ca kiểm thử;  run_tests.py sinh docs/BANG_KIEM_THU.md
docs/              SO_DO_LOP.md, BANG_KIEM_THU.md, BANG_PHAN_CONG.md
```

## Kiểm thử và đóng gói
- `python run_tests.py` chạy 30 ca và cập nhật bảng kiểm thử.
- Đóng gói .exe trên Windows: kích hoạt venv rồi chạy `build_exe.bat` (kết quả `dist\TicketSystem.exe`, thư mục `data` nằm cạnh file .exe). Cần kiểm tra file .exe trên một máy khác trước khi nộp.

## Nguồn tham khảo
Tài liệu Python (tkinter, json, re, hashlib, urllib, unittest), tài liệu GitHub REST API. Không dùng mã nguồn ngoài.
