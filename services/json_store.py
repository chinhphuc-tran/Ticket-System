"""Lớp JsonStore: đọc/ghi file JSON an toàn, có sao lưu và khôi phục.

Đặc điểm:
  * Dùng `with` cho mọi thao tác file.
  * File chưa tồn tại / rỗng -> tạo dữ liệu mặc định.
  * File sai định dạng -> tự khôi phục từ bản sao lưu gần nhất (nếu có),
    nếu không thì đổi tên file hỏng và tạo mới (không mất dấu dữ liệu cũ).
  * Ghi an toàn: sao lưu bản cũ -> ghi file tạm -> thay thế nguyên tử bằng os.replace.
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional

import config
from utils.exceptions import StorageError


class JsonStore:
    def __init__(self, path: Path, default_factory: Callable[[], Any] = list,
                 backup_dir: Optional[Path] = None, max_backups: int = config.MAX_BACKUPS):
        self.path = Path(path)
        self.default_factory = default_factory
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "backup"
        self.max_backups = max_backups
        self.last_warning: str = ""      # thông báo khôi phục/sửa lỗi gần nhất (để giao diện hiển thị)

    # ------------------------------------------------------------------
    # Đọc
    # ------------------------------------------------------------------
    def load(self) -> Any:
        try:
            if not self.path.exists():
                data = self.default_factory()
                self.save(data)
                return data
            with open(self.path, "r", encoding="utf-8") as f:
                text = f.read()
            if not text.strip():                       # file rỗng
                data = self.default_factory()
                self.save(data)
                return data
            return json.loads(text)
        except json.JSONDecodeError:
            return self._recover()
        except PermissionError as exc:
            raise StorageError(f"Không có quyền truy cập file '{self.path.name}': {exc}") from exc
        except OSError as exc:
            raise StorageError(f"Không đọc được file '{self.path.name}': {exc}") from exc

    def _recover(self) -> Any:
        """File sai định dạng: thử khôi phục từ sao lưu, nếu không được thì tạo mới."""
        for backup in self.list_backups():
            try:
                with open(backup, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            self._quarantine_corrupt()
            self.save(data, make_backup=False)
            self.last_warning = (f"File '{self.path.name}' bị lỗi định dạng; "
                                 f"đã khôi phục từ bản sao lưu '{backup.name}'.")
            return data
        self._quarantine_corrupt()
        data = self.default_factory()
        self.save(data, make_backup=False)
        self.last_warning = (f"File '{self.path.name}' bị lỗi định dạng và không có bản sao lưu; "
                             f"đã tạo dữ liệu mới (file hỏng được giữ lại với đuôi .corrupt).")
        return data

    def _quarantine_corrupt(self) -> None:
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = self.path.with_name(f"{self.path.name}.{stamp}.corrupt")
            os.replace(self.path, target)
        except OSError as exc:
            raise StorageError(f"Không thể cách ly file hỏng '{self.path.name}': {exc}") from exc

    # ------------------------------------------------------------------
    # Ghi
    # ------------------------------------------------------------------
    def save(self, data: Any, make_backup: bool = True) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if make_backup and self.path.exists() and self.path.stat().st_size > 0:
                self.backup()
            tmp_path = self.path.with_name(self.path.name + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)             # thay thế nguyên tử
        except PermissionError as exc:
            raise StorageError(f"Không có quyền ghi file '{self.path.name}': {exc}") from exc
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError(f"Không ghi được file '{self.path.name}': {exc}") from exc

    # ------------------------------------------------------------------
    # Sao lưu / khôi phục
    # ------------------------------------------------------------------
    def backup(self) -> Optional[Path]:
        """Sao chép file hiện tại vào thư mục backup; giữ tối đa `max_backups` bản."""
        if not self.path.exists():
            return None
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = self.backup_dir / f"{self.path.stem}_{stamp}{self.path.suffix}"
            shutil.copy2(self.path, target)
            for old in self.list_backups()[self.max_backups:]:
                try:
                    old.unlink()
                except OSError:
                    pass                                 # không xóa được bản cũ: bỏ qua, không ảnh hưởng dữ liệu
            return target
        except OSError as exc:
            raise StorageError(f"Không sao lưu được '{self.path.name}': {exc}") from exc

    def list_backups(self) -> List[Path]:
        """Danh sách bản sao lưu, mới nhất trước."""
        if not self.backup_dir.exists():
            return []
        files = self.backup_dir.glob(f"{self.path.stem}_*{self.path.suffix}")
        return sorted(files, key=lambda p: p.name, reverse=True)

    def restore_latest(self) -> Path:
        """Khôi phục bản sao lưu mới nhất đọc được. Trả về file đã dùng."""
        for backup in self.list_backups():
            try:
                with open(backup, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            self.save(data)           # bản hiện tại cũng được sao lưu trước khi ghi đè
            return backup
        raise StorageError(f"Không có bản sao lưu hợp lệ cho '{self.path.name}'.")
