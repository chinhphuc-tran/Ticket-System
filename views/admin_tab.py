"""Tab quản trị: tài khoản, nhóm hỗ trợ, dữ liệu (sao lưu/khôi phục/mẫu), nhật ký."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Optional

import config
from models.user import PERM_DATA_ADMIN, PERM_GROUP_MANAGE, PERM_USER_MANAGE, User
from services import sample_data
from services.context import AppContext
from utils import validators as v
from utils.exceptions import AppError
from views.dialogs import GroupDialog, LogDialog, UserDialog


class AdminTab(ttk.Frame):
    """Notebook con: mỗi trang dùng grid() trong Frame riêng của nó."""

    def __init__(self, master, ctx: AppContext, user: User, on_data_changed: Callable[[], None]):
        super().__init__(master, padding=config.PAD)
        self.ctx, self.user, self.on_data_changed = ctx, user, on_data_changed
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True)
        if user.can(PERM_USER_MANAGE):
            book.add(self._build_users(book), text="Tài khoản")
        if user.can(PERM_GROUP_MANAGE):
            book.add(self._build_groups(book), text="Nhóm hỗ trợ")
        if user.can(PERM_DATA_ADMIN):
            book.add(self._build_data(book), text="Dữ liệu và nhật ký")

    # ------------------------------------------------------------------
    @staticmethod
    def _tree(parent, columns) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for cid, text, width in columns:
            tree.heading(cid, text=text)
            tree.column(cid, width=width, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        return tree

    # Tài khoản
    def _build_users(self, book) -> ttk.Frame:
        page = ttk.Frame(book, padding=config.PAD)
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 6))
        self.user_search = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.user_search, width=26)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self.refresh_users())
        ttk.Button(bar, text="Tìm", command=self.refresh_users).pack(side="left", padx=4)
        for text, cmd, style in (("Thêm", self._add_user, "Primary.TButton"), ("Sửa", self._edit_user, "TButton"),
                                 ("Đặt lại mật khẩu", self._reset_password, "TButton"),
                                 ("Xóa", self._delete_user, "Danger.TButton")):
            ttk.Button(bar, text=text, style=style, command=cmd).pack(side="right", padx=(4, 0))
        self.user_tree = self._tree(page, (("username", "Tên đăng nhập", 130), ("full_name", "Họ tên", 190),
                                           ("email", "Email", 210), ("phone", "Điện thoại", 110),
                                           ("role", "Vai trò", 150), ("active", "Trạng thái", 90)))
        self.user_tree.bind("<Double-1>", lambda _e: self._edit_user())
        self.refresh_users()
        return page

    def refresh_users(self) -> None:
        self.user_tree.delete(*self.user_tree.get_children())
        for u in self.ctx.users.search(self.user_search.get()):
            self.user_tree.insert("", "end", iid=u.username, values=(
                u.username, u.full_name, u.email, u.phone, u.role_label, "Hoạt động" if u.active else "Đã khóa"))

    def _selected_user(self) -> Optional[User]:
        sel = self.user_tree.selection()
        if not sel:
            messagebox.showinfo("Chưa chọn", "Vui lòng chọn một tài khoản trong danh sách.", parent=self)
            return None
        return self.ctx.users.find(sel[0])

    def _add_user(self) -> None:
        UserDialog(self, self.ctx, self.user, None, self._users_changed)

    def _edit_user(self) -> None:
        target = self._selected_user()
        if target:
            UserDialog(self, self.ctx, self.user, target, self._users_changed)

    def _users_changed(self) -> None:
        self.refresh_users()
        self.on_data_changed()

    def _reset_password(self) -> None:
        target = self._selected_user()
        if not target:
            return
        new_pw = simpledialog.askstring("Đặt lại mật khẩu", f"Mật khẩu mới cho '{target.username}':",
                                        show="*", parent=self)
        if new_pw is None:
            return
        try:
            self.ctx.users.admin_reset_password(self.user, target.username, new_pw)
        except AppError as exc:
            messagebox.showerror("Không thể đặt lại", str(exc), parent=self)
            return
        messagebox.showinfo("Thành công", "Đã đặt lại mật khẩu.", parent=self)

    def _delete_user(self) -> None:
        target = self._selected_user()
        if not target:
            return
        if not messagebox.askyesno("Xác nhận xóa", f"Xóa tài khoản '{target.username}'?", icon="warning", parent=self):
            return
        try:
            self.ctx.users.delete(self.user, target.username)
        except AppError as exc:
            messagebox.showerror("Không thể xóa", str(exc), parent=self)
            return
        self._users_changed()


    # Nhóm hỗ trợ
    def _build_groups(self, book) -> ttk.Frame:
        page = ttk.Frame(book, padding=config.PAD)
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 6))
        for text, cmd, style in (("Thêm", self._add_group, "Primary.TButton"), ("Sửa", self._edit_group, "TButton"),
                                 ("Xóa", self._delete_group, "Danger.TButton")):
            ttk.Button(bar, text=text, style=style, command=cmd).pack(side="left", padx=(0, 4))
        self.group_tree = self._tree(page, (("group_id", "Mã", 70), ("name", "Tên nhóm", 200),
                                            ("description", "Mô tả", 320), ("lead", "Trưởng nhóm", 130)))
        self.group_tree.bind("<Double-1>", lambda _e: self._edit_group())
        self.refresh_groups()
        return page

    def refresh_groups(self) -> None:
        self.group_tree.delete(*self.group_tree.get_children())
        for g in self.ctx.groups.list():
            self.group_tree.insert("", "end", iid=g.group_id, values=(g.group_id, g.name, g.description, g.lead))

    def _selected_group(self):
        sel = self.group_tree.selection()
        if not sel:
            messagebox.showinfo("Chưa chọn", "Vui lòng chọn một nhóm trong danh sách.", parent=self)
            return None
        return self.ctx.groups.find(sel[0])

    def _groups_changed(self) -> None:
        self.refresh_groups()
        self.on_data_changed()

    def _add_group(self) -> None:
        GroupDialog(self, self.ctx, self.user, None, self._groups_changed)

    def _edit_group(self) -> None:
        group = self._selected_group()
        if group:
            GroupDialog(self, self.ctx, self.user, group, self._groups_changed)

    def _delete_group(self) -> None:
        group = self._selected_group()
        if not group:
            return
        if not messagebox.askyesno("Xác nhận xóa", f"Xóa nhóm '{group.name}'?", icon="warning", parent=self):
            return
        try:
            self.ctx.groups.delete(self.user, group.group_id)
        except AppError as exc:
            messagebox.showerror("Không thể xóa", str(exc), parent=self)
            return
        self._groups_changed()

    # Dữ liệu
    def _build_data(self, book) -> ttk.Frame:
        page = ttk.Frame(book, padding=config.PAD * 2)
        page.columnconfigure(1, weight=1)
        rows = (
            ("Sao lưu dữ liệu", "Sao chép users/groups/tickets vào data/backup.", "Sao lưu ngay", self._backup),
            ("Khôi phục", "Khôi phục bản sao lưu gần nhất (bản hiện tại cũng được sao lưu trước).",
             "Khôi phục", self._restore),
            ("Dữ liệu mẫu", "Sinh ticket ngẫu nhiên bằng module random để thử nghiệm.", "Sinh dữ liệu mẫu", self._sample),
            ("Nhật ký hoạt động", "Xem các thao tác đăng nhập, tạo/sửa/xóa gần đây.", "Xem nhật ký", self._log),
        )
        for r, (title, desc, text, cmd) in enumerate(rows):
            ttk.Label(page, text=title, style="Heading.TLabel").grid(row=r * 2, column=0, sticky="w", pady=(8, 0))
            ttk.Label(page, text=desc, style="Muted.TLabel").grid(row=r * 2 + 1, column=0, sticky="w")
            ttk.Button(page, text=text, command=cmd).grid(row=r * 2, column=1, rowspan=2, sticky="e")
        return page

    def _backup(self) -> None:
        try:
            paths = self.ctx.backup_all()
        except AppError as exc:
            messagebox.showerror("Sao lưu thất bại", str(exc), parent=self)
            return
        messagebox.showinfo("Thành công", f"Đã sao lưu {len(paths)} file vào thư mục data/backup.", parent=self)

    def _restore(self) -> None:
        if not messagebox.askyesno("Xác nhận khôi phục", "Dữ liệu hiện tại sẽ được thay bằng bản sao lưu gần nhất.\n"
                                                         "Tiếp tục?", icon="warning", parent=self):
            return
        try:
            count = self.ctx.restore_all()
        except AppError as exc:
            messagebox.showerror("Khôi phục thất bại", str(exc), parent=self)
            return
        self.refresh_users()
        self.refresh_groups()
        self.on_data_changed()
        messagebox.showinfo("Thành công", f"Đã khôi phục {count} file dữ liệu.", parent=self)

    def _sample(self) -> None:
        raw = simpledialog.askstring("Dữ liệu mẫu", "Số ticket cần sinh (1-500):", initialvalue="30", parent=self)
        if raw is None:
            return
        try:
            count = int(raw)
            added = sample_data.generate(self.ctx.tickets, self.ctx.users, self.ctx.groups, count)
        except ValueError:
            messagebox.showerror("Dữ liệu không hợp lệ", "Vui lòng nhập số nguyên từ 1 đến 500.", parent=self)
            return
        except AppError as exc:
            messagebox.showerror("Không thể sinh dữ liệu", str(exc), parent=self)
            return
        self.refresh_users()
        self.on_data_changed()
        messagebox.showinfo("Thành công", f"Đã thêm {added} ticket mẫu.", parent=self)

    def _log(self) -> None:
        LogDialog(self, self.ctx)
