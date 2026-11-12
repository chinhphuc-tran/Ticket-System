"""Thống kê, tổng hợp số liệu ticket (dùng cho Dashboard Canvas và báo cáo)."""
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import config
from models.ticket import Ticket


def summarize(tickets: Iterable[Ticket], now: Optional[datetime] = None) -> Dict:
    """Tổng hợp các chỉ số chính. Không chia cho 0 khi chưa có dữ liệu."""
    tickets = list(tickets)
    now = now or datetime.now()
    total = len(tickets)
    by_status = Counter(t.status for t in tickets)
    by_priority = Counter(t.priority for t in tickets)
    by_category = Counter(t.category for t in tickets)
    by_group = Counter(t.group_id or "" for t in tickets)

    sla_states = Counter(t.sla_state(now) for t in tickets)
    finished = [t for t in tickets if t.processing_hours() is not None]
    avg_hours = sum(t.processing_hours() for t in finished) / len(finished) if finished else 0.0
    met = sla_states.get("met", 0)
    sla_rate = met / len(finished) * 100 if finished else 0.0

    return {
        "total": total,
        "open": sum(1 for t in tickets if t.is_open),
        "finished": len(finished),
        "breached": sla_states.get("breached", 0),
        "warning": sla_states.get("warning", 0),
        "missed": sla_states.get("missed", 0),
        "avg_processing_hours": avg_hours,
        "sla_met_rate": sla_rate,
        "by_status": dict(by_status),
        "by_priority": dict(by_priority),
        "by_category": dict(by_category),
        "by_group": dict(by_group),
    }


def status_series(stats: Dict) -> List[Tuple[str, int, str]]:
    """[(nhãn, số lượng, màu)] theo thứ tự quy trình."""
    return [(info["label"], stats["by_status"].get(code, 0), info["color"])
            for code, info in config.STATUS_INFO.items()]


def priority_series(stats: Dict) -> List[Tuple[str, int, str]]:
    ordered = sorted(config.PRIORITY_INFO.items(), key=lambda kv: -kv[1]["rank"])
    return [(info["label"], stats["by_priority"].get(code, 0), info["color"]) for code, info in ordered]


def group_series(stats: Dict, group_names: Dict[str, str]) -> List[Tuple[str, int, str]]:
    items = sorted(stats["by_group"].items(), key=lambda kv: (-kv[1], kv[0]))
    series = []
    for i, (gid, count) in enumerate(items):
        name = group_names.get(gid, "(chưa có nhóm)") if gid else "(chưa có nhóm)"
        series.append((name, count, config.CHART_COLORS[i % len(config.CHART_COLORS)]))
    return series


def tickets_per_day(tickets: Iterable[Ticket], days: int = 14,
                    today: Optional[date] = None) -> List[Tuple[str, int]]:
    """Số ticket tạo mới mỗi ngày trong `days` ngày gần nhất."""
    today = today or date.today()
    counter = Counter(t.created_at.date() for t in tickets)
    series = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        series.append((d.strftime("%d/%m"), counter.get(d, 0)))
    return series


def avg_hours_by_group(tickets: Iterable[Ticket], group_names: Dict[str, str]) -> Dict[str, float]:
    sums: Dict[str, List[float]] = {}
    for t in tickets:
        hours = t.processing_hours()
        if hours is not None:
            sums.setdefault(group_names.get(t.group_id, "(chưa có nhóm)"), []).append(hours)
    return {name: sum(vals) / len(vals) for name, vals in sums.items()}
