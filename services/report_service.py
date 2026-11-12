"""Xuất báo cáo/kết quả ra file CSV, JSON và văn bản."""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import config
from models.ticket import Ticket
from services import stats_service
from utils.exceptions import StorageError

CSV_HEADERS = ["Mã ticket", "Tiêu đề", "Phân loại", "Ưu tiên", "Trạng thái", "Nhóm", "Người yêu cầu",
               "Người xử lý", "Ngày tạo", "Hạn SLA", "Tình trạng SLA", "Giờ xử lý"]


def _ticket_row(t: Ticket, group_names: Dict[str, str]) -> list:
    hours = t.processing_hours()
    return [t.ticket_id, t.title, t.category, t.priority_label, t.status_label,
            group_names.get(t.group_id, ""), t.requester, t.assignee,
            t.created_at.strftime(config.DISPLAY_DT_FMT), t.due_at.strftime(config.DISPLAY_DT_FMT),
            config.SLA_LABELS[t.sla_state()], f"{hours:.1f}" if hours is not None else ""]


def _write(path: Path, writer_fn) -> Path:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        writer_fn(path)
    except PermissionError as exc:
        raise StorageError(f"Không có quyền ghi file '{path.name}': {exc}") from exc
    except OSError as exc:
        raise StorageError(f"Không xuất được file '{path.name}': {exc}") from exc
    return path


def export_csv(tickets: Iterable[Ticket], path: Path, group_names: Dict[str, str]) -> Path:
    rows = [_ticket_row(t, group_names) for t in tickets]

    def writer(p: Path) -> None:
        with open(p, "w", encoding="utf-8-sig", newline="") as f:     # utf-8-sig để Excel đọc đúng tiếng Việt
            w = csv.writer(f)
            w.writerow(CSV_HEADERS)
            w.writerows(rows)
    return _write(path, writer)


def export_json(tickets: Iterable[Ticket], path: Path) -> Path:
    data = [t.to_dict() for t in tickets]

    def writer(p: Path) -> None:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return _write(path, writer)


def build_summary_text(tickets: List[Ticket], group_names: Dict[str, str], author: str) -> str:
    stats = stats_service.summarize(tickets)
    lines = [
        "BÁO CÁO TỔNG HỢP SỰ CỐ CÔNG NGHỆ THÔNG TIN",
        "=" * 50,
        f"Thời điểm xuất : {datetime.now().strftime(config.DISPLAY_DT_FMT)}",
        f"Người xuất     : {author}",
        "",
        "1. Tổng quan",
        f"   - Tổng số ticket          : {stats['total']}",
        f"   - Đang mở                 : {stats['open']}",
        f"   - Đã giải quyết/đóng      : {stats['finished']}",
        f"   - Đang quá hạn SLA        : {stats['breached']}",
        f"   - Sắp quá hạn SLA         : {stats['warning']}",
        f"   - Thời gian xử lý TB      : {stats['avg_processing_hours']:.1f} giờ",
        f"   - Tỷ lệ đạt SLA           : {stats['sla_met_rate']:.1f}%",
        "",
        "2. Theo trạng thái",
    ]
    lines += [f"   - {label:<15}: {count}" for label, count, _ in stats_service.status_series(stats)]
    lines += ["", "3. Theo mức ưu tiên"]
    lines += [f"   - {label:<15}: {count}" for label, count, _ in stats_service.priority_series(stats)]
    lines += ["", "4. Theo nhóm hỗ trợ"]
    lines += [f"   - {label:<22}: {count}" for label, count, _ in stats_service.group_series(stats, group_names)]
    lines += ["", "5. Theo phân loại lỗi"]
    lines += [f"   - {cat:<22}: {n}" for cat, n in sorted(stats["by_category"].items(), key=lambda kv: -kv[1])]
    lines += ["", "6. Thời gian xử lý trung bình theo nhóm"]
    avg = stats_service.avg_hours_by_group(tickets, group_names)
    lines += [f"   - {name:<22}: {hours:.1f} giờ" for name, hours in sorted(avg.items())] or ["   (chưa có dữ liệu)"]
    return "\n".join(lines) + "\n"


def export_summary(tickets: List[Ticket], path: Path, group_names: Dict[str, str], author: str) -> Path:
    text = build_summary_text(tickets, group_names, author)

    def writer(p: Path) -> None:
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    return _write(path, writer)
