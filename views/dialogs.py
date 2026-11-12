"""Các hộp thoại (Toplevel) của ứng dụng.

Mỗi hộp thoại dùng grid() trong vùng chứa chính (`self.body`); riêng hàng nút
bấm nằm trong một Frame riêng dùng pack() nên không trộn hai layout manager.
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional

import config
from models.ticket import Ticket
from models.user import PERM_TICKET_EDIT_ANY, User
from services.context import AppContext
from utils import validators as v
from utils.exceptions import AppError
from views.widgets import LabeledEntry

NONE_LABEL = "(chưa phân công)"


class BaseDialog(tk.Toplevel):
    """Khung hộp thoại modal: căn giữa, đóng bằng Esc, có hàng nút OK/Hủy."""

    def __init__(self, parent: tk.Widget, title: str):
        super().__init__(parent)
        self.title(title)
        self.configure(background=config.COLOR_BG)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.body = ttk.Frame(self, padding=config.PAD * 2)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _e: self.destroy())

    def add_buttons(self, row: int, ok_text: str, ok_command: Callable[[], None], columnspan: int = 2) -> None:
        bar = ttk.Frame(self.body)
        bar.grid(row=row, column=0, columnspan=columnspan, sticky="e", pady=(config.PAD * 2, 0))
        ttk.Button(bar, text="Hủy", command=self.destroy).pack(side="right", padx=(config.PAD, 0))
        ttk.Button(bar, text=ok_text, style="Primary.TButton", command=ok_command).pack(side="right")

    def finish(self) -> None:
        """Căn giữa theo cửa sổ cha và khóa tương tác với cửa sổ cha."""
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def error(self, title: str, exc: Exception) -> None:
        messagebox.showerror(title, str(exc), parent=self)


# ======================================================================
# Ticket
# ======================================================================
class TicketDialog(BaseDialog):
    """Tạo mới hoặc sửa ticket."""

    def __init__(self, parent, ctx: AppContext, user: User, ticket: Optional[Ticket] = None,
                 on_done: Optional[Callable[[Ticket], None]] = None):
        super().__init__(parent, "Sửa ticket" if ticket else "Tạo ticket mới")
        self.ctx, self.user, self.ticket, self.on_done = ctx, user, ticket, on_done
        self._attachment_src = ""

        self.title_entry = LabeledEntry(self.body, "Tiêu đề (5-120 ký tự) *", width=60)
        self.title_entry.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(self.body, text="Phân loại *").grid(row=1, column=0, sticky="w", pady=4)
        self.category_var = tk.StringVar(value=config.CATEGORIES[0])
        ttk.Combobox(self.body, textvariable=self.category_var, values=config.CATEGORIES,
                     state="readonly").grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(self.body, text="Mức ưu tiên *").grid(row=2, column=0, sticky="nw", pady=4)
        self.priority_var = tk.StringVar(value="medium")
        prio_frame = ttk.Frame(self.body)
        prio_frame.grid(row=2, column=1, sticky="w", pady=4)
        for code, info in config.PRIORITY_INFO.items():
            ttk.Radiobutton(prio_frame, text=f"{info['label']} (SLA {info['sla_hours']}h)",
                            variable=self.priority_var, value=code).pack(side="left", padx=(0, 10))

        ttk.Label(self.body, text="Người yêu cầu").grid(row=3, column=0, sticky="w", pady=4)
        self.requester_var = tk.StringVar(value=user.username)
        if ticket is None and user.is_staff:
            names = [u.username for u in ctx.users.list(config.ROLE_USER)] or [user.username]
            ttk.Combobox(self.body, textvariable=self.requester_var, values=[user.username] + names,
                         state="readonly").grid(row=3, column=1, sticky="ew", pady=4)
        else:
            owner = ticket.requester if ticket else user.username
            self.requester_var.set(owner)
            ttk.Label(self.body, text=owner).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(self.body, text="Mô tả (10-2000 ký tự) *").grid(row=4, column=0, sticky="nw", pady=4)
        text_frame = ttk.Frame(self.body)
        text_frame.grid(row=4, column=1, sticky="nsew", pady=4)
        text_frame.columnconfigure(0, weight=1)
        self.description = tk.Text(text_frame, width=58, height=8, wrap="word", font=config.FONT_NORMAL)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.description.yview)
        self.description.configure(yscrollcommand=scroll.set)
        self.description.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        ttk.Label(self.body, text="Tệp đính kèm").grid(row=5, column=0, sticky="w", pady=4)
        attach = ttk.Frame(self.body)
        attach.grid(row=5, column=1, sticky="ew", pady=4)
        self.attach_var = tk.StringVar(value=ticket.attachment if ticket else "")
        ttk.Entry(attach, textvariable=self.attach_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(attach, text="Chọn tệp…", command=self._choose_file).pack(side="left", padx=(6, 0))

        if ticket:
            self.title_entry.set(ticket.title)
            self.category_var.set(ticket.category)
            self.priority_var.set(ticket.priority)
            self.description.insert("1.0", ticket.description)
        self.add_buttons(6, "Lưu" if ticket else "Tạo ticket", self._submit)
        self.title_entry.focus()
        self.finish()

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Chọn tệp đính kèm")
        if path:
            self._attachment_src = path
            self.attach_var.set(path.replace("\\", "/").split("/")[-1])

    def _submit(self) -> None:
        title = self.title_entry.get()
        description = self.description.get("1.0", "end")
        try:
            if self.ticket:
                result = self.ctx.tickets.update(self.user, self.ticket.ticket_id, title, description,
                                                 self.category_var.get(), self.priority_var.get(),
                                                 self._attachment_src)
            else:
                result = self.ctx.tickets.create(self.user, title, description, self.category_var.get(),
                                                 self.priority_var.get(), self.requester_var.get(),
                                                 self._attachment_src)
        except AppError as exc:
            self.error("Không thể lưu ticket", exc)
            return
        self.destroy()
        if self.on_done:
            self.on_done(result)


class AssignDialog(BaseDialog):
    """Phân công nhóm hỗ trợ và người xử lý."""

    def __init__(self, parent, ctx: AppContext, user: User, ticket: Ticket,
                 on_done: Optional[Callable[[Ticket], None]] = None):
        super().__init__(parent, f"Phân công {ticket.ticket_id}")
        self.ctx, self.user, self.ticket, self.on_done = ctx, user, ticket, on_done
        self._groups: Dict[str, str] = {g.name: g.group_id for g in ctx.groups.list()}

        ttk.Label(self.body, text=ticket.title, font=config.FONT_BOLD, wraplength=360).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(self.body, text="Nhóm hỗ trợ").grid(row=1, column=0, sticky="w", pady=4)
        group_names = list(self._groups)
        self.group_var = tk.StringVar(value=ctx.groups.name_of(ticket.group_id) if ticket.group_id else "")
        ttk.Combobox(self.body, textvariable=self.group_var, values=group_names, state="readonly",
                     width=32).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(self.body, text="Người xử lý").grid(row=2, column=0, sticky="w", pady=4)
        if user.role == config.ROLE_AGENT:
            candidates = [user.username]          # kỹ thuật viên chỉ nhận cho chính mình
        else:
            candidates = [u.username for u in ctx.users.staff()]
        self.assignee_var = tk.StringVar(value=ticket.assignee or NONE_LABEL)
        ttk.Combobox(self.body, textvariable=self.assignee_var, values=[NONE_LABEL] + candidates,
                     state="readonly", width=32).grid(row=2, column=1, sticky="ew", pady=4)
        self.add_buttons(3, "Phân công", self._submit)
        self.finish()

    def _submit(self) -> None:
        assignee = self.assignee_var.get()
        assignee = "" if assignee == NONE_LABEL else assignee
        group_id = self._groups.get(self.group_var.get(), "")
        try:
            result = self.ctx.tickets.assign(self.user, self.ticket.ticket_id, assignee, group_id)
        except AppError as exc:
            self.error("Không thể phân công", exc)
            return
        self.destroy()
        if self.on_done:
            self.on_done(result)


class StatusDialog(BaseDialog):
    """Đổi trạng thái ticket theo quy trình cho phép."""

    def __init__(self, parent, ctx: AppContext, user: User, ticket: Ticket,
                 on_done: Optional[Callable[[Ticket], None]] = None):
        super().__init__(parent, f"Đổi trạng thái {ticket.ticket_id}")
        self.ctx, self.user, self.ticket, self.on_done = ctx, user, ticket, on_done
        allowed = ctx.tickets.allowed_statuses(user, ticket)
        self._label_to_code = {config.STATUS_INFO[c]["label"]: c for c in allowed}

        ttk.Label(self.body, text=f"Trạng thái hiện tại: {ticket.status_label}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(self.body, text="Chuyển sang").grid(row=1, column=0, sticky="w", pady=4)
        self.status_var = tk.StringVar(value=next(iter(self._label_to_code), ""))
        ttk.Combobox(self.body, textvariable=self.status_var, values=list(self._label_to_code),
                     state="readonly", width=28).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(self.body, text="Ghi chú").grid(row=2, column=0, sticky="w", pady=4)
        self.note_var = tk.StringVar()
        ttk.Entry(self.body, textvariable=self.note_var, width=40).grid(row=2, column=1, sticky="ew", pady=4)
        self.add_buttons(3, "Cập nhật", self._submit)
        self.finish()

    def _submit(self) -> None:
        code = self._label_to_code.get(self.status_var.get())
        if not code:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn trạng thái mới.", parent=self)
            return
        try:
            result = self.ctx.tickets.change_status(self.user, self.ticket.ticket_id, code, self.note_var.get())
        except AppError as exc:
            self.error("Không thể đổi trạng thái", exc)
            return
        self.destroy()
        if self.on_done:
            self.on_done(result)


# ======================================================================
# Tài khoản
# ======================================================================
class ChangePasswordDialog(BaseDialog):
    def __init__(self, parent, ctx: AppContext, user: User):
        super().__init__(parent, "Đổi mật khẩu")
        self.ctx, self.user = ctx, user
        self.old = LabeledEntry(self.body, "Mật khẩu hiện tại", show="*")
        self.new = LabeledEntry(self.body, "Mật khẩu mới (>= 6 ký tự, có chữ và số)",
                                validator=v.validate_password, show="*")
        self.confirm = LabeledEntry(self.body, "Nhập lại mật khẩu mới", show="*")
        for row, widget in enumerate((self.old, self.new, self.confirm)):
            widget.grid(row=row, column=0, columnspan=2, sticky="ew")
        self.add_buttons(3, "Đổi mật khẩu", self._submit)
        self.old.focus()
        self.finish()

    def _submit(self) -> None:
        try:
            self.ctx.auth.change_password(self.user, self.old.get(), self.new.get(), self.confirm.get())
        except AppError as exc:
            self.error("Không thể đổi mật khẩu", exc)
            return
        messagebox.showinfo("Thành công", "Đã đổi mật khẩu.", parent=self)
        self.destroy()


class UserDialog(BaseDialog):
    """Quản trị viên thêm hoặc sửa tài khoản."""

    def __init__(self, parent, ctx: AppContext, actor: User, target: Optional[User] = None,
                 on_done: Optional[Callable[[], None]] = None):
        super().__init__(parent, "Sửa tài khoản" if target else "Thêm tài khoản")
        self.ctx, self.actor, self.target, self.on_done = ctx, actor, target, on_done
        self.username = LabeledEntry(self.body, "Tên đăng nhập *", validator=v.validate_username)
        self.full_name = LabeledEntry(self.body, "Họ và tên *",
                                      validator=lambda s: v.validate_text(s, "Họ tên", 2, 60))
        self.email = LabeledEntry(self.body, "Email *", validator=v.validate_email)
        self.phone = LabeledEntry(self.body, "Số điện thoại",
                                  validator=lambda s: v.validate_phone(s, required=False))
        self.password = LabeledEntry(self.body, "Mật khẩu *", validator=v.validate_password, show="*")
        fields = [self.username, self.full_name, self.email, self.phone]
        if target is None:
            fields.append(self.password)
        for row, widget in enumerate(fields):
            widget.grid(row=row, column=0, columnspan=2, sticky="ew")
        row = len(fields)

        ttk.Label(self.body, text="Vai trò").grid(row=row, column=0, sticky="w", pady=4)
        self._role_by_label = {label: code for code, label in config.ROLE_LABELS.items()}
        self.role_var = tk.StringVar(value=config.ROLE_LABELS[config.ROLE_USER])
        ttk.Combobox(self.body, textvariable=self.role_var, values=list(self._role_by_label),
                     state="readonly").grid(row=row, column=1, sticky="ew", pady=4)
        self.active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.body, text="Tài khoản đang hoạt động", variable=self.active_var).grid(
            row=row + 1, column=0, columnspan=2, sticky="w")

        if target:
            self.username.set(target.username)
            self.username.set_enabled(False)
            self.full_name.set(target.full_name)
            self.email.set(target.email)
            self.phone.set(target.phone)
            self.role_var.set(target.role_label)
            self.active_var.set(target.active)
        self.add_buttons(row + 2, "Lưu", self._submit)
        self.finish()

    def _submit(self) -> None:
        role = self._role_by_label[self.role_var.get()]
        try:
            if self.target:
                self.ctx.users.update(self.actor, self.target.username, self.full_name.get(),
                                      self.email.get(), self.phone.get(), role, self.active_var.get())
            else:
                self.ctx.users.create(self.actor, self.username.get(), self.full_name.get(),
                                      self.email.get(), self.phone.get(), self.password.get(), role)
        except AppError as exc:
            self.error("Không thể lưu tài khoản", exc)
            return
        self.destroy()
        if self.on_done:
            self.on_done()


class GroupDialog(BaseDialog):
    """Thêm hoặc sửa nhóm hỗ trợ."""

    def __init__(self, parent, ctx: AppContext, actor: User, group=None,
                 on_done: Optional[Callable[[], None]] = None):
        super().__init__(parent, "Sửa nhóm hỗ trợ" if group else "Thêm nhóm hỗ trợ")
        self.ctx, self.actor, self.group, self.on_done = ctx, actor, group, on_done
        self.group_id = LabeledEntry(self.body, "Mã nhóm * (ví dụ G05)", validator=v.validate_group_id)
        self.name = LabeledEntry(self.body, "Tên nhóm *", validator=lambda s: v.validate_text(s, "Tên nhóm", 3, 50))
        self.description = LabeledEntry(self.body, "Mô tả")
        for row, widget in enumerate((self.group_id, self.name, self.description)):
            widget.grid(row=row, column=0, columnspan=2, sticky="ew")
        ttk.Label(self.body, text="Trưởng nhóm").grid(row=3, column=0, sticky="w", pady=4)
        self.lead_var = tk.StringVar()
        ttk.Combobox(self.body, textvariable=self.lead_var, state="readonly",
                     values=[""] + [u.username for u in ctx.users.staff()]).grid(row=3, column=1, sticky="ew", pady=4)
        if group:
            self.group_id.set(group.group_id)
            self.group_id.set_enabled(False)
            self.name.set(group.name)
            self.description.set(group.description)
            self.lead_var.set(group.lead)
        self.add_buttons(4, "Lưu", self._submit)
        self.finish()

    def _submit(self) -> None:
        try:
            if self.group:
                self.ctx.groups.update(self.actor, self.group.group_id, self.name.get(),
                                       self.description.get(), self.lead_var.get())
            else:
                self.ctx.groups.create(self.actor, self.group_id.get(), self.name.get(),
                                       self.description.get(), self.lead_var.get())
        except AppError as exc:
            self.error("Không thể lưu nhóm", exc)
            return
        self.destroy()
        if self.on_done:
            self.on_done()


# ======================================================================
# Công cụ: API, nhật ký
# ======================================================================
class ApiImportDialog(BaseDialog):
    """Lấy issue từ GitHub API (chạy nền để không treo giao diện) và nhập thành ticket."""

    def __init__(self, parent, ctx: AppContext, actor: User,
                 on_done: Optional[Callable[[int, int], None]] = None):
        super().__init__(parent, "Nhập dữ liệu từ API (GitHub Issues)")
        self.ctx, self.actor, self.on_done = ctx, actor, on_done
        self.records: List[dict] = []
        self._result = None

        ttk.Label(self.body, text="Repository (chủ-sở-hữu/tên)").grid(row=0, column=0, sticky="w", pady=4)
        self.repo_var = tk.StringVar(value=config.API_DEFAULT_REPO)
        ttk.Entry(self.body, textvariable=self.repo_var, width=36).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(self.body, text="Số issue tối đa").grid(row=1, column=0, sticky="w", pady=4)
        self.limit_var = tk.StringVar(value=str(config.API_MAX_ITEMS))
        ttk.Combobox(self.body, textvariable=self.limit_var, values=["10", "20", "30", "50"],
                     state="readonly", width=8).grid(row=1, column=1, sticky="w", pady=4)

        bar = ttk.Frame(self.body)
        bar.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        self.fetch_btn = ttk.Button(bar, text="Lấy dữ liệu từ API", style="Primary.TButton", command=self._fetch)
        self.fetch_btn.pack(side="left")
        ttk.Button(bar, text="Dùng dữ liệu đã lưu", command=self._load_cached).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="Nguồn: api.github.com (API công khai, giới hạn 60 lượt/giờ).")
        ttk.Label(self.body, textvariable=self.status_var, style="Muted.TLabel", wraplength=430).grid(
            row=3, column=0, columnspan=2, sticky="w")

        list_frame = ttk.Frame(self.body)
        list_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=6)
        list_frame.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(list_frame, height=10, width=70, activestyle="none")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self.import_btn = ttk.Button(self.body, text="Nhập vào hệ thống", command=self._import, state="disabled")
        self.import_btn.grid(row=5, column=0, columnspan=2, sticky="e")
        self.finish()

    def _show(self, records: List[dict]) -> None:
        self.records = records
        self.listbox.delete(0, "end")
        for rec in records:
            self.listbox.insert("end", f"{rec['external_ref'].split(':')[-1]:<14} [{rec['category']}/"
                                       f"{config.PRIORITY_INFO[rec['priority']]['label']}] {rec['title']}")
        self.import_btn.configure(state="normal" if records else "disabled")

    def _fetch(self) -> None:
        try:
            limit = int(self.limit_var.get())
        except ValueError:
            messagebox.showerror("Dữ liệu không hợp lệ", "Số issue tối đa phải là số nguyên.", parent=self)
            return
        repo = self.repo_var.get()
        self.fetch_btn.configure(state="disabled")
        self.status_var.set("Đang tải dữ liệu, vui lòng chờ…")
        self._result = None

        def worker() -> None:
            try:
                self._result = ("ok", self.ctx.api.fetch_issues(repo, limit))
            except AppError as exc:
                self._result = ("error", str(exc))
            except Exception as exc:    # noqa: BLE001 - luồng nền phải báo mọi lỗi về giao diện, nếu không sẽ treo
                self._result = ("error", f"Lỗi không xác định: {exc}")

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        if self._result is None:
            self.after(150, self._poll)
            return
        kind, payload = self._result
        self.fetch_btn.configure(state="normal")
        if kind == "ok":
            self._show(payload)
            self.status_var.set(f"Đã lấy {len(payload)} issue và lưu vào data/{config.API_CACHE_FILE_NAME}.")
        else:
            self.status_var.set("Không lấy được dữ liệu.")
            messagebox.showerror("Lỗi API", payload, parent=self)

    def _load_cached(self) -> None:
        try:
            records = self.ctx.api.load_cached()
        except AppError as exc:
            self.error("Không đọc được dữ liệu đã lưu", exc)
            return
        if not records:
            messagebox.showinfo("Chưa có dữ liệu", "Chưa có dữ liệu API đã lưu. Hãy bấm 'Lấy dữ liệu từ API'.",
                                parent=self)
            return
        self._show(records)
        self.status_var.set(f"Đang dùng {len(records)} issue đã lưu trong file JSON.")

    def _import(self) -> None:
        try:
            added, skipped = self.ctx.tickets.import_external(self.actor, self.records)
        except AppError as exc:
            self.error("Không thể nhập dữ liệu", exc)
            return
        messagebox.showinfo("Hoàn tất", f"Đã thêm {added} ticket, bỏ qua {skipped} (trùng hoặc không hợp lệ).",
                            parent=self)
        self.destroy()
        if self.on_done:
            self.on_done(added, skipped)


class LogDialog(BaseDialog):
    """Xem nhật ký hoạt động gần nhất."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, "Nhật ký hoạt động")
        self.resizable(True, True)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        text = tk.Text(self.body, width=110, height=24, wrap="none", font=("Consolas", 9))
        vsb = ttk.Scrollbar(self.body, orient="vertical", command=text.yview)
        hsb = ttk.Scrollbar(self.body, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        lines = ctx.logger.tail(300)
        text.insert("1.0", "\n".join(lines) if lines else "(Chưa có nhật ký)")
        text.see("end")
        text.configure(state="disabled")
        self.finish()
