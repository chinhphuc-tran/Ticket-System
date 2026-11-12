"""Nhật ký hoạt động ghi ra file văn bản (đăng nhập, thao tác quan trọng, lỗi)."""
from datetime import datetime
from pathlib import Path
from typing import List

import config


class ActivityLogger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def log(self, actor: str, action: str, detail: str = "") -> None:
        """Ghi một dòng nhật ký. Lỗi ghi log không được làm dừng ứng dụng."""
        stamp = datetime.now().strftime(config.DATETIME_FMT)
        detail = " ".join(str(detail).split())
        line = f"{stamp} | {actor or '-'} | {action} | {detail}\n"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass    # nhật ký chỉ là phụ trợ; bỏ qua nếu không ghi được

    def tail(self, max_lines: int = 200) -> List[str]:
        """Đọc các dòng nhật ký gần nhất."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        except OSError:
            return ["(Không đọc được file nhật ký)"]
        return [ln.rstrip("\n") for ln in lines[-max_lines:]]
