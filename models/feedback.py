"""Lớp Feedback: một phản hồi/bình luận gắn với ticket."""
from datetime import datetime
from typing import Optional, Union

import config
from utils import validators as v


def to_datetime(value: Union[str, datetime, None], default: Optional[datetime] = None) -> datetime:
    """Chuyển chuỗi ISO / datetime thành datetime (bỏ micro giây)."""
    if value is None or value == "":
        return default if default is not None else datetime.now().replace(microsecond=0)
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    try:
        return datetime.strptime(str(value), config.DATETIME_FMT)
    except ValueError:
        # Cho phép định dạng ISO khác (ví dụ có múi giờ 'Z' từ API)
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None, microsecond=0)
        except ValueError:
            raise v.ValidationError(f"Thời gian '{value}' không đúng định dạng.")


class Feedback:
    """Phản hồi của người dùng hoặc kỹ thuật viên.

    `internal=True` là ghi chú nội bộ: chỉ kỹ thuật viên/quản trị viên nhìn thấy.
    """

    def __init__(self, author: str, content: str, created_at=None, internal: bool = False):
        self.author = author
        self.content = content
        self.created_at = to_datetime(created_at)
        self.internal = bool(internal)

    @property
    def author(self) -> str:
        return self._author

    @author.setter
    def author(self, value: str) -> None:
        self._author = v.validate_text(value, "Người phản hồi", 1, 40)

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = v.validate_text(value, "Nội dung phản hồi", 1, 1000)

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "content": self.content,
            "created_at": self.created_at.strftime(config.DATETIME_FMT),
            "internal": self.internal,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Feedback":
        return cls(data.get("author", ""), data.get("content", ""),
                   data.get("created_at"), data.get("internal", False))
