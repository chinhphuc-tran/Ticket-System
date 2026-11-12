"""Lớp quản lý ticket: CRUD, tìm kiếm/lọc/sắp xếp, phân công, đổi trạng thái, phản hồi."""
import difflib
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import config
from models.ticket import Ticket
from models.user import (PERM_API_IMPORT, PERM_FEEDBACK, PERM_INTERNAL_NOTE, PERM_TICKET_ASSIGN,
                         PERM_TICKET_CREATE, PERM_TICKET_DELETE, PERM_TICKET_EDIT_ANY,
                         PERM_TICKET_EDIT_OWN, PERM_TICKET_STATUS, User)
from services.activity_logger import ActivityLogger
from services.group_manager import GroupManager
from services.json_store import JsonStore
from services.user_manager import UserManager
from utils import validators as v
from utils.exceptions import (BusinessError, NotFoundError, PermissionDenied,
                              StorageError, ValidationError)

UNASSIGNED = "__unassigned__"      # giá trị đặc biệt: lọc ticket chưa có người xử lý

SORT_KEYS: Dict[str, Callable[[Ticket], object]] = {
    "ticket_id": lambda t: t.ticket_id,
    "title": lambda t: t.title.lower(),
    "priority": lambda t: config.PRIORITY_INFO[t.priority]["rank"],
    "status": lambda t: list(config.STATUS_INFO).index(t.status),
    "created_at": lambda t: t.created_at,
    "sla": lambda t: t.remaining_hours(),
    "group": lambda t: t.group_id,
    "assignee": lambda t: t.assignee.lower(),
    "requester": lambda t: t.requester.lower(),
}


class TicketManager:
    def __init__(self, store: JsonStore, logger: ActivityLogger, users: UserManager,
                 groups: GroupManager, attachment_dir: Optional[Path] = None):
        self.store = store
        self.logger = logger
        self.users = users
        self.groups = groups
        self.attachment_dir = Path(attachment_dir) if attachment_dir else config.ATTACHMENT_DIR
        self._tickets: Dict[str, Ticket] = {}
        self.skipped = 0
        self.reload()

    # ------------------------------------------------------------------
    # Lưu trữ
    # ------------------------------------------------------------------
    def reload(self) -> None:
        raw = self.store.load()
        self._tickets, self.skipped = {}, 0
        if not isinstance(raw, list):
            raw = []
        for item in raw:
            try:
                ticket = Ticket.from_dict(item)
                self._tickets[ticket.ticket_id] = ticket
            except (ValidationError, AttributeError, TypeError) as exc:
                self.skipped += 1
                self.logger.log("system", "SKIP_TICKET", str(exc))

    def _commit(self) -> None:
        try:
            self.store.save([t.to_dict() for t in sorted(self._tickets.values(), key=lambda t: t.ticket_id)])
        except StorageError:
            self.reload()     # không để bộ nhớ lệch với file khi ghi thất bại
            raise

    def next_id(self) -> str:
        numbers = [int(tid[2:]) for tid in self._tickets]
        return f"TK{(max(numbers) + 1 if numbers else 1):06d}"

    # ------------------------------------------------------------------
    # Kiểm tra quyền
    # ------------------------------------------------------------------
    def _can_view(self, actor: User, ticket: Ticket) -> bool:
        return actor.is_staff or ticket.requester == actor.username

    def _staff_or_owner_edit(self, actor: User, ticket: Ticket) -> None:
        if actor.can(PERM_TICKET_EDIT_ANY):
            return
        if actor.can(PERM_TICKET_EDIT_OWN) and ticket.requester == actor.username:
            if ticket.status != "new":
                raise BusinessError("Chỉ được sửa ticket khi còn ở trạng thái 'Mới'.")
            return
        raise PermissionDenied("Bạn không có quyền sửa ticket này.")

    # ------------------------------------------------------------------
    # Truy vấn
    # ------------------------------------------------------------------
    def get(self, actor: User, ticket_id: str) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise NotFoundError(f"Không tìm thấy ticket '{ticket_id}'.")
        if not self._can_view(actor, ticket):
            raise PermissionDenied("Bạn không có quyền xem ticket này.")
        return ticket

    def all_tickets(self) -> List[Ticket]:
        return list(self._tickets.values())

    def list_for(self, actor: User) -> List[Ticket]:
        return [t for t in self._tickets.values() if self._can_view(actor, t)]

    def open_count_for_user(self, username: str) -> int:
        """Số ticket đang mở mà tài khoản là người yêu cầu hoặc người xử lý."""
        return sum(1 for t in self._tickets.values()
                   if t.is_open and (t.requester == username or t.assignee == username))

    def group_in_use(self, group_id: str) -> bool:
        return any(t.group_id == group_id for t in self._tickets.values())

    def search(self, actor: User, keyword: str = "", status: Optional[str] = None,
               priority: Optional[str] = None, group_id: Optional[str] = None,
               assignee: Optional[str] = None, date_from: Optional[date] = None,
               date_to: Optional[date] = None, overdue_only: bool = False,
               fuzzy: bool = False, sort_by: str = "created_at",
               descending: bool = True) -> List[Ticket]:
        """Tìm kiếm/lọc theo nhiều tiêu chí và sắp xếp. Tham số None = không lọc."""
        v.validate_date_range(date_from, date_to)
        if sort_by not in SORT_KEYS:
            raise ValidationError(f"Không hỗ trợ sắp xếp theo '{sort_by}'.")
        kw = v.clean_text(keyword or "", single_line=True).lower()
        now = datetime.now()
        result = []
        for t in self.list_for(actor):
            if status and t.status != status:
                continue
            if priority and t.priority != priority:
                continue
            if group_id and t.group_id != group_id:
                continue
            if assignee == UNASSIGNED:
                if t.assignee:
                    continue
            elif assignee and t.assignee != assignee:
                continue
            if date_from and t.created_at.date() < date_from:
                continue
            if date_to and t.created_at.date() > date_to:
                continue
            if overdue_only and t.sla_state(now) not in ("breached", "missed"):
                continue
            if kw and not self._matches(t, kw, fuzzy):
                continue
            result.append(t)
        result.sort(key=SORT_KEYS[sort_by], reverse=descending)
        return result

    @staticmethod
    def _matches(ticket: Ticket, kw: str, fuzzy: bool) -> bool:
        haystack = " ".join([ticket.ticket_id, ticket.title, ticket.description,
                             ticket.requester, ticket.assignee]).lower()
        if kw in haystack:
            return True
        if not fuzzy:
            return False
        # Tìm gần đúng: so khớp từng từ của từ khóa với từng từ trong tiêu đề/mô tả
        words = set(haystack.replace(",", " ").replace(".", " ").split())
        return all(difflib.get_close_matches(token, words, n=1, cutoff=0.75) for token in kw.split())

    # ------------------------------------------------------------------
    # Tạo / sửa / xóa
    # ------------------------------------------------------------------
    def create(self, actor: User, title: str, description: str, category: str, priority: str,
               requester: Optional[str] = None, attachment_src: str = "") -> Ticket:
        if not actor.can(PERM_TICKET_CREATE):
            raise PermissionDenied("Bạn không có quyền tạo ticket.")
        owner = actor.username
        if requester and requester != actor.username:
            if not actor.is_staff:
                raise PermissionDenied("Chỉ nhân viên hỗ trợ mới được tạo ticket thay người khác.")
            owner = self.users.get(requester).username

        ticket_id = self.next_id()
        group_id = config.CATEGORY_DEFAULT_GROUP.get(category, "")
        if group_id and not self.groups.find(group_id):
            group_id = ""
        ticket = Ticket(ticket_id, title, description, owner, category, priority, group_id=group_id)
        ticket.add_history(actor.username, "Tạo ticket", f"Ưu tiên {ticket.priority_label}")
        if attachment_src:
            ticket.attachment = self._store_attachment(ticket_id, attachment_src)
            ticket.add_history(actor.username, "Đính kèm tệp", ticket.attachment)
        self._tickets[ticket_id] = ticket
        self._commit()
        self.logger.log(actor.username, "CREATE_TICKET", ticket_id)
        return ticket

    def update(self, actor: User, ticket_id: str, title: str, description: str, category: str,
               priority: str, attachment_src: str = "") -> Ticket:
        ticket = self.get(actor, ticket_id)
        self._staff_or_owner_edit(actor, ticket)
        # Kiểm tra dữ liệu mới bằng ticket tạm trước khi áp dụng
        Ticket(ticket.ticket_id, title, description, ticket.requester, category, priority)
        ticket.title, ticket.description = title, description
        changed_priority = ticket.priority != priority
        ticket.category, ticket.priority = category, priority
        if attachment_src:
            ticket.attachment = self._store_attachment(ticket_id, attachment_src)
        ticket.add_history(actor.username, "Cập nhật", "Priority đổi" if changed_priority else "Sửa thông tin")
        self._commit()
        self.logger.log(actor.username, "UPDATE_TICKET", ticket_id)
        return ticket

    def delete(self, actor: User, ticket_id: str) -> None:
        if not actor.can(PERM_TICKET_DELETE):
            raise PermissionDenied("Chỉ quản trị viên mới được xóa ticket.")
        ticket = self.get(actor, ticket_id)
        if ticket.status in ("in_progress", "waiting"):
            raise BusinessError("Không thể xóa ticket đang được xử lý. "
                                "Hãy giải quyết hoặc đóng ticket trước.")
        del self._tickets[ticket_id]
        self._commit()
        self.logger.log(actor.username, "DELETE_TICKET", ticket_id)

    # ------------------------------------------------------------------
    # Phân công / trạng thái / phản hồi
    # ------------------------------------------------------------------
    def assign(self, actor: User, ticket_id: str, assignee: str, group_id: str) -> Ticket:
        if not actor.can(PERM_TICKET_ASSIGN):
            raise PermissionDenied("Bạn không có quyền phân công ticket.")
        ticket = self.get(actor, ticket_id)
        if not ticket.is_open:
            raise BusinessError("Không thể phân công ticket đã giải quyết hoặc đã đóng.")
        if group_id:
            self.groups.get(group_id)
        if assignee:
            person = self.users.get(assignee)
            if not person.is_staff or not person.active:
                raise ValidationError("Người xử lý phải là kỹ thuật viên/quản trị viên đang hoạt động.")
            if actor.role == config.ROLE_AGENT and person.username != actor.username:
                raise PermissionDenied("Kỹ thuật viên chỉ được nhận xử lý ticket cho chính mình.")
            assignee = person.username
        ticket.assign(assignee, group_id, actor.username)
        self._commit()
        self.logger.log(actor.username, "ASSIGN_TICKET", f"{ticket_id} -> {assignee or '-'}")
        return ticket

    def allowed_statuses(self, actor: User, ticket: Ticket) -> List[str]:
        """Các trạng thái mà `actor` được phép chuyển ticket sang."""
        nxt = list(ticket.allowed_next_statuses())
        if actor.can(PERM_TICKET_STATUS):
            return nxt
        if ticket.requester == actor.username and ticket.status == "resolved":
            return [s for s in nxt if s in ("closed", "in_progress")]   # xác nhận hoặc mở lại
        return []

    def change_status(self, actor: User, ticket_id: str, new_status: str, note: str = "") -> Ticket:
        ticket = self.get(actor, ticket_id)
        if new_status not in self.allowed_statuses(actor, ticket):
            if new_status in ticket.allowed_next_statuses():
                raise PermissionDenied("Bạn không có quyền chuyển ticket sang trạng thái này.")
            ticket.change_status(new_status, actor.username)   # ném BusinessError với thông báo rõ ràng
        if new_status == "in_progress" and ticket.status == "new" and not ticket.assignee and actor.is_staff:
            ticket.assignee = actor.username                   # nhận xử lý khi bắt đầu
        ticket.change_status(new_status, actor.username, note)
        self._commit()
        self.logger.log(actor.username, "STATUS_TICKET", f"{ticket_id} -> {new_status}")
        return ticket

    def add_feedback(self, actor: User, ticket_id: str, content: str, internal: bool = False) -> Ticket:
        if not actor.can(PERM_FEEDBACK):
            raise PermissionDenied("Bạn không có quyền phản hồi.")
        ticket = self.get(actor, ticket_id)
        if internal and not actor.can(PERM_INTERNAL_NOTE):
            raise PermissionDenied("Bạn không có quyền tạo ghi chú nội bộ.")
        if ticket.status == "closed":
            raise BusinessError("Ticket đã đóng, không thể thêm phản hồi.")
        ticket.add_feedback(actor.username, content, internal)
        self._commit()
        self.logger.log(actor.username, "FEEDBACK", ticket_id)
        return ticket

    # ------------------------------------------------------------------
    # Tệp đính kèm
    # ------------------------------------------------------------------
    def _store_attachment(self, ticket_id: str, src: str) -> str:
        """Sao chép tệp vào thư mục đính kèm của ứng dụng; trả về tên tệp lưu."""
        source = Path(src)
        try:
            if not source.is_file():
                raise ValidationError(f"Không tìm thấy tệp đính kèm: {source.name}")
            size_mb = source.stat().st_size / (1024 * 1024)
            if size_mb > config.MAX_ATTACHMENT_MB:
                raise ValidationError(f"Tệp đính kèm quá lớn ({size_mb:.1f} MB). "
                                      f"Tối đa {config.MAX_ATTACHMENT_MB} MB.")
            self.attachment_dir.mkdir(parents=True, exist_ok=True)
            stored = f"{ticket_id}_{v.safe_filename(source.name)}"
            shutil.copy2(source, self.attachment_dir / stored)
            return stored
        except OSError as exc:
            raise StorageError(f"Không sao chép được tệp đính kèm: {exc}") from exc

    # ------------------------------------------------------------------
    # Nhập hàng loạt (API / dữ liệu mẫu)
    # ------------------------------------------------------------------
    def bulk_add(self, tickets: Iterable[Ticket]) -> int:
        count = 0
        for t in tickets:
            if t.ticket_id in self._tickets:
                continue
            self._tickets[t.ticket_id] = t
            count += 1
        if count:
            self._commit()
        return count

    def import_external(self, actor: User, records: List[dict]) -> Tuple[int, int]:
        """Nhập các bản ghi đã làm sạch từ API. Trả về (số thêm mới, số bỏ qua)."""
        if not actor.can(PERM_API_IMPORT):
            raise PermissionDenied("Bạn không có quyền nhập dữ liệu từ API.")
        known = {t.external_ref for t in self._tickets.values() if t.external_ref}
        added, skipped = 0, 0
        requester = actor.username
        for rec in records:
            ref = rec.get("external_ref", "")
            if ref and ref in known:
                skipped += 1
                continue
            try:
                ticket = Ticket(self.next_id(), rec.get("title", ""), rec.get("description", ""),
                                requester, rec.get("category", "Khác"), rec.get("priority", "medium"),
                                group_id=config.CATEGORY_DEFAULT_GROUP.get(rec.get("category", "Khác"), ""),
                                created_at=rec.get("created_at"), source="api", external_ref=ref)
            except ValidationError as exc:
                skipped += 1
                self.logger.log(actor.username, "IMPORT_SKIP", f"{ref}: {exc}")
                continue
            ticket.add_history(actor.username, "Nhập từ API", ref)
            if rec.get("status") == "closed":
                ticket.change_status("in_progress", "system")
                ticket.change_status("resolved", "system", "đồng bộ từ nguồn")
            self._tickets[ticket.ticket_id] = ticket
            known.add(ref)
            added += 1
        if added:
            self._commit()
        self.logger.log(actor.username, "IMPORT_API", f"thêm {added}, bỏ qua {skipped}")
        return added, skipped
