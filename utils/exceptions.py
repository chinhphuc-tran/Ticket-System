"""Hệ thống ngoại lệ riêng của ứng dụng.

Mỗi loại lỗi có lớp riêng để giao diện hiển thị thông báo rõ ràng và để
`except` chỉ bắt đúng loại lỗi cần xử lý (không dùng except trống).
"""


class AppError(Exception):
    """Lớp cơ sở cho mọi lỗi nghiệp vụ của ứng dụng."""


class ValidationError(AppError):
    """Dữ liệu nhập không hợp lệ (thiếu, sai định dạng, ngoài miền giá trị)."""


class StorageError(AppError):
    """Lỗi đọc/ghi file dữ liệu."""


class AuthError(AppError):
    """Lỗi đăng nhập, đăng ký hoặc đổi mật khẩu."""


class PermissionDenied(AppError):
    """Người dùng không có quyền thực hiện thao tác."""


class BusinessError(AppError):
    """Vi phạm ràng buộc nghiệp vụ (ví dụ: xóa dữ liệu đang được sử dụng)."""


class NotFoundError(AppError):
    """Không tìm thấy bản ghi."""


class ApiError(AppError):
    """Lỗi khi lấy dữ liệu từ API/website bên ngoài."""
