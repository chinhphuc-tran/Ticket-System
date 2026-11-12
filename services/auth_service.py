"""Dịch vụ xác thực: đăng nhập, đăng xuất, đăng ký, đổi mật khẩu."""
import time
from typing import Dict, Optional

import config
from models.user import User
from services.activity_logger import ActivityLogger
from services.user_manager import UserManager, verify_password
from utils import validators as v
from utils.exceptions import AuthError, ValidationError


class AuthService:
    def __init__(self, users: UserManager, logger: ActivityLogger):
        self.users = users
        self.logger = logger
        self.current_user: Optional[User] = None
        self._failed: Dict[str, int] = {}          # số lần đăng nhập sai liên tiếp
        self._locked_until: Dict[str, float] = {}  # thời điểm (monotonic) hết khóa

    def login(self, username: str, password: str) -> User:
        username = (username or "").strip()
        if not username or not password:
            raise AuthError("Vui lòng nhập tên đăng nhập và mật khẩu.")
        key = username.lower()
        remaining = self._locked_until.get(key, 0) - time.monotonic()
        if remaining > 0:
            raise AuthError(f"Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau {int(remaining) + 1} giây.")

        user = self.users.find(username)
        # Thông báo chung để không lộ tài khoản nào tồn tại
        if user is None or not verify_password(password, user.password_hash, user.salt):
            self._failed[key] = self._failed.get(key, 0) + 1
            self.logger.log(username, "LOGIN_FAILED", f"lần {self._failed[key]}")
            if self._failed[key] >= config.MAX_LOGIN_ATTEMPTS:
                self._locked_until[key] = time.monotonic() + config.LOCKOUT_SECONDS
                self._failed[key] = 0
                raise AuthError(f"Nhập sai {config.MAX_LOGIN_ATTEMPTS} lần. Tài khoản bị khóa "
                                f"{config.LOCKOUT_SECONDS} giây.")
            raise AuthError("Tên đăng nhập hoặc mật khẩu không đúng.")
        if not user.active:
            self.logger.log(user.username, "LOGIN_BLOCKED", "tài khoản bị khóa")
            raise AuthError("Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.")

        self._failed.pop(key, None)
        self._locked_until.pop(key, None)
        self.current_user = user
        self.logger.log(user.username, "LOGIN", user.role)
        return user

    def logout(self) -> None:
        if self.current_user:
            self.logger.log(self.current_user.username, "LOGOUT")
        self.current_user = None

    def register(self, username, full_name, email, phone, password, confirm) -> User:
        if password != confirm:
            raise ValidationError("Mật khẩu xác nhận không khớp.")
        # Đăng ký công khai chỉ tạo Người dùng thông thường (không tự cấp quyền cao)
        return self.users.register(username, full_name, email, phone, password, config.ROLE_USER)

    def change_password(self, user: User, old_password: str, new_password: str, confirm: str) -> None:
        if not verify_password(old_password or "", user.password_hash, user.salt):
            raise AuthError("Mật khẩu hiện tại không đúng.")
        if new_password != confirm:
            raise ValidationError("Mật khẩu xác nhận không khớp.")
        if new_password == old_password:
            raise ValidationError("Mật khẩu mới phải khác mật khẩu hiện tại.")
        v.validate_password(new_password)
        self.users.set_password(user.username, new_password)
        self.logger.log(user.username, "CHANGE_PASSWORD")
