"""Lớp Ticket: một yêu cầu hỗ trợ / sự cố CNTT, kèm SLA và lịch sử xử lý."""
from datetime import datetime, timedelta
from typing import List, Optional

import config
from models.feedback import Feedback, to_datetime
from utils import validators as v
from utils.exceptions import BusinessError

# Quy trình chuyển trạng thái hợp lệ
ALLOWED_TRANSITIONS = {
    "new": ("in_progress", "closed"),
    "in_progress": ("waiting", "resolved"),
    "waiting": ("in_progress", "resolved", "closed"),
    "resolved": ("closed", "in_progress"),
    "closed": (),
}


class HistoryEntry:
    """Một dòng trong nhật ký sự kiện của ticket."""

    def __init__(self, actor: str, action: str, detail: str = "", time=None):
        self.actor = actor
        self.action = action
        self.detail = detail
        self.time = to_datetime(time)

    def to_dict(self) -> dict:
        return {"actor": self.actor, "action": self.action, "detail": self.detail,
                "time": self.time.strftime(config.DATETIME_FMT)}

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(data.get("actor", "?"), data.get("action", "?"),
                   data.get("detail", ""), data.get("time"))


class Ticket:
    def __init__(self, ticket_id, title, description, requester, category, priority,
                 group_id="", assignee="", status="new", created_at=None,
                 updated_at=None, resolved_at=None, attachment="",
                 feedbacks: Optional[List[Feedback]] = None,
                 history: Optional[List[HistoryEntry]] = None,
                 source="manual", external_ref=""):
        self.ticket_id = ticket_id
        self.title = title
        self.description = description
        self.requester = requester
        self.category = category
        self.priority = priority
        self.group_id = group_id
        self.assignee = assignee
        self.attachment = attachment
        self._status = v.validate_choice(status, config.STATUS_INFO, "Trạng thái")
        self.created_at = to_datetime(created_at)
        self.updated_at = to_datetime(updated_at, default=self.created_at)
        self.resolved_at = to_datetime(resolved_at) if resolved_at else None
        self.feedbacks: List[Feedback] = list(feedbacks or [])
        self.history: List[HistoryEntry] = list(history or [])
        self.source = source or "manual"
        self.external_ref = external_ref or ""

    # --- thuộc tính có kiểm tra ------------------------------------------
    @property
    def ticket_id(self) -> str:
        return self._ticket_id

    @ticket_id.setter
    def ticket_id(self, value: str) -> None:
        self._ticket_id = v.validate_ticket_id(value)

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = v.clean_text(v.validate_text(value, "Tiêu đề", 5, 120), single_line=True)

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = v.validate_text(value, "Mô tả", 10, 2000)

    @property
    def requester(self) -> str:
        return self._requester

    @requester.setter
    def requester(self, value: str) -> None:
        self._requester = v.validate_text(value, "Người yêu cầu", 1, 40)

    @property
    def category(self) -> str:
        return self._category

    @category.setter
    def category(self, value: str) -> None:
        self._category = v.validate_choice(value, config.CATEGORIES, "Phân loại")

    @property
    def priority(self) -> str:
        return self._priority

    @priority.setter
    def priority(self, value: str) -> None:
        self._priority = v.validate_choice(value, config.PRIORITY_INFO, "Mức ưu tiên")

    @property
    def group_id(self) -> str:
        return self._group_id

    @group_id.setter
    def group_id(self, value: str) -> None:
        self._group_id = (value or "").strip()

    @property
    def assignee(self) -> str:
        return self._assignee

    @assignee.setter
    def assignee(self, value: str) -> None:
        self._assignee = (value or "").strip()

    @property
    def attachment(self) -> str:
        return self._attachment

    @attachment.setter
    def attachment(self, value: str) -> None:
        self._attachment = v.validate_text(value, "Tệp đính kèm", 0, 260, required=False)

    @property
    def status(self) -> str:
        return self._status

    # --- hiển thị ---------------------------------------------------------
    @property
    def status_label(self) -> str:
        return config.STATUS_INFO[self._status]["label"]

    @property
    def priority_label(self) -> str:
        return config.PRIORITY_INFO[self._priority]["label"]

    @property
    def is_open(self) -> bool:
        return self._status in config.OPEN_STATUSES

    # --- SLA ---------------------------------------------------------------
    @property
    def sla_hours(self) -> int:
        return config.PRIORITY_INFO[self._priority]["sla_hours"]

    @property
    def due_at(self) -> datetime:
        return self.created_at + timedelta(hours=self.sla_hours)

    def _finished_at(self) -> Optional[datetime]:
        if self._status in config.FINISHED_STATUSES:
            return self.resolved_at or self.updated_at
        return None

    def sla_state(self, now: Optional[datetime] = None) -> str:
        """ok | warning | breached (đang mở) hoặc met | missed (đã xong)."""
        now = now or datetime.now()
        finished = self._finished_at()
        if finished is not None:
            return "met" if finished <= self.due_at else "missed"
        if now > self.due_at:
            return "breached"
        total = (self.due_at - self.created_at).total_seconds()
        elapsed = (now - self.created_at).total_seconds()
        if total > 0 and elapsed >= total * config.SLA_WARNING_RATIO:
            return "warning"
        return "ok"

    def sla_ratio(self, now: Optional[datetime] = None) -> float:
        """Tỷ lệ thời gian SLA đã dùng (0..1.5), dùng cho thanh tiến độ."""
        now = now or datetime.now()
        end = self._finished_at() or now
        total = (self.due_at - self.created_at).total_seconds()
        if total <= 0:
            return 1.5
        return max(0.0, min(1.5, (end - self.created_at).total_seconds() / total))

    def remaining_hours(self, now: Optional[datetime] = None) -> float:
        """Số giờ còn lại đến hạn SLA (âm nếu đã quá hạn)."""
        now = now or datetime.now()
        return (self.due_at - now).total_seconds() / 3600

    def processing_hours(self) -> Optional[float]:
        """Thời gian xử lý (giờ) từ lúc tạo đến lúc giải quyết; None nếu chưa xong."""
        finished = self._finished_at()
        if finished is None:
            return None
        return max(0.0, (finished - self.created_at).total_seconds() / 3600)

    # --- nghiệp vụ ---------------------------------------------------------
    def allowed_next_statuses(self) -> tuple:
        return ALLOWED_TRANSITIONS[self._status]

    def add_history(self, actor: str, action: str, detail: str = "") -> None:
        self.history.append(HistoryEntry(actor, action, detail))
        self.updated_at = datetime.now().replace(microsecond=0)

    def change_status(self, new_status: str, actor: str, note: str = "") -> None:
        """Chuyển trạng thái theo quy trình; ném BusinessError nếu không hợp lệ."""
        v.validate_choice(new_status, config.STATUS_INFO, "Trạng thái")
        if new_status not in ALLOWED_TRANSITIONS[self._status]:
            raise BusinessError(
                f"Không thể chuyển từ '{self.status_label}' sang "
                f"'{config.STATUS_INFO[new_status]['label']}'.")
        old_label = self.status_label
        now = datetime.now().replace(microsecond=0)
        self._status = new_status
        if new_status in config.FINISHED_STATUSES:
            if self.resolved_at is None:
                self.resolved_at = now
        else:
            self.resolved_at = None      # mở lại ticket
        detail = f"{old_label} -> {self.status_label}"
        if note:
            detail += f" ({v.clean_text(note, single_line=True)[:200]})"
        self.add_history(actor, "Đổi trạng thái", detail)

    def assign(self, assignee: str, group_id: str, actor: str) -> None:
        self.assignee = assignee
        self.group_id = group_id
        self.add_history(actor, "Phân công", f"Nhóm: {group_id or '-'}, người xử lý: {assignee or '-'}")

    def add_feedback(self, author: str, content: str, internal: bool = False) -> Feedback:
        fb = Feedback(author, content, internal=internal)
        self.feedbacks.append(fb)
        self.add_history(author, "Ghi chú nội bộ" if internal else "Phản hồi",
                         v.clean_text(content, single_line=True)[:80])
        return fb

    def visible_feedbacks(self, include_internal: bool) -> List[Feedback]:
        return [f for f in self.feedbacks if include_internal or not f.internal]

    # --- chuyển đổi dữ liệu -----------------------------------------------
    def to_dict(self) -> dict:
        fmt = config.DATETIME_FMT
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "requester": self.requester,
            "category": self.category,
            "priority": self.priority,
            "group_id": self.group_id,
            "assignee": self.assignee,
            "status": self.status,
            "created_at": self.created_at.strftime(fmt),
            "updated_at": self.updated_at.strftime(fmt),
            "resolved_at": self.resolved_at.strftime(fmt) if self.resolved_at else None,
            "attachment": self.attachment,
            "source": self.source,
            "external_ref": self.external_ref,
            "feedbacks": [f.to_dict() for f in self.feedbacks],
            "history": [h.to_dict() for h in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ticket":
        return cls(
            ticket_id=data.get("ticket_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            requester=data.get("requester", ""),
            category=data.get("category", ""),
            priority=data.get("priority", ""),
            group_id=data.get("group_id", ""),
            assignee=data.get("assignee", ""),
            status=data.get("status", "new"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            resolved_at=data.get("resolved_at"),
            attachment=data.get("attachment", ""),
            feedbacks=[Feedback.from_dict(f) for f in data.get("feedbacks", [])],
            history=[HistoryEntry.from_dict(h) for h in data.get("history", [])],
            source=data.get("source", "manual"),
            external_ref=data.get("external_ref", ""),
        )

    def __repr__(self) -> str:
        return f"Ticket({self.ticket_id}, {self.status}, {self.priority})"
