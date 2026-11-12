"""Các widget tùy biến (Custom Widget) kế thừa và mở rộng widget Tkinter chuẩn.

  * PriorityBadge / StatusBadge : kế thừa tk.Label, tự đổi màu theo giá trị.
  * SLAMeter                    : kế thừa tk.Canvas, thanh tiến độ thời gian SLA.
  * LabeledEntry                : kế thừa ttk.Frame, nhãn + ô nhập + báo lỗi tại chỗ.
  * DateEntry / CalendarPopup   : ô nhập ngày dd/mm/yyyy kèm lịch chọn ngày.
"""
import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import Callable, Optional

import config
from utils import validators as v
from utils.exceptions import ValidationError


class PriorityBadge(tk.Label):
    """Nhãn màu hiển thị mức ưu tiên."""

    def __init__(self, master, priority: str = "medium", **kwargs):
        super().__init__(master, padx=10, pady=2, font=config.FONT_BOLD, **kwargs)
        self.set_priority(priority)

    def set_priority(self, code: str) -> None:
        info = config.PRIORITY_INFO.get(code, {"label": code, "color": config.COLOR_MUTED})
        self.configure(text=info["label"], bg=info["color"], fg="white")


class StatusBadge(tk.Label):
    """Nhãn màu hiển thị trạng thái ticket."""

    def __init__(self, master, status: str = "new", **kwargs):
        super().__init__(master, padx=10, pady=2, font=config.FONT_BOLD, **kwargs)
        self.set_status(status)

    def set_status(self, code: str) -> None:
        info = config.STATUS_INFO.get(code, {"label": code, "color": config.COLOR_MUTED})
        self.configure(text=info["label"], bg=info["color"], fg="white")


class SLAMeter(tk.Canvas):
    """Thanh tiến độ hiển thị phần trăm thời gian SLA đã sử dụng."""

    _COLORS = {"ok": "#86efac", "warning": "#fcd34d", "breached": "#fca5a5",
               "met": "#4ade80", "missed": "#f87171"}

    def __init__(self, master, height: int = 24, **kwargs):
        super().__init__(master, height=height, highlightthickness=1,
                         highlightbackground=config.COLOR_BORDER, bg="#e5e7eb", **kwargs)
        self._ratio = 0.0
        self._text = ""
        self._state = "ok"
        self.bind("<Configure>", lambda _e: self._draw())

    def set_value(self, ratio: float, text: str, state: str) -> None:
        self._ratio, self._text, self._state = ratio, text, state
        self._draw()

    def clear(self) -> None:
        self._ratio, self._text, self._state = 0.0, "", "ok"
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 2:
            return
        filled = int(width * min(self._ratio, 1.0))
        self.create_rectangle(0, 0, filled, height, fill=self._COLORS.get(self._state, "#d1d5db"), outline="")
        if self._text:
            self.create_text(width // 2, height // 2, text=self._text, font=config.FONT_BOLD,
                             fill=config.COLOR_TEXT)


class LabeledEntry(ttk.Frame):
    """Nhãn + ô nhập + dòng báo lỗi. Kiểm tra dữ liệu khi rời ô nhập (sự kiện FocusOut)."""

    def __init__(self, master, label: str, validator: Optional[Callable[[str], object]] = None,
                 show: str = "", width: int = 32, **kwargs):
        super().__init__(master, **kwargs)
        self.validator = validator
        self.var = tk.StringVar()
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=label).grid(row=0, column=0, sticky="w")
        self.entry = ttk.Entry(self, textvariable=self.var, show=show, width=width)
        self.entry.grid(row=1, column=0, sticky="ew")
        self.error = ttk.Label(self, text="", style="Error.TLabel", wraplength=300, justify="left")
        self.error.grid(row=2, column=0, sticky="w")
        if validator is not None:
            self.entry.bind("<FocusOut>", lambda _e: self.validate())
        self.entry.bind("<KeyPress>", lambda _e: self.error.configure(text=""))

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value or "")

    def clear(self) -> None:
        self.var.set("")
        self.error.configure(text="")

    def focus(self) -> None:
        self.entry.focus_set()

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    def validate(self) -> bool:
        """Chạy validator; hiển thị lỗi ngay dưới ô nhập nếu sai."""
        if self.validator is None:
            return True
        try:
            self.validator(self.get())
        except ValidationError as exc:
            self.error.configure(text=str(exc))
            return False
        self.error.configure(text="")
        return True


class CalendarPopup(tk.Toplevel):
    """Cửa sổ lịch nhỏ để chọn ngày."""

    _WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

    def __init__(self, anchor: tk.Widget, initial: date, on_pick: Callable[[date], None]):
        super().__init__(anchor)
        self.title("Chọn ngày")
        self.resizable(False, False)
        self.transient(anchor.winfo_toplevel())
        self.on_pick = on_pick
        self.year, self.month = initial.year, initial.month

        header = ttk.Frame(self)
        header.pack(fill="x", padx=6, pady=6)
        header.columnconfigure(1, weight=1)
        ttk.Button(header, text="◀", width=3, command=lambda: self._shift(-1)).grid(row=0, column=0)
        self.caption = ttk.Label(header, anchor="center", font=config.FONT_BOLD)
        self.caption.grid(row=0, column=1, sticky="ew")
        ttk.Button(header, text="▶", width=3, command=lambda: self._shift(1)).grid(row=0, column=2)

        self.body = ttk.Frame(self)
        self.body.pack(padx=6, pady=(0, 6))
        self._render()

        self.geometry(f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height()}")
        self.bind("<Escape>", lambda _e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass        # không giành được grab (cửa sổ chưa hiển thị): vẫn dùng bình thường

    def _shift(self, delta: int) -> None:
        self.month += delta
        if self.month < 1:
            self.month, self.year = 12, self.year - 1
        elif self.month > 12:
            self.month, self.year = 1, self.year + 1
        self._render()

    def _render(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self.caption.configure(text=f"Tháng {self.month}/{self.year}")
        for col, name in enumerate(self._WEEKDAYS):
            ttk.Label(self.body, text=name, anchor="center", width=4).grid(row=0, column=col)
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), start=1):
            for col, day in enumerate(week):
                if day:
                    ttk.Button(self.body, text=str(day), width=4,
                               command=lambda d=day: self._pick(d)).grid(row=row, column=col, padx=1, pady=1)

    def _pick(self, day: int) -> None:
        self.on_pick(date(self.year, self.month, day))
        self.destroy()


class DateEntry(ttk.Frame):
    """Ô nhập ngày dd/mm/yyyy, có nút mở lịch chọn ngày."""

    def __init__(self, master, width: int = 11, **kwargs):
        super().__init__(master, **kwargs)
        self.var = tk.StringVar()
        self.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(self, text="▾", width=2, command=self._open_calendar).grid(row=0, column=1, padx=(2, 0))

    def get_date(self, field: str = "Ngày", required: bool = False) -> Optional[date]:
        """Trả về `date` hoặc None nếu để trống; ném ValidationError nếu sai định dạng."""
        return v.validate_date_str(self.var.get(), field, required)

    def set_date(self, value: Optional[date]) -> None:
        self.var.set(value.strftime(config.DISPLAY_DATE_FMT) if value else "")

    def clear(self) -> None:
        self.var.set("")

    def _open_calendar(self) -> None:
        try:
            initial = self.get_date() or date.today()
        except ValidationError:
            initial = date.today()
        CalendarPopup(self.entry, initial, self.set_date)
