"""Tab quản lý ticket: tìm kiếm/lọc, danh sách (Treeview), chi tiết, thao tác CRUD."""
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

import config
from models.ticket import Ticket
from models.user import (PERM_FEEDBACK, PERM_INTERNAL_NOTE, PERM_TICKET_ASSIGN, PERM_TICKET_CREATE,
                         PERM_TICKET_DELETE, PERM_TICKET_EDIT_ANY, PERM_TICKET_EDIT_OWN, User)
from services.context import AppContext
from services.ticket_manager import UNASSIGNED
from utils.exceptions import AppError
from views.dialogs import AssignDialog, StatusDialog, TicketDialog
from views.widgets import DateEntry, PriorityBadge, SLAMeter, StatusBadge

ALL = "Tất cả"
COLUMNS = (
    ("ticket_id", "Mã", 85, "center"),
    ("title", "Tiêu đề", 280, "w"),
    ("priority", "Ưu tiên", 85, "center"),
    ("status", "Trạng thái", 105, "center"),
    ("group", "Nhóm", 130, "w"),
    ("assignee", "Người xử lý", 100, "w"),
    ("requester", "Người yêu cầu", 105, "w"),
    ("created_at", "Ngày tạo", 115, "center"),
    ("sla", "SLA", 150, "w"),
)


class TicketsTab(ttk.Frame):
    """Vùng chứa chính dùng pack(); bộ lọc và panel chi tiết dùng grid() trong Frame riêng."""

    def __init__(self, master, ctx: AppContext, user: User,
                 on_count: Optional[Callable[[int, int], None]] = None):
        super().__init__(master, padding=config.PAD)
        self.ctx, self.user, self.on_count = ctx, user, on_count
        self.sort_col = "created_at"
        self.descending = tk.BooleanVar(value=True)
        self._shown: List[Ticket] = []

        self._build_filters()
        self._build_toolbar()
        self._build_body()
        self.refresh_lookups()
        self.apply_filters()

    # ==================================================================
    # Xây dựng giao diện
    # ==================================================================
    def _build_filters(self) -> None:
        box = ttk.LabelFrame(self, text="Tìm kiếm và lọc", padding=config.PAD)
        box.pack(fill="x")
        for col in (1, 3, 5, 7):
            box.columnconfigure(col, weight=1)

        self.keyword_var = tk.StringVar()
        self.status_var = tk.StringVar(value=ALL)
        self.priority_var = tk.StringVar(value=ALL)
        self.group_var = tk.StringVar(value=ALL)
        self.assignee_var = tk.StringVar(value=ALL)
        self.overdue_var = tk.BooleanVar(value=False)
        self.fuzzy_var = tk.BooleanVar(value=False)

        pad = {"padx": (0, 4), "pady": 3}
        ttk.Label(box, text="Từ khóa").grid(row=0, column=0, sticky="w", **pad)
        keyword = ttk.Entry(box, textvariable=self.keyword_var)
        keyword.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=3)
        keyword.bind("<Return>", self.apply_filters)

        ttk.Label(box, text="Trạng thái").grid(row=0, column=2, sticky="w", **pad)
        self.status_cb = ttk.Combobox(box, textvariable=self.status_var, state="readonly", width=14,
                                      values=[ALL] + [i["label"] for i in config.STATUS_INFO.values()])
        self.status_cb.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=3)

        ttk.Label(box, text="Ưu tiên").grid(row=0, column=4, sticky="w", **pad)
        self.priority_cb = ttk.Combobox(box, textvariable=self.priority_var, state="readonly", width=12,
                                        values=[ALL] + [i["label"] for i in config.PRIORITY_INFO.values()])
        self.priority_cb.grid(row=0, column=5, sticky="ew", padx=(0, 12), pady=3)

        ttk.Label(box, text="Nhóm").grid(row=0, column=6, sticky="w", **pad)
        self.group_cb = ttk.Combobox(box, textvariable=self.group_var, state="readonly", width=18)
        self.group_cb.grid(row=0, column=7, sticky="ew", pady=3)

        ttk.Label(box, text="Người xử lý").grid(row=1, column=0, sticky="w", **pad)
        self.assignee_cb = ttk.Combobox(box, textvariable=self.assignee_var, state="readonly", width=16)
        self.assignee_cb.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=3)

        ttk.Label(box, text="Từ ngày").grid(row=1, column=2, sticky="w", **pad)
        self.date_from = DateEntry(box)
        self.date_from.grid(row=1, column=3, sticky="ew", padx=(0, 12), pady=3)
        ttk.Label(box, text="Đến ngày").grid(row=1, column=4, sticky="w", **pad)
        self.date_to = DateEntry(box)
        self.date_to.grid(row=1, column=5, sticky="ew", padx=(0, 12), pady=3)

        opts = ttk.Frame(box)
        opts.grid(row=1, column=6, columnspan=2, sticky="w", pady=3)
        ttk.Checkbutton(opts, text="Chỉ quá hạn/trễ SLA", variable=self.overdue_var,
                        command=self.apply_filters).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(opts, text="Tìm gần đúng", variable=self.fuzzy_var,
                        command=self.apply_filters).pack(side="left")

        actions = ttk.Frame(box)
        actions.grid(row=2, column=0, columnspan=8, sticky="ew", pady=(6, 0))
        ttk.Label(actions, text="Sắp xếp:").pack(side="left")
        ttk.Radiobutton(actions, text="Giảm dần", variable=self.descending, value=True,
                        command=self.apply_filters).pack(side="left", padx=6)
        ttk.Radiobutton(actions, text="Tăng dần", variable=self.descending, value=False,
                        command=self.apply_filters).pack(side="left")
        ttk.Button(actions, text="Xóa bộ lọc", command=self.clear_filters).pack(side="right")
        ttk.Button(actions, text="Tìm kiếm", style="Primary.TButton",
                   command=self.apply_filters).pack(side="right", padx=6)

        for combo in (self.status_cb, self.priority_cb, self.group_cb, self.assignee_cb):
            combo.bind("<<ComboboxSelected>>", self.apply_filters)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(config.PAD, 4))
        self.btn_create = ttk.Button(bar, text="+ Tạo ticket", style="Primary.TButton", command=self.create_ticket)
        self.btn_edit = ttk.Button(bar, text="Sửa", command=self.edit_ticket)
        self.btn_assign = ttk.Button(bar, text="Phân công", command=self.assign_ticket)
        self.btn_status = ttk.Button(bar, text="Đổi trạng thái", command=self.change_status)
        self.btn_delete = ttk.Button(bar, text="Xóa", style="Danger.TButton", command=self.delete_ticket)
        for button in (self.btn_create, self.btn_edit, self.btn_assign, self.btn_status, self.btn_delete):
            button.pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Làm mới", command=self.reload).pack(side="left")
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var, style="Muted.TLabel").pack(side="right")

    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse")
        for cid, text, width, anchor in COLUMNS:
            self.tree.heading(cid, text=text, command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=width, anchor=anchor, stretch=(cid == "title"))
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("breached", background=config.COLOR_ROW_BREACHED)
        self.tree.tag_configure("missed", background=config.COLOR_ROW_BREACHED)
        self.tree.tag_configure("warning", background=config.COLOR_ROW_WARNING)
        self.tree.tag_configure("met", background=config.COLOR_ROW_DONE)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self.edit_ticket())
        self.tree.bind("<Delete>", lambda _e: self.delete_ticket())
        paned.add(left, weight=3)

        paned.add(self._build_detail(paned), weight=2)

    def _build_detail(self, parent) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=config.PAD)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(4, weight=1)

        self.detail_title = ttk.Label(panel, text="Chọn một ticket để xem chi tiết", style="Card.TLabel",
                                      font=config.FONT_BOLD, wraplength=380, justify="left")
        self.detail_title.grid(row=0, column=0, sticky="w")

        badges = ttk.Frame(panel, style="Card.TFrame")
        badges.grid(row=1, column=0, sticky="w", pady=4)
        self.priority_badge = PriorityBadge(badges)
        self.status_badge = StatusBadge(badges)
        self.priority_badge.pack(side="left", padx=(0, 6))
        self.status_badge.pack(side="left")

        self.detail_info = ttk.Label(panel, text="", style="Card.TLabel", justify="left", wraplength=380)
        self.detail_info.grid(row=2, column=0, sticky="w")
        self.sla_meter = SLAMeter(panel)
        self.sla_meter.grid(row=3, column=0, sticky="ew", pady=6)

        text_frame = ttk.Frame(panel, style="Card.TFrame")
        text_frame.grid(row=4, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.detail_text = tk.Text(text_frame, width=44, height=12, wrap="word", state="disabled",
                                   font=config.FONT_NORMAL, relief="flat", background=config.COLOR_PANEL)
        tsb = ttk.Scrollbar(text_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=tsb.set)
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        tsb.grid(row=0, column=1, sticky="ns")
        self.detail_text.tag_configure("h", font=config.FONT_BOLD, foreground=config.COLOR_PRIMARY, spacing1=6)
        self.detail_text.tag_configure("internal", foreground="#92400e")
        self.detail_text.tag_configure("muted", foreground=config.COLOR_MUTED)

        reply = ttk.Frame(panel, style="Card.TFrame")
        reply.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        reply.columnconfigure(0, weight=1)
        self.feedback_var = tk.StringVar()
        self.feedback_entry = ttk.Entry(reply, textvariable=self.feedback_var)
        self.feedback_entry.grid(row=0, column=0, sticky="ew")
        self.feedback_entry.bind("<Return>", lambda _e: self.send_feedback())
        self.internal_var = tk.BooleanVar(value=False)
        self.internal_cb = ttk.Checkbutton(reply, text="Nội bộ", variable=self.internal_var, style="Card.TCheckbutton")
        self.internal_cb.grid(row=0, column=1, padx=6)
        self.btn_send = ttk.Button(reply, text="Gửi phản hồi", command=self.send_feedback)
        self.btn_send.grid(row=0, column=2)
        if not self.user.can(PERM_INTERNAL_NOTE):
            self.internal_cb.grid_remove()
        return panel

    # ==================================================================
    # Dữ liệu và bộ lọc
    # ==================================================================
    def refresh_lookups(self) -> None:
        """Nạp lại danh sách nhóm và người xử lý cho các Combobox lọc."""
        self._group_by_name = {g.name: g.group_id for g in self.ctx.groups.list()}
        self.group_cb.configure(values=[ALL] + list(self._group_by_name))
        staff = [u.username for u in self.ctx.users.staff()]
        self.assignee_cb.configure(values=[ALL, NONE_ASSIGNEE] + staff)
        for var, values in ((self.group_var, self._group_by_name), (self.assignee_var, [ALL, NONE_ASSIGNEE] + staff)):
            if var.get() not in list(values) + [ALL]:
                var.set(ALL)

    @staticmethod
    def _code(label: str, table: dict) -> Optional[str]:
        for code, info in table.items():
            if info["label"] == label:
                return code
        return None

    def _search_args(self) -> dict:
        assignee = self.assignee_var.get()
        if assignee == ALL:
            assignee = None
        elif assignee == NONE_ASSIGNEE:
            assignee = UNASSIGNED
        return dict(
            keyword=self.keyword_var.get(),
            status=self._code(self.status_var.get(), config.STATUS_INFO),
            priority=self._code(self.priority_var.get(), config.PRIORITY_INFO),
            group_id=self._group_by_name.get(self.group_var.get()),
            assignee=assignee,
            date_from=self.date_from.get_date("Từ ngày"),
            date_to=self.date_to.get_date("Đến ngày"),
            overdue_only=self.overdue_var.get(),
            fuzzy=self.fuzzy_var.get(),
            sort_by=self.sort_col,
            descending=self.descending.get(),
        )

    def apply_filters(self, _event=None) -> None:
        try:
            tickets = self.ctx.tickets.search(self.user, **self._search_args())
        except AppError as exc:
            messagebox.showerror("Điều kiện tìm kiếm không hợp lệ", str(exc), parent=self)
            return
        self._fill(tickets)

    def clear_filters(self) -> None:
        self.keyword_var.set("")
        for var in (self.status_var, self.priority_var, self.group_var, self.assignee_var):
            var.set(ALL)
        self.date_from.clear()
        self.date_to.clear()
        self.overdue_var.set(False)
        self.fuzzy_var.set(False)
        self.apply_filters()

    def reload(self) -> None:
        """Làm mới từ file JSON rồi áp dụng lại bộ lọc."""
        try:
            self.ctx.tickets.reload()
        except AppError as exc:
            messagebox.showerror("Không đọc được dữ liệu", str(exc), parent=self)
            return
        self.refresh_lookups()
        self.apply_filters()

    def sort_by(self, column: str) -> None:
        if column == self.sort_col:
            self.descending.set(not self.descending.get())
        else:
            self.sort_col = column
            self.descending.set(column in ("created_at", "priority"))
        self.apply_filters()

    def current_tickets(self) -> List[Ticket]:
        return list(self._shown)

    @staticmethod
    def _sla_text(ticket: Ticket, now: datetime) -> str:
        state = ticket.sla_state(now)
        label = config.SLA_LABELS[state]
        if state in ("ok", "warning"):
            return f"{label} (còn {ticket.remaining_hours(now):.1f}h)"
        if state == "breached":
            return f"{label} (trễ {abs(ticket.remaining_hours(now)):.1f}h)"
        return label

    def _fill(self, tickets: List[Ticket]) -> None:
        selected = self.selected_id()
        self._shown = tickets
        names = self.ctx.group_names()
        now = datetime.now()
        self.tree.delete(*self.tree.get_children())
        for t in tickets:
            self.tree.insert("", "end", iid=t.ticket_id, tags=(t.sla_state(now),), values=(
                t.ticket_id, t.title, t.priority_label, t.status_label, names.get(t.group_id, ""),
                t.assignee, t.requester, t.created_at.strftime(config.DISPLAY_DT_FMT), self._sla_text(t, now)))
        total = len(self.ctx.tickets.list_for(self.user))
        self.count_var.set(f"Hiển thị {len(tickets)} / {total} ticket")
        if self.on_count:
            self.on_count(len(tickets), total)
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.see(selected)
        else:
            self._on_select()

    # ==================================================================
    # Chi tiết
    # ==================================================================
    def selected_id(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _selected_ticket(self) -> Optional[Ticket]:
        tid = self.selected_id()
        if not tid:
            return None
        try:
            return self.ctx.tickets.get(self.user, tid)
        except AppError:
            return None

    def _on_select(self, _event=None) -> None:
        ticket = self._selected_ticket()
        self._update_buttons(ticket)
        self._show_detail(ticket)

    def _show_detail(self, ticket: Optional[Ticket]) -> None:
        text = self.detail_text
        text.configure(state="normal")
        text.delete("1.0", "end")
        if ticket is None:
            self.detail_title.configure(text="Chọn một ticket để xem chi tiết")
            self.detail_info.configure(text="")
            self.sla_meter.clear()
            text.configure(state="disabled")
            return
        now = datetime.now()
        names = self.ctx.group_names()
        self.detail_title.configure(text=f"{ticket.ticket_id} - {ticket.title}")
        self.priority_badge.set_priority(ticket.priority)
        self.status_badge.set_status(ticket.status)
        hours = ticket.processing_hours()
        info = (f"Phân loại: {ticket.category}   |   Nhóm: {names.get(ticket.group_id, '-')}\n"
                f"Người yêu cầu: {ticket.requester}   |   Người xử lý: {ticket.assignee or '-'}\n"
                f"Tạo lúc: {ticket.created_at.strftime(config.DISPLAY_DT_FMT)}   |   "
                f"Hạn SLA: {ticket.due_at.strftime(config.DISPLAY_DT_FMT)}")
        if hours is not None:
            info += f"\nThời gian xử lý: {hours:.1f} giờ"
        self.detail_info.configure(text=info)
        state = ticket.sla_state(now)
        self.sla_meter.set_value(ticket.sla_ratio(now), f"{config.SLA_LABELS[state]} - {ticket.sla_ratio(now) * 100:.0f}% thời gian SLA", state)

        text.insert("end", "MÔ TẢ\n", "h")
        text.insert("end", ticket.description + "\n")
        if ticket.attachment:
            text.insert("end", f"Đính kèm: {ticket.attachment}\n", "muted")
        text.insert("end", "\nPHẢN HỒI\n", "h")
        feedbacks = ticket.visible_feedbacks(self.user.can(PERM_INTERNAL_NOTE))
        if not feedbacks:
            text.insert("end", "(chưa có phản hồi)\n", "muted")
        for fb in feedbacks:
            tag = "internal" if fb.internal else ""
            label = " [nội bộ]" if fb.internal else ""
            text.insert("end", f"[{fb.created_at.strftime('%d/%m %H:%M')}] {fb.author}{label}: {fb.content}\n", tag)
        text.insert("end", "\nLỊCH SỬ XỬ LÝ\n", "h")
        for h in reversed(ticket.history):
            text.insert("end", f"{h.time.strftime('%d/%m %H:%M')}  {h.actor}: {h.action}"
                               f"{' - ' + h.detail if h.detail else ''}\n", "muted")
        text.configure(state="disabled")

    def _update_buttons(self, ticket: Optional[Ticket]) -> None:
        user = self.user
        can_edit = bool(ticket) and (
            user.can(PERM_TICKET_EDIT_ANY)
            or (user.can(PERM_TICKET_EDIT_OWN) and ticket.requester == user.username and ticket.status == "new"))
        states = {
            self.btn_create: user.can(PERM_TICKET_CREATE),
            self.btn_edit: can_edit,
            self.btn_assign: bool(ticket) and ticket.is_open and user.can(PERM_TICKET_ASSIGN),
            self.btn_status: bool(ticket) and bool(self.ctx.tickets.allowed_statuses(user, ticket)),
            self.btn_delete: bool(ticket) and user.can(PERM_TICKET_DELETE),
            self.btn_send: bool(ticket) and user.can(PERM_FEEDBACK) and ticket.status != "closed",
        }
        for button, enabled in states.items():
            button.configure(state="normal" if enabled else "disabled")
        self.feedback_entry.configure(state="normal" if states[self.btn_send] else "disabled")

    # ==================================================================
    # Thao tác
    # ==================================================================
    def _after_change(self, ticket: Optional[Ticket] = None) -> None:
        self.refresh_lookups()
        self.apply_filters()
        if ticket is not None and self.tree.exists(ticket.ticket_id):
            self.tree.selection_set(ticket.ticket_id)
            self.tree.see(ticket.ticket_id)

    def create_ticket(self) -> None:
        TicketDialog(self, self.ctx, self.user, None, self._after_change)

    def edit_ticket(self) -> None:
        ticket = self._selected_ticket()
        if ticket is None or str(self.btn_edit.cget("state")) == "disabled":
            return
        TicketDialog(self, self.ctx, self.user, ticket, self._after_change)

    def assign_ticket(self) -> None:
        ticket = self._selected_ticket()
        if ticket:
            AssignDialog(self, self.ctx, self.user, ticket, self._after_change)

    def change_status(self) -> None:
        ticket = self._selected_ticket()
        if ticket:
            StatusDialog(self, self.ctx, self.user, ticket, self._after_change)

    def delete_ticket(self) -> None:
        ticket = self._selected_ticket()
        if ticket is None or str(self.btn_delete.cget("state")) == "disabled":
            return
        if not messagebox.askyesno("Xác nhận xóa", f"Xóa vĩnh viễn ticket {ticket.ticket_id}?\n"
                                                    f"Thao tác này không thể hoàn tác.", icon="warning", parent=self):
            return
        try:
            self.ctx.tickets.delete(self.user, ticket.ticket_id)
        except AppError as exc:
            messagebox.showerror("Không thể xóa", str(exc), parent=self)
            return
        self._after_change()

    def send_feedback(self) -> None:
        ticket = self._selected_ticket()
        content = self.feedback_var.get().strip()
        if ticket is None or str(self.btn_send.cget("state")) == "disabled":
            return
        if not content:
            messagebox.showwarning("Thiếu nội dung", "Vui lòng nhập nội dung phản hồi.", parent=self)
            return
        try:
            self.ctx.tickets.add_feedback(self.user, ticket.ticket_id, content, self.internal_var.get())
        except AppError as exc:
            messagebox.showerror("Không thể gửi phản hồi", str(exc), parent=self)
            return
        self.feedback_var.set("")
        self.internal_var.set(False)
        self._show_detail(ticket)


NONE_ASSIGNEE = "(chưa phân công)"
