"""Cấu hình và hằng số dùng chung cho toàn bộ ứng dụng.

Mọi đường dẫn đều được tính tương đối so với thư mục dự án (hoặc thư mục chứa
file .exe khi đã đóng gói) nên chương trình chạy được trên máy khác.
"""
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Thông tin ứng dụng
# --------------------------------------------------------------------------
APP_TITLE = "Hệ thống quản lý sự cố công nghệ thông tin"
APP_VERSION = "1.0.0"
MIN_PYTHON = (3, 8)


def _base_dir() -> Path:
    """Thư mục gốc: cạnh file .exe nếu đã đóng gói bằng PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# Đường dẫn dữ liệu
# --------------------------------------------------------------------------
BASE_DIR = _base_dir()
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backup"
ATTACHMENT_DIR = DATA_DIR / "attachments"
EXPORT_DIR = BASE_DIR / "exports"

USERS_FILE_NAME = "users.json"
GROUPS_FILE_NAME = "groups.json"
TICKETS_FILE_NAME = "tickets.json"
API_CACHE_FILE_NAME = "api_issues.json"
LOG_FILE_NAME = "activity.log"

MAX_BACKUPS = 10            # số bản sao lưu tối đa cho mỗi file dữ liệu
MAX_ATTACHMENT_MB = 5       # dung lượng tối đa của tệp đính kèm

# --------------------------------------------------------------------------
# Định dạng thời gian
# --------------------------------------------------------------------------
DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"      # định dạng lưu trong JSON
DISPLAY_DT_FMT = "%d/%m/%Y %H:%M"       # định dạng hiển thị
DISPLAY_DATE_FMT = "%d/%m/%Y"

# --------------------------------------------------------------------------
# Vai trò người dùng
# --------------------------------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_AGENT = "agent"
ROLE_USER = "user"
ROLE_LABELS = {
    ROLE_ADMIN: "Quản trị viên",
    ROLE_AGENT: "Kỹ thuật viên",
    ROLE_USER: "Người dùng thông thường",
}

# --------------------------------------------------------------------------
# Mức ưu tiên (kèm SLA giả lập, đơn vị: giờ)
# --------------------------------------------------------------------------
PRIORITY_INFO = {
    "critical": {"label": "Khẩn cấp", "sla_hours": 4, "color": "#dc2626", "rank": 4},
    "high": {"label": "Cao", "sla_hours": 8, "color": "#ea580c", "rank": 3},
    "medium": {"label": "Trung bình", "sla_hours": 24, "color": "#ca8a04", "rank": 2},
    "low": {"label": "Thấp", "sla_hours": 72, "color": "#16a34a", "rank": 1},
}

# --------------------------------------------------------------------------
# Trạng thái ticket
# --------------------------------------------------------------------------
STATUS_INFO = {
    "new": {"label": "Mới", "color": "#2563eb"},
    "in_progress": {"label": "Đang xử lý", "color": "#7c3aed"},
    "waiting": {"label": "Chờ phản hồi", "color": "#ca8a04"},
    "resolved": {"label": "Đã giải quyết", "color": "#16a34a"},
    "closed": {"label": "Đã đóng", "color": "#6b7280"},
}
OPEN_STATUSES = ("new", "in_progress", "waiting")
FINISHED_STATUSES = ("resolved", "closed")

# Trạng thái SLA -> nhãn hiển thị
SLA_LABELS = {
    "ok": "Trong hạn",
    "warning": "Sắp quá hạn",
    "breached": "QUÁ HẠN",
    "met": "Đạt SLA",
    "missed": "Trễ SLA",
}
SLA_WARNING_RATIO = 0.75    # đã dùng >= 75% thời gian SLA thì cảnh báo

# --------------------------------------------------------------------------
# Phân loại sự cố và nhóm hỗ trợ mặc định
# --------------------------------------------------------------------------
CATEGORIES = ["Mạng", "Phần cứng", "Phần mềm", "Tài khoản & Bảo mật", "Khác"]

DEFAULT_GROUPS = [
    ("G01", "Hạ tầng mạng", "Wi-Fi, LAN, VPN, thiết bị mạng"),
    ("G02", "Phần cứng", "Máy tính, máy in, thiết bị ngoại vi"),
    ("G03", "Phần mềm & Ứng dụng", "Cài đặt, lỗi ứng dụng, cập nhật"),
    ("G04", "Tài khoản & Bảo mật", "Mật khẩu, phân quyền, cảnh báo bảo mật"),
]
CATEGORY_DEFAULT_GROUP = {
    "Mạng": "G01",
    "Phần cứng": "G02",
    "Phần mềm": "G03",
    "Tài khoản & Bảo mật": "G04",
    "Khác": "G03",
}

# --------------------------------------------------------------------------
# Bảo mật tài khoản
# --------------------------------------------------------------------------
PASSWORD_ITERATIONS = 120_000
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

# --------------------------------------------------------------------------
# Nguồn dữ liệu ngoài (API) - GitHub REST API: danh sách issue của một repo
# Tài liệu: https://docs.github.com/en/rest/issues/issues
# --------------------------------------------------------------------------
API_URL_TEMPLATE = "https://api.github.com/repos/{repo}/issues"
API_DEFAULT_REPO = "python/cpython"
API_TIMEOUT = 10            # giây
API_MAX_ITEMS = 30
API_USER_AGENT = "TicketSystem-StudentProject/1.0"

# --------------------------------------------------------------------------
# Giao diện
# --------------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_KPI = (FONT_FAMILY, 20, "bold")

COLOR_BG = "#f3f4f6"
COLOR_PANEL = "#ffffff"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_DARK = "#1d4ed8"
COLOR_TEXT = "#111827"
COLOR_MUTED = "#6b7280"
COLOR_DANGER = "#dc2626"
COLOR_BORDER = "#d1d5db"
COLOR_ROW_BREACHED = "#fee2e2"
COLOR_ROW_WARNING = "#fef3c7"
COLOR_ROW_DONE = "#dcfce7"
CHART_COLORS = ["#2563eb", "#7c3aed", "#ca8a04", "#16a34a", "#ea580c", "#0891b2", "#db2777"]

PAD = 8
