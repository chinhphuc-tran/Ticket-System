"""Kiểm tra dữ liệu đầu vào (điều kiện + Regular Expression).

Các hàm `validate_*` trả về giá trị đã được làm sạch hoặc ném
`ValidationError` kèm thông báo hướng dẫn người dùng cách sửa.
"""
import re
from datetime import date, datetime
from typing import Optional

import config
from utils.exceptions import ValidationError

# --------------------------------------------------------------------------
# Các mẫu Regular Expression
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
# Số điện thoại Việt Nam: 0xxxxxxxxx hoặc +84xxxxxxxxx (đầu số 3,5,7,8,9)
PHONE_RE = re.compile(r"^(?:\+84|0)(?:3|5|7|8|9)\d{8}$")
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,19}$")
TICKET_ID_RE = re.compile(r"^TK\d{6}$")
GROUP_ID_RE = re.compile(r"^G\d{2,3}$")
DATE_RE = re.compile(r"^(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/(\d{4})$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES_RE = re.compile(r"\s+")
_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------
# Làm sạch văn bản
# --------------------------------------------------------------------------
def clean_text(value: str, single_line: bool = False) -> str:
    """Bỏ ký tự điều khiển; nếu `single_line` thì gộp mọi khoảng trắng."""
    if value is None:
        return ""
    value = _CONTROL_CHARS_RE.sub("", str(value))
    if single_line:
        value = _SPACES_RE.sub(" ", value)
    return value.strip()


def safe_filename(name: str) -> str:
    """Chuyển tên tệp về dạng an toàn (chỉ chữ, số, ., _, -)."""
    cleaned = _UNSAFE_FILENAME_RE.sub("_", name).strip("._")
    return cleaned or "file"


# --------------------------------------------------------------------------
# Các hàm kiểm tra
# --------------------------------------------------------------------------
def validate_text(value, field: str, min_len: int = 1, max_len: int = 255,
                  required: bool = True) -> str:
    """Kiểm tra chuỗi bắt buộc/độ dài."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} phải là chuỗi ký tự.")
    value = clean_text(value)
    if not value:
        if required:
            raise ValidationError(f"{field} không được để trống.")
        return ""
    if len(value) < min_len:
        raise ValidationError(f"{field} phải có ít nhất {min_len} ký tự (hiện có {len(value)}).")
    if len(value) > max_len:
        raise ValidationError(f"{field} không được vượt quá {max_len} ký tự (hiện có {len(value)}).")
    return value


def _validate_pattern(value, pattern, field: str, hint: str, required: bool) -> str:
    value = clean_text(value or "", single_line=True)
    if not value:
        if required:
            raise ValidationError(f"{field} không được để trống.")
        return ""
    if not pattern.match(value):
        raise ValidationError(f"{field} không hợp lệ. {hint}")
    return value


def validate_email(value, required: bool = True) -> str:
    return _validate_pattern(value, EMAIL_RE, "Email", "Ví dụ: ten@congty.vn", required).lower()


def validate_phone(value, required: bool = False) -> str:
    return _validate_pattern(value, PHONE_RE, "Số điện thoại",
                             "Ví dụ: 0912345678 hoặc +84912345678", required)


def validate_username(value) -> str:
    return _validate_pattern(
        value, USERNAME_RE, "Tên đăng nhập",
        "Gồm 4-20 ký tự, bắt đầu bằng chữ cái, chỉ chứa chữ, số và dấu gạch dưới.", True)


def validate_ticket_id(value) -> str:
    return _validate_pattern(value, TICKET_ID_RE, "Mã ticket", "Định dạng: TK + 6 chữ số, ví dụ TK000123.", True)


def validate_group_id(value) -> str:
    return _validate_pattern(value, GROUP_ID_RE, "Mã nhóm", "Định dạng: G + 2-3 chữ số, ví dụ G01.", True)


def validate_password(value) -> str:
    """Mật khẩu: 6-64 ký tự, có ít nhất một chữ cái và một chữ số."""
    if value is None or value == "":
        raise ValidationError("Mật khẩu không được để trống.")
    if len(value) < 6:
        raise ValidationError("Mật khẩu phải có ít nhất 6 ký tự.")
    if len(value) > 64:
        raise ValidationError("Mật khẩu không được vượt quá 64 ký tự.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValidationError("Mật khẩu phải chứa ít nhất một chữ cái và một chữ số.")
    return value


def validate_choice(value, choices, field: str) -> str:
    if value not in choices:
        raise ValidationError(f"{field} không hợp lệ: '{value}'.")
    return value


def validate_date_str(text, field: str = "Ngày", required: bool = True) -> Optional[date]:
    """Chuyển chuỗi dd/mm/yyyy thành `date`; kiểm tra cả ngày không tồn tại (31/02)."""
    text = clean_text(text or "", single_line=True)
    if not text:
        if required:
            raise ValidationError(f"{field} không được để trống.")
        return None
    if not DATE_RE.match(text):
        raise ValidationError(f"{field} phải có định dạng dd/mm/yyyy (ví dụ 25/12/2026).")
    try:
        return datetime.strptime(text, config.DISPLAY_DATE_FMT).date()
    except ValueError:
        raise ValidationError(f"{field} '{text}' không tồn tại trong lịch.")


def validate_date_range(date_from: Optional[date], date_to: Optional[date]) -> None:
    if date_from and date_to and date_from > date_to:
        raise ValidationError("'Từ ngày' không được sau 'Đến ngày'.")
