"""Lấy dữ liệu từ API bên ngoài (GitHub REST API - Issues), làm sạch và lưu JSON.

Nguồn: https://api.github.com/repos/{owner}/{repo}/issues
Tài liệu: https://docs.github.com/en/rest/issues/issues
Ghi chú tuân thủ điều khoản: dùng API công khai, không cần khóa, giới hạn
60 yêu cầu/giờ/IP, chỉ lấy tối đa `API_MAX_ITEMS` issue mỗi lần và có gửi User-Agent.
"""
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional

import config
from services.json_store import JsonStore
from utils import validators as v
from utils.exceptions import ApiError, StorageError

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Từ khóa nhãn -> phân loại / mức ưu tiên
_CATEGORY_KEYWORDS = [
    ("Mạng", ("network", "socket", "ssl", "http", "email", "asyncio", "urllib")),
    ("Tài khoản & Bảo mật", ("security", "auth", "crash", "vulnerab")),
    ("Phần cứng", ("hardware", "memory", "platform", "windows", "macos", "linux")),
    ("Phần mềm", ("bug", "type-", "stdlib", "interpreter", "docs", "performance", "build", "tests")),
]
_PRIORITY_KEYWORDS = [
    ("critical", ("security", "crash", "release-blocker", "deferred-blocker")),
    ("high", ("bug", "regression", "type-bug")),
    ("low", ("docs", "enhancement", "feature", "type-feature", "easy", "documentation")),
]

Fetcher = Callable[[str, float], bytes]


def _default_fetch(url: str, timeout: float) -> bytes:
    """Gửi yêu cầu HTTP GET và trả về nội dung thô."""
    request = urllib.request.Request(url, headers={
        "User-Agent": config.API_USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class ApiService:
    def __init__(self, cache_store: JsonStore, fetcher: Optional[Fetcher] = None):
        self.cache_store = cache_store
        self._fetch = fetcher or _default_fetch

    # ------------------------------------------------------------------
    def fetch_issues(self, repo: str = config.API_DEFAULT_REPO,
                     limit: int = config.API_MAX_ITEMS) -> List[dict]:
        """Gọi API, làm sạch, lưu vào JSON và trả về danh sách bản ghi chuẩn hóa."""
        repo = (repo or "").strip()
        if not _REPO_RE.match(repo):
            raise ApiError("Tên repository không hợp lệ. Định dạng: chu-so-huu/ten-repo (ví dụ python/cpython).")
        if not 1 <= limit <= 100:
            raise ApiError("Số lượng issue phải trong khoảng 1-100.")

        query = urllib.parse.urlencode({"state": "all", "per_page": limit, "sort": "created", "direction": "desc"})
        url = config.API_URL_TEMPLATE.format(repo=repo) + "?" + query
        try:
            body = self._fetch(url, config.API_TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise ApiError("API từ chối yêu cầu (có thể đã vượt giới hạn số lần gọi). Hãy thử lại sau ít phút.") from exc
            if exc.code == 404:
                raise ApiError(f"Không tìm thấy repository '{repo}'.") from exc
            raise ApiError(f"Máy chủ API trả về lỗi HTTP {exc.code}.") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise ApiError("Hết thời gian chờ phản hồi từ máy chủ API.") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Không kết nối được tới máy chủ API ({exc.reason}). Kiểm tra kết nối mạng.") from exc
        except OSError as exc:
            raise ApiError(f"Lỗi mạng khi gọi API: {exc}") from exc

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("Dữ liệu API trả về không đúng định dạng JSON.") from exc
        if not isinstance(payload, list):
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            raise ApiError(f"API trả về dữ liệu không như mong đợi. {message}".strip())

        records = self.clean_records(payload, repo)
        if not records:
            raise ApiError("API không trả về issue nào dùng được.")
        try:
            self.cache_store.save(records)
        except StorageError as exc:
            raise ApiError(f"Đã lấy dữ liệu nhưng không lưu được file JSON: {exc}") from exc
        return records

    def load_cached(self) -> List[dict]:
        data = self.cache_store.load()
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    @staticmethod
    def clean_records(payload: list, repo: str) -> List[dict]:
        """Làm sạch, kiểm tra và chuyển đổi issue thành bản ghi ticket."""
        records = []
        for item in payload:
            if not isinstance(item, dict) or "pull_request" in item:   # bỏ pull request
                continue
            number, title = item.get("number"), item.get("title")
            if not isinstance(number, int) or not isinstance(title, str):
                continue                                               # thiếu dữ liệu bắt buộc
            title = v.clean_text(title, single_line=True)
            if len(title) < 5:
                continue
            title = title[:120]
            body = v.clean_text(item.get("body") or "")
            description = (body[:1500] if body else "(Không có mô tả)")
            if len(description) < 10:                                  # ticket yêu cầu mô tả >= 10 ký tự
                description = f"{description} (mô tả ngắn)"
            labels = [str(lb.get("name", "")).lower() for lb in item.get("labels", []) if isinstance(lb, dict)]
            records.append({
                "external_ref": f"github:{repo}#{number}",
                "title": title,
                "description": description,
                "category": ApiService._guess_category(labels, title),
                "priority": ApiService._guess_priority(labels),
                "status": "closed" if item.get("state") == "closed" else "new",
                "created_at": item.get("created_at") or "",
                "labels": labels,
                "url": item.get("html_url", ""),
            })
        return records

    @staticmethod
    def _guess_category(labels: List[str], title: str) -> str:
        text = " ".join(labels + [title.lower()])
        for category, keywords in _CATEGORY_KEYWORDS:
            if any(k in text for k in keywords):
                return category
        return "Khác"

    @staticmethod
    def _guess_priority(labels: List[str]) -> str:
        text = " ".join(labels)
        for priority, keywords in _PRIORITY_KEYWORDS:
            if any(k in text for k in keywords):
                return priority
        return "medium"
