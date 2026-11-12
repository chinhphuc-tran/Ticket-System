"""Lớp người dùng: lớp trừu tượng User và các lớp con theo vai trò.

Minh họa: kế thừa, lớp trừu tượng (ABC), ghi đè phương thức (can, ticket_scope)
và đa hình (mỗi vai trò xử lý quyền theo cách riêng).
"""
from abc import ABC, abstractmethod
from datetime import datetime

import config
from models.feedback import to_datetime
from utils import validators as v
from utils.exceptions import ValidationError

# Danh sách quyền (permission) của hệ thống
PERM_TICKET_CREATE = "ticket.create"
PERM_TICKET_EDIT_OWN = "ticket.edit_own"
PERM_TICKET_EDIT_ANY = "ticket.edit_any"
PERM_TICKET_ASSIGN = "ticket.assign"
PERM_TICKET_STATUS = "ticket.status"
PERM_TICKET_DELETE = "ticket.delete"
PERM_FEEDBACK = "ticket.feedback"
PERM_INTERNAL_NOTE = "ticket.internal_note"
PERM_STATS = "stats.view"
PERM_EXPORT = "report.export"
PERM_USER_MANAGE = "user.manage"
PERM_GROUP_MANAGE = "group.manage"
PERM_API_IMPORT = "api.import"
PERM_DATA_ADMIN = "data.admin"       # sao lưu/khôi phục/sinh dữ liệu mẫu
PERM_VIEW_LOG = "log.view"

ALL_PERMISSIONS = frozenset({
    PERM_TICKET_CREATE, PERM_TICKET_EDIT_OWN, PERM_TICKET_EDIT_ANY, PERM_TICKET_ASSIGN,
    PERM_TICKET_STATUS, PERM_TICKET_DELETE, PERM_FEEDBACK, PERM_INTERNAL_NOTE, PERM_STATS,
    PERM_EXPORT, PERM_USER_MANAGE, PERM_GROUP_MANAGE, PERM_API_IMPORT, PERM_DATA_ADMIN,
    PERM_VIEW_LOG,
})

SCOPE_ALL = "all"
SCOPE_OWN = "own"


class User(ABC):
    """Lớp cơ sở trừu tượng cho mọi loại tài khoản."""

    ROLE = ""
    PERMISSIONS = frozenset()

    def __init__(self, username, full_name, email, phone, password_hash, salt,
                 active=True, created_at=None):
        self.username = username
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self._set_credentials(password_hash, salt)
        self.active = bool(active)
        self.created_at = to_datetime(created_at)

    # --- thuộc tính có kiểm tra dữ liệu (đóng gói) -----------------------
    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = v.validate_username(value)

    @property
    def full_name(self) -> str:
        return self._full_name

    @full_name.setter
    def full_name(self, value: str) -> None:
        self._full_name = v.validate_text(value, "Họ tên", 2, 60)

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        self._email = v.validate_email(value)

    @property
    def phone(self) -> str:
        return self._phone

    @phone.setter
    def phone(self, value: str) -> None:
        self._phone = v.validate_phone(value, required=False)

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def salt(self) -> str:
        return self._salt

    def _set_credentials(self, password_hash: str, salt: str) -> None:
        if not password_hash or not salt:
            raise ValidationError("Tài khoản thiếu thông tin mật khẩu đã băm.")
        self._password_hash = password_hash
        self._salt = salt

    def set_credentials(self, password_hash: str, salt: str) -> None:
        """Cập nhật mật khẩu (đã băm) - chỉ dùng bởi AuthService."""
        self._set_credentials(password_hash, salt)

    # --- vai trò / quyền -------------------------------------------------
    @property
    def role(self) -> str:
        return self.ROLE

    @property
    def role_label(self) -> str:
        return config.ROLE_LABELS.get(self.ROLE, self.ROLE)

    def can(self, permission: str) -> bool:
        """Kiểm tra quyền. Lớp con có thể ghi đè."""
        return permission in self.PERMISSIONS

    @abstractmethod
    def ticket_scope(self) -> str:
        """Phạm vi ticket được xem: SCOPE_ALL hoặc SCOPE_OWN."""

    @property
    def is_staff(self) -> bool:
        return self.ticket_scope() == SCOPE_ALL

    # --- chuyển đổi dữ liệu ----------------------------------------------
    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "role": self.ROLE,
            "password_hash": self.password_hash,
            "salt": self.salt,
            "active": self.active,
            "created_at": self.created_at.strftime(config.DATETIME_FMT),
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.username!r})"


class AdminUser(User):
    ROLE = config.ROLE_ADMIN
    PERMISSIONS = ALL_PERMISSIONS

    def can(self, permission: str) -> bool:      # ghi đè: quản trị viên có mọi quyền
        return True

    def ticket_scope(self) -> str:
        return SCOPE_ALL


class AgentUser(User):
    ROLE = config.ROLE_AGENT
    PERMISSIONS = frozenset({
        PERM_TICKET_CREATE, PERM_TICKET_EDIT_ANY, PERM_TICKET_ASSIGN, PERM_TICKET_STATUS,
        PERM_FEEDBACK, PERM_INTERNAL_NOTE, PERM_STATS, PERM_EXPORT,
    })

    def ticket_scope(self) -> str:
        return SCOPE_ALL


class EndUser(User):
    ROLE = config.ROLE_USER
    PERMISSIONS = frozenset({PERM_TICKET_CREATE, PERM_TICKET_EDIT_OWN, PERM_FEEDBACK})

    def ticket_scope(self) -> str:
        return SCOPE_OWN


ROLE_CLASSES = {
    config.ROLE_ADMIN: AdminUser,
    config.ROLE_AGENT: AgentUser,
    config.ROLE_USER: EndUser,
}


def user_from_dict(data: dict) -> User:
    """Factory: tạo đúng lớp con theo trường `role`."""
    cls = ROLE_CLASSES.get(data.get("role"))
    if cls is None:
        raise ValidationError(f"Vai trò không hợp lệ: {data.get('role')!r}.")
    return cls(
        username=data.get("username", ""),
        full_name=data.get("full_name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        password_hash=data.get("password_hash", ""),
        salt=data.get("salt", ""),
        active=data.get("active", True),
        created_at=data.get("created_at"),
    )


def new_user(role: str, username, full_name, email, phone, password_hash, salt) -> User:
    """Tạo tài khoản mới theo vai trò."""
    cls = ROLE_CLASSES.get(role)
    if cls is None:
        raise ValidationError(f"Vai trò không hợp lệ: {role!r}.")
    return cls(username, full_name, email, phone, password_hash, salt,
               active=True, created_at=datetime.now())
