"""Tab thống kê: thẻ chỉ số (KPI) và biểu đồ tự vẽ bằng tk.Canvas (không dùng thư viện ngoài)."""
import math
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Sequence, Tuple

import config
from models.user import User
from services import stats_service
from services.context import AppContext

Series = Sequence[Tuple[str, int, str]]


class ChartCanvas(tk.Canvas):
    """Lớp cơ sở cho biểu đồ: tự vẽ lại khi đổi kích thước cửa sổ."""

    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, bg=config.COLOR_PANEL, highlightthickness=1,
                         highlightbackground=config.COLOR_BORDER, height=260, width=320, **kwargs)
        self.title = title
        self.data: List[Tuple[str, int, str]] = []
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_data(self, data: Series) -> None:
        self.data = list(data)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 60 or height < 60:
            return
        self.create_text(10, 12, text=self.title, anchor="w", font=config.FONT_BOLD, fill=config.COLOR_TEXT)
        if not any(count for _, count, _ in self.data):
            self.create_text(width / 2, height / 2, text="Chưa có dữ liệu", fill=config.COLOR_MUTED)
            return
        self.draw(width, height)

    def draw(self, width: int, height: int) -> None:           # ghi đè ở lớp con
        raise NotImplementedError


class BarChart(ChartCanvas):
    """Biểu đồ cột."""

    def draw(self, width: int, height: int) -> None:
        left, right, top, bottom = 34, 12, 34, 44
        plot_w, plot_h = width - left - right, height - top - bottom
        peak = max(count for _, count, _ in self.data)
        step = max(1, math.ceil(peak / 4))
        axis_max = step * math.ceil(peak / step)

        for i in range(0, axis_max + 1, step):                  # lưới ngang + nhãn trục tung
            y = top + plot_h - plot_h * i / axis_max
            self.create_line(left, y, width - right, y, fill="#e5e7eb")
            self.create_text(left - 6, y, text=str(i), anchor="e", fill=config.COLOR_MUTED, font=(config.FONT_FAMILY, 8))

        slot = plot_w / len(self.data)
        bar_w = min(slot * 0.6, 56)
        for i, (label, count, color) in enumerate(self.data):
            cx = left + slot * (i + 0.5)
            bar_h = plot_h * count / axis_max
            self.create_rectangle(cx - bar_w / 2, top + plot_h - bar_h, cx + bar_w / 2, top + plot_h,
                                  fill=color, outline="")
            self.create_text(cx, top + plot_h - bar_h - 8, text=str(count), font=config.FONT_BOLD,
                             fill=config.COLOR_TEXT)
            self.create_text(cx, top + plot_h + 6, text=label, anchor="n", width=max(slot - 4, 30),
                             font=(config.FONT_FAMILY, 8), fill=config.COLOR_TEXT, justify="center")


class PieChart(ChartCanvas):
    """Biểu đồ tròn kèm chú thích."""

    def draw(self, width: int, height: int) -> None:
        total = sum(count for _, count, _ in self.data)
        size = min(width * 0.5, height - 50)
        x0, y0 = 14, 34 + (height - 34 - size) / 2 - 8
        box = (x0, y0, x0 + size, y0 + size)
        start = 90.0
        nonzero = [d for d in self.data if d[1] > 0]
        if len(nonzero) == 1:                                   # một phần duy nhất: vẽ cả hình tròn
            self.create_oval(*box, fill=nonzero[0][2], outline="white", width=2)
        else:
            for _label, count, color in nonzero:
                extent = -360.0 * count / total
                self.create_arc(*box, start=start, extent=extent, fill=color, outline="white", width=2)
                start += extent
        lx, ly = x0 + size + 16, 40
        for label, count, color in self.data:
            self.create_rectangle(lx, ly, lx + 12, ly + 12, fill=color, outline="")
            self.create_text(lx + 18, ly + 6, text=f"{label}: {count} ({count / total * 100:.0f}%)", anchor="w",
                             font=(config.FONT_FAMILY, 9), fill=config.COLOR_TEXT, width=max(width - lx - 22, 60))
            ly += 22


class LineChart(ChartCanvas):
    """Biểu đồ đường (xu hướng theo ngày)."""

    def draw(self, width: int, height: int) -> None:
        left, right, top, bottom = 34, 16, 34, 34
        plot_w, plot_h = width - left - right, height - top - bottom
        peak = max(count for _, count, _ in self.data)
        step = max(1, math.ceil(peak / 4))
        axis_max = step * math.ceil(peak / step)
        for i in range(0, axis_max + 1, step):
            y = top + plot_h - plot_h * i / axis_max
            self.create_line(left, y, width - right, y, fill="#e5e7eb")
            self.create_text(left - 6, y, text=str(i), anchor="e", fill=config.COLOR_MUTED, font=(config.FONT_FAMILY, 8))
        n = len(self.data)
        points = []
        for i, (label, count, _c) in enumerate(self.data):
            x = left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
            y = top + plot_h - plot_h * count / axis_max
            points.append((x, y))
            if n <= 8 or i % 2 == 0:
                self.create_text(x, top + plot_h + 6, text=label, anchor="n", font=(config.FONT_FAMILY, 8),
                                 fill=config.COLOR_MUTED)
        if len(points) > 1:
            self.create_line(*[c for p in points for c in p], fill=config.COLOR_PRIMARY, width=2, smooth=False)
        for x, y in points:
            self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=config.COLOR_PRIMARY, outline="white")


class DashboardTab(ttk.Frame):
    """Vùng chứa chính dùng pack(); các thẻ KPI và biểu đồ dùng grid() trong Frame riêng."""

    KPIS = (("total", "Tổng ticket"), ("open", "Đang mở"), ("breached", "Quá hạn SLA"),
            ("avg", "Giờ xử lý TB"), ("sla_rate", "Tỷ lệ đạt SLA"))

    def __init__(self, master, ctx: AppContext, user: User):
        super().__init__(master, padding=config.PAD)
        self.ctx, self.user = ctx, user

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Tổng quan sự cố", style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="Làm mới", command=self.refresh).pack(side="right")

        kpi_row = ttk.Frame(self)
        kpi_row.pack(fill="x", pady=config.PAD)
        self.kpi_vars = {}
        for col, (key, caption) in enumerate(self.KPIS):
            kpi_row.columnconfigure(col, weight=1, uniform="kpi")
            card = ttk.Frame(kpi_row, style="Card.TFrame", padding=config.PAD)
            card.grid(row=0, column=col, sticky="ew", padx=4)
            var = tk.StringVar(value="0")
            self.kpi_vars[key] = var
            ttk.Label(card, textvariable=var, style="KPI.TLabel").pack()
            ttk.Label(card, text=caption, style="Card.TLabel", foreground=config.COLOR_MUTED).pack()

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="chart")
        for row in range(2):
            grid.rowconfigure(row, weight=1)
        self.status_chart = BarChart(grid, "Ticket theo trạng thái")
        self.priority_chart = PieChart(grid, "Ticket theo mức ưu tiên")
        self.group_chart = BarChart(grid, "Ticket theo nhóm hỗ trợ")
        self.category_chart = PieChart(grid, "Ticket theo phân loại")
        self.trend_chart = LineChart(grid, "Ticket tạo mới 14 ngày gần nhất")
        charts = (self.status_chart, self.priority_chart, self.group_chart, self.category_chart)
        for i, chart in enumerate(charts):
            chart.grid(row=i // 3 if i < 3 else 1, column=i % 3 if i < 3 else 0, sticky="nsew", padx=4, pady=4)
        self.trend_chart.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        tickets = self.ctx.tickets.list_for(self.user)
        stats = stats_service.summarize(tickets)
        self.kpi_vars["total"].set(str(stats["total"]))
        self.kpi_vars["open"].set(str(stats["open"]))
        self.kpi_vars["breached"].set(str(stats["breached"]))
        self.kpi_vars["avg"].set(f"{stats['avg_processing_hours']:.1f}")
        self.kpi_vars["sla_rate"].set(f"{stats['sla_met_rate']:.0f}%")
        names = self.ctx.group_names()
        self.status_chart.set_data(stats_service.status_series(stats))
        self.priority_chart.set_data(stats_service.priority_series(stats))
        self.group_chart.set_data(stats_service.group_series(stats, names))
        cats = sorted(stats["by_category"].items(), key=lambda kv: -kv[1])
        self.category_chart.set_data([(c, n, config.CHART_COLORS[i % len(config.CHART_COLORS)])
                                      for i, (c, n) in enumerate(cats)])
        self.trend_chart.set_data([(d, n, config.COLOR_PRIMARY) for d, n in stats_service.tickets_per_day(tickets)])
