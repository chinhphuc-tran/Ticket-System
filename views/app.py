import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import config
from models.user import (PERM_API_IMPORT, PERM_EXPORT, PERM_STATS, PERM_USER_MANAGE, PERM_GROUP_MANAGE,
                         PERM_DATA_ADMIN, User)
from services import report_service
from services.context import AppContext
from utils import sys_info
from utils.exceptions import AppError
from views.admin_tab import AdminTab
from views.dashboard_tab import DashboardTab
from views.dialogs import ApiImportDialog, ChangePasswordDialog
from views.login_view import LoginView
from views.styles import apply_style
from views.tickets_tab import TicketsTab


class TicketApp:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.root = tk.Tk()
        self.root.title(config.APP_TITLE)
        self.root.geometry("1280x760")
        self.root.minsize(1000, 640)
        apply_style(self.root)

        self.user: Optional[User] = None
        self.current_view: Optional[ttk.Frame] = None
        self.tickets_tab: Optional[TicketsTab] = None
        self.dashboard_tab: Optional[DashboardTab] = None
        self.status_var = tk.StringVar(value="Sẵn sàng")

        status_bar = ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel", anchor="w", padding=(8, 3))
        status_bar.pack(side="bottom", fill="x")
        self.container = ttk.Frame(self.root)
        self.container.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_login()
        self.root.after(300, self._show_startup_warnings)

    def run(self) -> None:
        self.root.mainloop()

    # ------------------------------------------------------------------
    def _show_startup_warnings(self) -> None:
        for message in self.ctx.startup_warnings():
            messagebox.showwarning("Cảnh báo dữ liệu", message, parent=self.root)

    def _swap_view(self, view: ttk.Frame) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
        self.current_view = view
        view.pack(fill="both", expand=True)

    def _set_menu(self, menu: Optional[tk.Menu]) -> None:
        self.root.configure(menu=menu if menu else tk.Menu(self.root))

    # Đăng nhập / đăng xuất
    def show_login(self) -> None:
        self.user = None
        self.tickets_tab = self.dashboard_tab = None
        self._set_menu(None)
        self._swap_view(LoginView(self.container, self.ctx, self.show_main))
        self.status_var.set("Vui lòng đăng nhập")

    def show_main(self, user: User) -> None:
        self.user = user
        self._build_menu()
        main = ttk.Frame(self.container)
        header = ttk.Frame(main, padding=(config.PAD, config.PAD, config.PAD, 0))
        header.pack(fill="x")
        ttk.Label(header, text=config.APP_TITLE, style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Đăng xuất", command=self.logout).pack(side="right")
        ttk.Label(header, text=f"{user.full_name}  ({user.role_label})", style="Muted.TLabel").pack(
            side="right", padx=12)

        book = ttk.Notebook(main)
        book.pack(fill="both", expand=True, padx=config.PAD, pady=config.PAD)
        self.tickets_tab = TicketsTab(book, self.ctx, user, self._on_count)
        book.add(self.tickets_tab, text="Ticket")
        if user.can(PERM_STATS):
            self.dashboard_tab = DashboardTab(book, self.ctx, user)
            book.add(self.dashboard_tab, text="Thống kê")
        if user.can(PERM_USER_MANAGE) or user.can(PERM_GROUP_MANAGE) or user.can(PERM_DATA_ADMIN):
            book.add(AdminTab(book, self.ctx, user, self._data_changed), text="Quản trị")
        book.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())
        self._book = book
        self._swap_view(main)
        self.status_var.set(f"Đã đăng nhập: {user.username} - {datetime.now().strftime(config.DISPLAY_DT_FMT)}")

    def logout(self) -> None:
        self.ctx.auth.logout()
        self.show_login()

    def _on_tab_changed(self) -> None:
        if self.dashboard_tab is not None and self._book.select() == str(self.dashboard_tab):
            self.dashboard_tab.refresh()

    def _on_count(self, shown: int, total: int) -> None:
        self.status_var.set(f"Hiển thị {shown}/{total} ticket  |  Người dùng: {self.user.username}")

    def _data_changed(self) -> None:
        if self.tickets_tab:
            self.tickets_tab.refresh_lookups()
            self.tickets_tab.apply_filters()
        if self.dashboard_tab:
            self.dashboard_tab.refresh()

    # Menu
    def _build_menu(self) -> None:
        user = self.user
        bar = tk.Menu(self.root)
        file_menu = tk.Menu(bar, tearoff=False)
        if user.can(PERM_EXPORT):
            file_menu.add_command(label="Xuất danh sách ticket (CSV)…", command=lambda: self._export("csv"))
            file_menu.add_command(label="Xuất danh sách ticket (JSON)…", command=lambda: self._export("json"))
            file_menu.add_command(label="Xuất báo cáo tổng hợp (TXT)…", command=lambda: self._export("txt"))
            file_menu.add_separator()
        if user.can(PERM_API_IMPORT):
            file_menu.add_command(label="Nhập dữ liệu từ API…",
                                  command=lambda: ApiImportDialog(self.root, self.ctx, user, self._api_done))
            file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self._on_close)
        bar.add_cascade(label="Tệp", menu=file_menu)

        account = tk.Menu(bar, tearoff=False)
        account.add_command(label="Đổi mật khẩu…", command=lambda: ChangePasswordDialog(self.root, self.ctx, user))
        account.add_command(label="Đăng xuất", command=self.logout)
        bar.add_cascade(label="Tài khoản", menu=account)

        help_menu = tk.Menu(bar, tearoff=False)
        help_menu.add_command(label="Thông tin hệ thống", command=self._about)
        bar.add_cascade(label="Trợ giúp", menu=help_menu)
        self._set_menu(bar)

    def _api_done(self, added: int, _skipped: int) -> None:
        self._data_changed()
        self.status_var.set(f"Đã nhập {added} ticket từ API")

    def _export(self, kind: str) -> None:
        tickets = self.tickets_tab.current_tickets() if self.tickets_tab else self.ctx.tickets.list_for(self.user)
        if not tickets:
            messagebox.showinfo("Không có dữ liệu", "Danh sách ticket đang trống, không có gì để xuất.", parent=self.root)
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        types = {"csv": ("CSV", "*.csv"), "json": ("JSON", "*.json"), "txt": ("Văn bản", "*.txt")}
        label, pattern = types[kind]
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Lưu file", defaultextension=pattern[1:],
            initialfile=f"tickets_{stamp}{pattern[1:]}", filetypes=[(label, pattern)])
        if not path:
            return
        names = self.ctx.group_names()
        try:
            if kind == "csv":
                saved = report_service.export_csv(tickets, path, names)
            elif kind == "json":
                saved = report_service.export_json(tickets, path)
            else:
                saved = report_service.export_summary(tickets, path, names, self.user.username)
        except AppError as exc:
            messagebox.showerror("Xuất file thất bại", str(exc), parent=self.root)
            return
        self.ctx.logger.log(self.user.username, "EXPORT", f"{kind}: {saved.name}")
        messagebox.showinfo("Thành công", f"Đã xuất {len(tickets)} ticket ra:\n{saved}", parent=self.root)

    def _about(self) -> None:
        messagebox.showinfo("Thông tin hệ thống", sys_info.environment_summary(), parent=self.root)

    def _on_close(self) -> None:
        if messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát ứng dụng?", parent=self.root):
            self.ctx.auth.logout()
            self.root.destroy()
