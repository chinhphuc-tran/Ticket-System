"""Lớp quản lý tài khoản người dùng (CRUD, băm mật khẩu, ràng buộc)."""
import hashlib
import hmac
import secrets
from typing import Callable, Dict, List, Optional, Tuple

import config
from models.user import PERM_USER_MANAGE, User, new_user, user_from_dict
from services.activity_logger import ActivityLogger
from services.json_store import JsonStore
from utils import validators as v
from utils.exceptions import (BusinessError, NotFoundError, PermissionDenied,
                              StorageError, ValidationError)

# Tài khoản demo tạo ở lần chạy đầu tiên (nên đổi mật khẩu sau khi đăng nhập)
DEFAULT_ACCOUNTS = [
    (config.ROLE_ADMIN, "admin", "Quản Trị Viên", "admin@example.com", "0900000001", "Admin@123"),
    (config.ROLE_AGENT, "agent", "Kỹ Thuật Viên", "agent@example.com", "0900000002", "Agent@123"),
    (config.ROLE_USER, "user", "Người Dùng Mẫu", "user@example.com", "0900000003", "User@123"),
]


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """Băm mật khẩu bằng PBKDF2-HMAC-SHA256 với salt ngẫu nhiên. Trả về (hash, salt)."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, config.PASSWORD_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    candidate, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, password_hash)


class UserManager:
    def __init__(self, store: JsonStore, logger: ActivityLogger):
        self.store = store
        self.logger = logger
        # Hàm do context gắn vào: số ticket đang mở liên quan đến một tài khoản
        self.open_ticket_count: Callable[[str], int] = lambda username: 0
        self._users: Dict[str, User] = {}
        self.skipped = 0
        self.reload()
        self.ensure_defaults()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        raw = self.store.load()
        self._users, self.skipped = {}, 0
        if not isinstance(raw, list):
            raw = []
        for item in raw:
            try:
                user = user_from_dict(item)
                self._users[user.username.lower()] = user
            except (ValidationError, AttributeError) as exc:
                self.skipped += 1
                self.logger.log("system", "SKIP_USER", str(exc))

    def _commit(self) -> None:
        try:
            self.store.save([u.to_dict() for u in self.list()])
        except StorageError:
            self.reload()
            raise

    def ensure_defaults(self) -> None:
        """Tạo tài khoản demo nếu hệ thống chưa có người dùng nào."""
        if self._users:
            return
        for role, username, full_name, email, phone, password in DEFAULT_ACCOUNTS:
            pw_hash, salt = hash_password(password)
            user = new_user(role, username, full_name, email, phone, pw_hash, salt)
            self._users[user.username.lower()] = user
        self._commit()
        self.logger.log("system", "SEED_USERS", "Đã tạo tài khoản mặc định")

    @staticmethod
    def _require(actor: User) -> None:
        if not actor.can(PERM_USER_MANAGE):
            raise PermissionDenied("Bạn không có quyền quản lý tài khoản.")

    # ------------------------------------------------------------------
    # Truy vấn
    # ------------------------------------------------------------------
    def list(self, role: Optional[str] = None) -> List[User]:
        users = sorted(self._users.values(), key=lambda u: u.username.lower())
        return [u for u in users if role is None or u.role == role]

    def staff(self) -> List[User]:
        """Tài khoản có thể được phân công xử lý ticket (đang hoạt động)."""
        return [u for u in self.list() if u.is_staff and u.active]

    def find(self, username: str) -> Optional[User]:
        return self._users.get((username or "").strip().lower())

    def get(self, username: str) -> User:
        user = self.find(username)
        if user is None:
            raise NotFoundError(f"Không tìm thấy tài khoản '{username}'.")
        return user

    def search(self, keyword: str = "", role: Optional[str] = None) -> List[User]:
        kw = (keyword or "").strip().lower()
        return [u for u in self.list(role)
                if not kw or kw in u.username.lower() or kw in u.full_name.lower() or kw in u.email.lower()]

    # ------------------------------------------------------------------
    # Thêm / sửa / xóa
    # ------------------------------------------------------------------
    def register(self, username, full_name, email, phone, password, role=config.ROLE_USER) -> User:
        """Tạo tài khoản (đăng ký công khai luôn là Người dùng thông thường)."""
        username = v.validate_username(username)
        if self.find(username):
            raise ValidationError(f"Tên đăng nhập '{username}' đã tồn tại.")
        v.validate_password(password)
        pw_hash, salt = hash_password(password)
        user = new_user(role, username, full_name, email, phone, pw_hash, salt)
        if any(u.email == user.email for u in self._users.values()):
            raise ValidationError(f"Email '{user.email}' đã được sử dụng.")
        self._users[user.username.lower()] = user
        self._commit()
        self.logger.log(user.username, "REGISTER", f"role={role}")
        return user

    def create(self, actor: User, username, full_name, email, phone, password, role) -> User:
        self._require(actor)
        user = self.register(username, full_name, email, phone, password, role)
        self.logger.log(actor.username, "CREATE_USER", f"{user.username} ({role})")
        return user

    def update(self, actor: User, username: str, full_name: str, email: str, phone: str,
               role: str, active: bool) -> User:
        self._require(actor)
        user = self.get(username)
        # Kiểm tra toàn bộ dữ liệu trước khi thay đổi để tránh sửa dở dang
        v.validate_text(full_name, "Họ tên", 2, 60)
        new_email = v.validate_email(email)
        v.validate_phone(phone, required=False)
        if role not in config.ROLE_LABELS:
            raise ValidationError(f"Vai trò không hợp lệ: {role!r}.")
        for other in self._users.values():
            if other.username != user.username and other.email == new_email:
                raise ValidationError(f"Email '{new_email}' đã được sử dụng.")
        if user.username == actor.username and (role != user.role or not active):
            raise BusinessError("Bạn không thể tự đổi vai trò hoặc khóa chính tài khoản của mình.")
        if user.role == config.ROLE_ADMIN and (role != config.ROLE_ADMIN or not active):
            if self._active_admin_count() <= 1:
                raise BusinessError("Phải còn ít nhất một quản trị viên đang hoạt động.")
        user.full_name, user.email, user.phone, user.active = full_name, new_email, phone, bool(active)
        if role != user.role:   # đổi vai trò = đổi lớp -> tạo đối tượng mới, giữ nguyên thông tin
            data = user.to_dict()
            data["role"] = role
            user = user_from_dict(data)
            self._users[user.username.lower()] = user
        self._commit()
        self.logger.log(actor.username, "UPDATE_USER", user.username)
        return user

    def delete(self, actor: User, username: str) -> None:
        self._require(actor)
        user = self.get(username)
        if user.username == actor.username:
            raise BusinessError("Bạn không thể xóa chính tài khoản đang đăng nhập.")
        if user.role == config.ROLE_ADMIN and self._active_admin_count() <= 1:
            raise BusinessError("Không thể xóa quản trị viên cuối cùng.")
        count = self.open_ticket_count(user.username)
        if count:
            raise BusinessError(f"Tài khoản còn {count} ticket đang mở. "
                                f"Hãy xử lý hoặc chuyển ticket trước khi xóa (hoặc khóa tài khoản).")
        del self._users[user.username.lower()]
        self._commit()
        self.logger.log(actor.username, "DELETE_USER", user.username)

    def _active_admin_count(self) -> int:
        return sum(1 for u in self._users.values() if u.role == config.ROLE_ADMIN and u.active)

    # ------------------------------------------------------------------
    # Mật khẩu
    # ------------------------------------------------------------------
    def set_password(self, username: str, new_password: str) -> None:
        user = self.get(username)
        v.validate_password(new_password)
        pw_hash, salt = hash_password(new_password)
        user.set_credentials(pw_hash, salt)
        self._commit()

    def admin_reset_password(self, actor: User, username: str, new_password: str) -> None:
        self._require(actor)
        self.set_password(username, new_password)
        self.logger.log(actor.username, "RESET_PASSWORD", username)

    def ensure_sample_users(self) -> List[User]:
        """Đảm bảo có vài người dùng thông thường để sinh dữ liệu mẫu."""
        samples = [("nv_an", "Nguyễn Văn An", "an.nv@example.com", "0911111111"),
                   ("nv_binh", "Trần Thị Bình", "binh.tt@example.com", "0922222222"),
                   ("nv_chi", "Lê Minh Chi", "chi.lm@example.com", "0933333333"),
                   ("nv_dung", "Phạm Quốc Dũng", "dung.pq@example.com", "0944444444")]
        for username, name, email, phone in samples:
            if not self.find(username):
                self.register(username, name, email, phone, "User@123", config.ROLE_USER)
        return [self.get(s[0]) for s in samples]
