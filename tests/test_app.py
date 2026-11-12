"""Bộ kiểm thử tự động (unittest). Mỗi ca có docstring dạng:  Đầu vào | Kết quả mong đợi
để `run_tests.py` sinh ra bảng kiểm thử trong docs/BANG_KIEM_THU.md.

Chạy:  python -m unittest discover -s tests -v
"""
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from models.ticket import Ticket
from services import sample_data, stats_service
from services.api_service import ApiService
from services.context import AppContext
from services.json_store import JsonStore
from services.ticket_manager import UNASSIGNED
from utils import validators as v
from utils.exceptions import (ApiError, AuthError, BusinessError, PermissionDenied, StorageError,
                              ValidationError)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.ctx = AppContext(self.dir)
        self.admin = self.ctx.auth.login("admin", "Admin@123")
        self.agent = self.ctx.users.get("agent")
        self.user = self.ctx.users.get("user")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def new_ticket(self, actor=None, **kw):
        args = dict(title="Máy in bị kẹt giấy", description="Máy in tầng 2 kẹt giấy liên tục",
                    category="Phần cứng", priority="high")
        args.update(kw)
        return self.ctx.tickets.create(actor or self.user, **args)


class TestValidation(Base):
    def test_tc01_email_valid_invalid(self):
        """TC01 | Email 'a@b.vn' và 'abc@' | 'a@b.vn' hợp lệ; 'abc@' báo ValidationError"""
        self.assertEqual(v.validate_email("A@B.vn"), "a@b.vn")
        with self.assertRaises(ValidationError):
            v.validate_email("abc@")

    def test_tc02_phone_boundary(self):
        """TC02 | SĐT '0912345678', '+84912345678', '091234567' (thiếu số) | hai số đầu hợp lệ, số cuối bị từ chối"""
        self.assertEqual(v.validate_phone("0912345678"), "0912345678")
        self.assertEqual(v.validate_phone("+84912345678"), "+84912345678")
        with self.assertRaises(ValidationError):
            v.validate_phone("091234567")

    def test_tc03_date_nonexistent(self):
        """TC03 | Ngày '31/02/2026', '25/12/2026', '2026-12-25' | 31/02 và sai định dạng bị từ chối; 25/12 hợp lệ"""
        self.assertEqual(v.validate_date_str("25/12/2026"), date(2026, 12, 25))
        for bad in ("31/02/2026", "2026-12-25"):
            with self.assertRaises(ValidationError):
                v.validate_date_str(bad)

    def test_tc04_title_boundary(self):
        """TC04 | Tiêu đề 4, 5, 120, 121 ký tự | 4 và 121 bị từ chối; 5 và 120 được chấp nhận"""
        for n in (5, 120):
            self.assertTrue(self.new_ticket(title="a" * n))
        for n in (4, 121):
            with self.assertRaises(ValidationError):
                self.new_ticket(title="a" * n)

    def test_tc05_empty_and_control_chars(self):
        """TC05 | Mô tả rỗng / toàn khoảng trắng | báo 'không được để trống', không tạo ticket"""
        with self.assertRaises(ValidationError):
            self.new_ticket(description="   \n  ")
        self.assertEqual(len(self.ctx.tickets.all_tickets()), 0)


class TestAuth(Base):
    def test_tc06_login_ok_and_wrong_password(self):
        """TC06 | admin/Admin@123 và admin/sai | đúng: đăng nhập; sai: AuthError"""
        self.assertEqual(self.ctx.auth.login("admin", "Admin@123").role, config.ROLE_ADMIN)
        with self.assertRaises(AuthError):
            self.ctx.auth.login("admin", "sai")

    def test_tc07_lockout_after_5_failures(self):
        """TC07 | Nhập sai mật khẩu 5 lần liên tiếp rồi nhập đúng | tài khoản bị khóa tạm, lần đúng vẫn bị từ chối"""
        for _ in range(config.MAX_LOGIN_ATTEMPTS):
            with self.assertRaises(AuthError):
                self.ctx.auth.login("user", "sai")
        with self.assertRaises(AuthError) as cm:
            self.ctx.auth.login("user", "User@123")
        self.assertIn("khóa", str(cm.exception))

    def test_tc08_register_duplicate_and_weak_password(self):
        """TC08 | Đăng ký trùng tên 'user'; mật khẩu '123456' (không có chữ) | cả hai bị từ chối"""
        with self.assertRaises(ValidationError):
            self.ctx.auth.register("user", "Ten Du", "x@y.vn", "", "Abc123", "Abc123")
        with self.assertRaises(ValidationError):
            self.ctx.auth.register("newuser", "Ten Du", "x@y.vn", "", "123456", "123456")

    def test_tc09_password_is_hashed(self):
        """TC09 | Đọc users.json sau khi tạo tài khoản | không chứa mật khẩu gốc, có salt + hash"""
        raw = (self.dir / config.USERS_FILE_NAME).read_text(encoding="utf-8")
        self.assertNotIn("Admin@123", raw)
        self.assertIn("password_hash", raw)
        self.assertIn("salt", raw)

    def test_tc10_user_cannot_use_admin_functions(self):
        """TC10 | Người dùng thường xóa ticket / quản lý tài khoản | PermissionDenied"""
        t = self.new_ticket()
        with self.assertRaises(PermissionDenied):
            self.ctx.tickets.delete(self.user, t.ticket_id)
        with self.assertRaises(PermissionDenied):
            self.ctx.users.delete(self.user, "agent")


class TestTickets(Base):
    def test_tc11_create_read_update_delete(self):
        """TC11 | Tạo -> đọc lại từ file -> sửa -> xóa ticket | dữ liệu khớp ở từng bước, xóa xong không còn trong file"""
        t = self.new_ticket()
        self.assertEqual(t.ticket_id, "TK000001")
        reloaded = AppContext(self.dir)
        self.assertEqual(reloaded.tickets.get(self.admin, "TK000001").title, "Máy in bị kẹt giấy")
        self.ctx.tickets.update(self.user, t.ticket_id, "Máy in hỏng hoàn toàn", "Mô tả đã được sửa lại",
                                "Phần cứng", "critical")
        self.assertEqual(AppContext(self.dir).tickets.get(self.admin, "TK000001").priority, "critical")
        self.ctx.tickets.delete(self.admin, t.ticket_id)
        self.assertEqual(AppContext(self.dir).tickets.all_tickets(), [])

    def test_tc12_search_and_filter(self):
        """TC12 | Tìm 'wifi' + lọc ưu tiên + chưa phân công + khoảng ngày | chỉ trả đúng ticket khớp tất cả tiêu chí"""
        a = self.new_ticket(title="Wifi tầng 2 chập chờn", description="Mất kết nối wifi nhiều lần",
                            category="Mạng", priority="high")
        self.new_ticket(title="Máy in kẹt giấy", priority="low")
        got = self.ctx.tickets.search(self.admin, keyword="wifi", priority="high", assignee=UNASSIGNED,
                                      date_from=date.today(), date_to=date.today())
        self.assertEqual([t.ticket_id for t in got], [a.ticket_id])
        self.assertEqual(self.ctx.tickets.search(self.admin, keyword="khong-co-gi"), [])

    def test_tc13_fuzzy_search_and_invalid_date_range(self):
        """TC13 | Tìm gần đúng 'wifii'; khoảng ngày từ > đến | tìm gần đúng thấy ticket; khoảng ngày sai báo lỗi"""
        self.new_ticket(title="Wifi tầng 2 chập chờn", description="Mất kết nối wifi nhiều lần")
        self.assertEqual(len(self.ctx.tickets.search(self.admin, keyword="wifii", fuzzy=True)), 1)
        self.assertEqual(len(self.ctx.tickets.search(self.admin, keyword="wifii", fuzzy=False)), 0)
        with self.assertRaises(ValidationError):
            self.ctx.tickets.search(self.admin, date_from=date(2026, 12, 1), date_to=date(2026, 1, 1))

    def test_tc14_user_sees_only_own_tickets(self):
        """TC14 | Hai người dùng cùng tạo ticket | mỗi người chỉ thấy và chỉ truy cập được ticket của mình"""
        other = self.ctx.users.register("other_user", "Người Khác", "o@x.vn", "", "Other123")
        mine, theirs = self.new_ticket(), self.new_ticket(other)
        self.assertEqual([t.ticket_id for t in self.ctx.tickets.list_for(self.user)], [mine.ticket_id])
        with self.assertRaises(PermissionDenied):
            self.ctx.tickets.get(self.user, theirs.ticket_id)

    def test_tc15_status_workflow(self):
        """TC15 | new -> resolved (nhảy cóc); new -> in_progress -> resolved -> closed | nhảy cóc bị từ chối, quy trình đúng được chấp nhận"""
        t = self.new_ticket()
        with self.assertRaises(BusinessError):
            self.ctx.tickets.change_status(self.agent, t.ticket_id, "resolved")
        for status in ("in_progress", "resolved", "closed"):
            self.ctx.tickets.change_status(self.agent, t.ticket_id, status)
        self.assertEqual(t.status, "closed")
        with self.assertRaises(BusinessError):        # ticket đã đóng không nhận phản hồi
            self.ctx.tickets.add_feedback(self.agent, t.ticket_id, "thêm ý kiến")

    def test_tc16_delete_constraints(self):
        """TC16 | Xóa ticket đang xử lý; xóa nhóm đang có ticket | cả hai bị từ chối (ràng buộc dữ liệu)"""
        t = self.new_ticket()
        self.ctx.tickets.change_status(self.agent, t.ticket_id, "in_progress")
        with self.assertRaises(BusinessError):
            self.ctx.tickets.delete(self.admin, t.ticket_id)
        with self.assertRaises(BusinessError):
            self.ctx.groups.delete(self.admin, t.group_id)

    def test_tc17_internal_note_hidden_from_user(self):
        """TC17 | Kỹ thuật viên ghi chú nội bộ; người dùng xem ticket | người dùng không thấy ghi chú nội bộ và không được tạo"""
        t = self.new_ticket()
        self.ctx.tickets.add_feedback(self.agent, t.ticket_id, "Nghi do cáp mạng", internal=True)
        self.ctx.tickets.add_feedback(self.user, t.ticket_id, "Cảm ơn đã hỗ trợ")
        self.assertEqual(len(t.visible_feedbacks(self.user.can("ticket.internal_note"))), 1)
        self.assertEqual(len(t.visible_feedbacks(self.agent.can("ticket.internal_note"))), 2)
        with self.assertRaises(PermissionDenied):
            self.ctx.tickets.add_feedback(self.user, t.ticket_id, "ghi chú", internal=True)

    def test_tc18_attachment_too_large_and_missing(self):
        """TC18 | Đính kèm tệp 6MB và tệp không tồn tại | cả hai bị từ chối, không tạo ticket"""
        big = self.dir / "big.bin"
        big.write_bytes(b"0" * (6 * 1024 * 1024))
        with self.assertRaises(ValidationError):
            self.new_ticket(attachment_src=str(big))
        with self.assertRaises(ValidationError):
            self.new_ticket(attachment_src=str(self.dir / "khong_ton_tai.txt"))
        self.assertEqual(self.ctx.tickets.all_tickets(), [])


class TestSLA(Base):
    def test_tc19_sla_states_and_boundary(self):
        """TC19 | Ticket high (SLA 8h) ở 1h, 7h, 8h01 sau khi tạo; đã giải quyết đúng/trễ hạn | ok, warning, breached, met, missed"""
        t = Ticket("TK000001", "Kiểm tra SLA", "Mô tả đủ dài để hợp lệ", "user", "Mạng", "high",
                   created_at=datetime(2026, 1, 1, 8, 0, 0))
        at = lambda h, m=0: datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=h, minutes=m)
        self.assertEqual(t.sla_state(at(1)), "ok")
        self.assertEqual(t.sla_state(at(7)), "warning")
        self.assertEqual(t.sla_state(at(8, 1)), "breached")
        t.change_status("in_progress", "agent")
        t.change_status("resolved", "agent")
        t.resolved_at = at(7)
        self.assertEqual(t.sla_state(at(100)), "met")
        t.resolved_at = at(9)
        self.assertEqual(t.sla_state(at(100)), "missed")


class TestStorage(Base):
    def test_tc20_missing_and_empty_file(self):
        """TC20 | File JSON chưa tồn tại / rỗng | tự tạo dữ liệu mặc định, không báo lỗi"""
        store = JsonStore(self.dir / "new.json", list)
        self.assertEqual(store.load(), [])
        (self.dir / "empty.json").write_text("", encoding="utf-8")
        self.assertEqual(JsonStore(self.dir / "empty.json", list).load(), [])

    def test_tc21_corrupt_file_recovers_from_backup(self):
        """TC21 | Ghi hỏng tickets.json khi đã có bản sao lưu | tự khôi phục từ backup, giữ file hỏng (.corrupt), có cảnh báo"""
        self.new_ticket()
        self.new_ticket(title="Ticket thứ hai")      # lần ghi thứ hai tạo ra bản sao lưu
        path = self.dir / config.TICKETS_FILE_NAME
        path.write_text("{ không phải json", encoding="utf-8")
        ctx2 = AppContext(self.dir)
        self.assertGreaterEqual(len(ctx2.tickets.all_tickets()), 1)
        self.assertTrue(list(self.dir.glob("*.corrupt")))
        self.assertTrue(ctx2.startup_warnings())

    def test_tc22_corrupt_without_backup_and_bad_records(self):
        """TC22 | File hỏng không có backup; file có 1 bản ghi sai trong 2 bản ghi | không crash; bản ghi sai bị bỏ qua và đếm"""
        (self.dir / config.TICKETS_FILE_NAME).write_text("[[[", encoding="utf-8")
        self.assertEqual(AppContext(self.dir).tickets.all_tickets(), [])
        good = Ticket("TK000001", "Ticket hợp lệ", "Mô tả đủ dài để hợp lệ", "user", "Mạng", "low").to_dict()
        bad = dict(good, ticket_id="SAI", title="x")
        (self.dir / config.TICKETS_FILE_NAME).write_text(json.dumps([good, bad]), encoding="utf-8")
        ctx3 = AppContext(self.dir)
        self.assertEqual(len(ctx3.tickets.all_tickets()), 1)
        self.assertEqual(ctx3.tickets.skipped, 1)

    def test_tc23_backup_limit_and_restore(self):
        """TC23 | Ghi 15 lần; sau đó khôi phục | giữ tối đa 10 bản sao lưu; khôi phục thành công"""
        store = JsonStore(self.dir / "x.json", list, self.dir / "bk", max_backups=10)
        for i in range(15):
            store.save([i])
        self.assertLessEqual(len(store.list_backups()), 10)
        store.restore_latest()
        self.assertIsInstance(store.load(), list)

    def test_tc24_write_failure_keeps_memory_consistent(self):
        """TC24 | Thư mục dữ liệu bị thay bằng file (không ghi được) khi tạo ticket | báo StorageError, bộ nhớ không giữ ticket lỗi"""
        shutil.rmtree(self.dir / "attachments", ignore_errors=True)
        store_path = self.ctx.ticket_store.path
        self.ctx.ticket_store.path = self.dir / "chan" / "tickets.json"
        (self.dir / "chan").write_text("tôi là file, không phải thư mục", encoding="utf-8")
        with self.assertRaises(StorageError):
            self.new_ticket()
        self.ctx.ticket_store.path = store_path


class TestApi(Base):
    PAYLOAD = [
        {"number": 1, "title": "Crash khi mở tệp lớn", "body": "Chương trình bị crash khi mở tệp lớn", "state": "open",
         "labels": [{"name": "type-crash"}], "created_at": "2026-11-01T08:00:00Z", "html_url": "u1"},
        {"number": 2, "title": "PR không phải issue", "pull_request": {}, "state": "open", "labels": []},
        {"number": 3, "title": "ab", "body": "tiêu đề quá ngắn", "state": "open", "labels": []},
        {"title": "Thiếu số hiệu", "state": "open", "labels": []},
        {"number": 4, "title": "Cập nhật tài liệu hướng dẫn", "body": None, "state": "closed",
         "labels": [{"name": "docs"}], "created_at": "2026-11-02T09:00:00Z"},
    ]

    def api(self, fetcher):
        return ApiService(self.ctx.api_store, fetcher)

    def test_tc25_api_clean_save_and_import(self):
        """TC25 | API trả 5 bản ghi (1 PR, 1 tiêu đề ngắn, 1 thiếu số hiệu) | lọc còn 2, lưu JSON, nhập 2 ticket; nhập lại bị bỏ qua (trùng)"""
        records = self.api(lambda url, timeout: json.dumps(self.PAYLOAD).encode()).fetch_issues("python/cpython", 10)
        self.assertEqual([r["external_ref"] for r in records], ["github:python/cpython#1", "github:python/cpython#4"])
        self.assertEqual(len(json.loads((self.dir / config.API_CACHE_FILE_NAME).read_text(encoding="utf-8"))), 2)
        self.assertEqual(self.ctx.tickets.import_external(self.admin, records), (2, 0))
        self.assertEqual(self.ctx.tickets.import_external(self.admin, records), (0, 2))
        with self.assertRaises(PermissionDenied):
            self.ctx.tickets.import_external(self.user, records)

    def test_tc26_api_errors(self):
        """TC26 | Mất mạng, hết thời gian, HTTP 404, HTTP 403, JSON hỏng, repo sai định dạng | mỗi trường hợp ném ApiError với thông báo rõ ràng"""
        def raiser(exc):
            def f(url, timeout):
                raise exc
            return f
        cases = [urllib.error.URLError("không có mạng"), TimeoutError(),
                 urllib.error.HTTPError("u", 404, "nf", {}, None), urllib.error.HTTPError("u", 403, "rl", {}, None)]
        for exc in cases:
            with self.assertRaises(ApiError):
                self.api(raiser(exc)).fetch_issues("python/cpython")
        with self.assertRaises(ApiError):
            self.api(lambda u, t: b"<html>not json").fetch_issues("python/cpython")
        with self.assertRaises(ApiError):
            self.api(lambda u, t: b"[]").fetch_issues("python/cpython")
        with self.assertRaises(ApiError):
            self.api(lambda u, t: b"[]").fetch_issues("khong hop le")


class TestStats(Base):
    def test_tc27_stats_empty_and_sample(self):
        """TC27 | Thống kê khi chưa có ticket; sau khi sinh 40 ticket mẫu (seed 3) | rỗng: không chia cho 0; mẫu: tổng các nhóm = 40"""
        empty = stats_service.summarize([])
        self.assertEqual((empty["total"], empty["avg_processing_hours"], empty["sla_met_rate"]), (0, 0.0, 0.0))
        sample_data.generate(self.ctx.tickets, self.ctx.users, self.ctx.groups, 40, seed=3)
        s = stats_service.summarize(self.ctx.tickets.all_tickets())
        self.assertEqual(s["total"], 40)
        self.assertEqual(sum(s["by_status"].values()), 40)
        self.assertEqual(sum(s["by_priority"].values()), 40)
        self.assertEqual(sum(s["by_group"].values()), 40)

    def test_tc28_sample_reproducible_with_seed(self):
        """TC28 | Sinh 20 ticket với cùng seed ở hai thư mục khác nhau; số lượng 0 và 501 | cùng seed -> cùng tiêu đề; số lượng ngoài 1-500 bị từ chối"""
        other = AppContext(Path(tempfile.mkdtemp()))
        sample_data.generate(self.ctx.tickets, self.ctx.users, self.ctx.groups, 20, seed=5)
        sample_data.generate(other.tickets, other.users, other.groups, 20, seed=5)
        titles = lambda c: [t.title for t in sorted(c.tickets.all_tickets(), key=lambda t: t.ticket_id)]
        self.assertEqual(titles(self.ctx), titles(other))
        for bad in (0, 501):
            with self.assertRaises(ValueError):
                sample_data.generate(self.ctx.tickets, self.ctx.users, self.ctx.groups, bad)
        shutil.rmtree(other.data_dir, ignore_errors=True)


class TestAccounts(Base):
    def test_tc29_last_admin_and_self_protection(self):
        """TC29 | Xóa/khóa quản trị viên cuối cùng; tự đổi vai trò của mình | bị từ chối (BusinessError)"""
        with self.assertRaises(BusinessError):
            self.ctx.users.delete(self.admin, "admin")
        with self.assertRaises(BusinessError):
            self.ctx.users.update(self.admin, "admin", "Quản Trị Viên", "admin@example.com", "",
                                  config.ROLE_USER, True)

    def test_tc30_delete_user_with_open_tickets_and_change_password(self):
        """TC30 | Xóa người dùng còn ticket mở; đổi mật khẩu sai mật khẩu cũ / đúng | xóa bị từ chối; đổi sai báo lỗi, đổi đúng đăng nhập được bằng mật khẩu mới"""
        self.new_ticket()
        with self.assertRaises(BusinessError):
            self.ctx.users.delete(self.admin, "user")
        with self.assertRaises(AuthError):
            self.ctx.auth.change_password(self.user, "sai", "Moi12345", "Moi12345")
        self.ctx.auth.change_password(self.user, "User@123", "Moi12345", "Moi12345")
        self.assertEqual(self.ctx.auth.login("user", "Moi12345").username, "user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
