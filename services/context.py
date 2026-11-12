"""AppContext: khởi tạo và nối các dịch vụ lại với nhau (một điểm truy cập duy nhất)."""
from pathlib import Path
from typing import Dict, List, Optional

import config
from models.user import User
from services.activity_logger import ActivityLogger
from services.api_service import ApiService
from services.auth_service import AuthService
from services.group_manager import GroupManager
from services.json_store import JsonStore
from services.ticket_manager import TicketManager
from services.user_manager import UserManager
from utils.exceptions import StorageError


class AppContext:
    def __init__(self, data_dir: Optional[Path] = None, fetcher=None):
        self.data_dir = Path(data_dir) if data_dir else config.DATA_DIR
        backup_dir = self.data_dir / "backup"
        self.logger = ActivityLogger(self.data_dir / config.LOG_FILE_NAME)

        self.user_store = JsonStore(self.data_dir / config.USERS_FILE_NAME, list, backup_dir)
        self.group_store = JsonStore(self.data_dir / config.GROUPS_FILE_NAME, self._default_groups, backup_dir)
        self.ticket_store = JsonStore(self.data_dir / config.TICKETS_FILE_NAME, list, backup_dir)
        self.api_store = JsonStore(self.data_dir / config.API_CACHE_FILE_NAME, list, backup_dir)
        self.stores = [self.user_store, self.group_store, self.ticket_store]

        self.users = UserManager(self.user_store, self.logger)
        self.groups = GroupManager(self.group_store, self.logger)
        self.tickets = TicketManager(self.ticket_store, self.logger, self.users, self.groups,
                                     attachment_dir=self.data_dir / "attachments")
        self.auth = AuthService(self.users, self.logger)
        self.api = ApiService(self.api_store, fetcher)

        # Gắn các ràng buộc dữ liệu liên quan giữa các manager
        self.users.open_ticket_count = self.tickets.open_count_for_user
        self.groups.in_use = self.tickets.group_in_use

    @staticmethod
    def _default_groups() -> list:
        from models.group import SupportGroup
        return [SupportGroup(gid, name, desc).to_dict() for gid, name, desc in config.DEFAULT_GROUPS]

    # ------------------------------------------------------------------
    def group_names(self) -> Dict[str, str]:
        return {g.group_id: g.name for g in self.groups.list()}

    def startup_warnings(self) -> List[str]:
        """Các cảnh báo cần báo cho người dùng sau khi nạp dữ liệu."""
        warnings = [s.last_warning for s in self.stores + [self.api_store] if s.last_warning]
        skipped = self.users.skipped + self.groups.skipped + self.tickets.skipped
        if skipped:
            warnings.append(f"Có {skipped} bản ghi sai định dạng đã bị bỏ qua (xem nhật ký hoạt động).")
        return warnings

    def backup_all(self) -> List[Path]:
        paths = []
        for store in self.stores:
            path = store.backup()
            if path:
                paths.append(path)
        self.logger.log("system", "BACKUP", f"{len(paths)} file")
        return paths

    def restore_all(self) -> int:
        """Khôi phục bản sao lưu gần nhất cho từng file và nạp lại dữ liệu."""
        restored = 0
        errors = []
        for store in self.stores:
            try:
                store.restore_latest()
                restored += 1
            except StorageError as exc:
                errors.append(str(exc))
        self.reload()
        self.logger.log("system", "RESTORE", f"{restored} file")
        if restored == 0 and errors:
            raise StorageError(errors[0])
        return restored

    def reload(self) -> None:
        self.users.reload()
        self.groups.reload()
        self.tickets.reload()

    def refresh_user(self, user: User) -> Optional[User]:
        """Lấy lại đối tượng người dùng mới nhất (sau khi đổi vai trò/khóa)."""
        return self.users.find(user.username)
