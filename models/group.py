"""Lớp SupportGroup: nhóm hỗ trợ kỹ thuật."""
from utils import validators as v


class SupportGroup:
    def __init__(self, group_id: str, name: str, description: str = "", lead: str = ""):
        self.group_id = group_id
        self.name = name
        self.description = description
        self.lead = lead   # tên đăng nhập của trưởng nhóm (có thể để trống)

    @property
    def group_id(self) -> str:
        return self._group_id

    @group_id.setter
    def group_id(self, value: str) -> None:
        self._group_id = v.validate_group_id(value)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = v.validate_text(value, "Tên nhóm", 3, 50)

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = v.validate_text(value, "Mô tả nhóm", 0, 200, required=False)

    @property
    def lead(self) -> str:
        return self._lead

    @lead.setter
    def lead(self, value: str) -> None:
        self._lead = (value or "").strip()

    def to_dict(self) -> dict:
        return {"group_id": self.group_id, "name": self.name,
                "description": self.description, "lead": self.lead}

    @classmethod
    def from_dict(cls, data: dict) -> "SupportGroup":
        return cls(data.get("group_id", ""), data.get("name", ""),
                   data.get("description", ""), data.get("lead", ""))

    def __repr__(self) -> str:
        return f"SupportGroup({self.group_id}, {self.name!r})"
