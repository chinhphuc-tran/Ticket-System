"""Lớp quản lý nhóm hỗ trợ (CRUD + ràng buộc dữ liệu)."""
from typing import Callable, Dict, List, Optional

import config
from models.group import SupportGroup
from models.user import PERM_GROUP_MANAGE, User
from services.activity_logger import ActivityLogger
from services.json_store import JsonStore
from utils.exceptions import (BusinessError, NotFoundError, PermissionDenied,
                              StorageError, ValidationError)


def _default_groups() -> list:
    return [SupportGroup(gid, name, desc).to_dict() for gid, name, desc in config.DEFAULT_GROUPS]


class GroupManager:
    def __init__(self, store: JsonStore, logger: ActivityLogger):
        self.store = store
        self.logger = logger
        # Hàm do context gắn vào: kiểm tra nhóm có đang được ticket sử dụng không
        self.in_use: Callable[[str], bool] = lambda group_id: False
        self._groups: Dict[str, SupportGroup] = {}
        self.skipped = 0
        self.reload()

    def reload(self) -> None:
        raw = self.store.load()
        self._groups, self.skipped = {}, 0
        if not isinstance(raw, list):
            raw = []
        for item in raw:
            try:
                group = SupportGroup.from_dict(item)
                self._groups[group.group_id] = group
            except (ValidationError, AttributeError) as exc:
                self.skipped += 1
                self.logger.log("system", "SKIP_GROUP", str(exc))

    def _commit(self) -> None:
        try:
            self.store.save([g.to_dict() for g in self.list()])
        except StorageError:
            self.reload()       # giữ bộ nhớ khớp với file nếu ghi thất bại
            raise

    @staticmethod
    def _require(actor: User) -> None:
        if not actor.can(PERM_GROUP_MANAGE):
            raise PermissionDenied("Bạn không có quyền quản lý nhóm hỗ trợ.")

    # ------------------------------------------------------------------
    def list(self) -> List[SupportGroup]:
        return sorted(self._groups.values(), key=lambda g: g.group_id)

    def get(self, group_id: str) -> SupportGroup:
        try:
            return self._groups[group_id]
        except KeyError:
            raise NotFoundError(f"Không tìm thấy nhóm '{group_id}'.")

    def find(self, group_id: str) -> Optional[SupportGroup]:
        return self._groups.get(group_id)

    def name_of(self, group_id: str) -> str:
        group = self._groups.get(group_id)
        return group.name if group else "(chưa có nhóm)"

    def create(self, actor: User, group_id: str, name: str, description: str = "",
               lead: str = "") -> SupportGroup:
        self._require(actor)
        group = SupportGroup(group_id, name, description, lead)
        if group.group_id in self._groups:
            raise ValidationError(f"Mã nhóm '{group.group_id}' đã tồn tại.")
        if any(g.name.lower() == group.name.lower() for g in self._groups.values()):
            raise ValidationError(f"Tên nhóm '{group.name}' đã tồn tại.")
        self._groups[group.group_id] = group
        self._commit()
        self.logger.log(actor.username, "CREATE_GROUP", group.group_id)
        return group

    def update(self, actor: User, group_id: str, name: str, description: str = "",
               lead: str = "") -> SupportGroup:
        self._require(actor)
        group = self.get(group_id)
        new_name = SupportGroup(group_id, name, description, lead)   # kiểm tra dữ liệu trước khi sửa
        for other in self._groups.values():
            if other.group_id != group_id and other.name.lower() == new_name.name.lower():
                raise ValidationError(f"Tên nhóm '{new_name.name}' đã tồn tại.")
        group.name, group.description, group.lead = new_name.name, new_name.description, new_name.lead
        self._commit()
        self.logger.log(actor.username, "UPDATE_GROUP", group_id)
        return group

    def delete(self, actor: User, group_id: str) -> None:
        self._require(actor)
        self.get(group_id)
        if self.in_use(group_id):
            raise BusinessError("Không thể xóa nhóm đang có ticket được gán. "
                                "Hãy chuyển các ticket sang nhóm khác trước.")
        del self._groups[group_id]
        self._commit()
        self.logger.log(actor.username, "DELETE_GROUP", group_id)
