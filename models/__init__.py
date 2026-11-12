"""Các lớp dữ liệu (model) của hệ thống quản lý sự cố CNTT."""
from models.feedback import Feedback
from models.group import SupportGroup
from models.ticket import ALLOWED_TRANSITIONS, HistoryEntry, Ticket
from models.user import AdminUser, AgentUser, EndUser, User, user_from_dict

__all__ = [
    "Feedback", "SupportGroup", "Ticket", "HistoryEntry", "ALLOWED_TRANSITIONS",
    "User", "AdminUser", "AgentUser", "EndUser", "user_from_dict",
]
