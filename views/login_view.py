"""Màn hình đăng nhập và tạo tài khoản."""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import config
from models.user import User
from services.context import AppContext
from utils import validators as v
from utils.exceptions import AppError, AuthError
from views.widgets import LabeledEntry


class LoginView(ttk.Frame):
    """Vùng chứa chính chỉ dùng place(); thẻ (card) bên trong dùng pack(); từng tab dùng grid()."""

    def __init__(self, master, ctx: AppContext, on_login: Callable[[User], None]):
        super().__init__(master)
        self.ctx, self.on_login = ctx, on_login

        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.place(relx=0.5, rely=0.45, anchor="center")
        inner_bg = ttk.Frame(card, style="Card.TFrame")
        inner_bg.pack()
        ttk.Label(inner_bg, text="Quản lý sự cố CNTT", style="Title.TLabel", background=config.COLOR_PANEL
                  ).pack(pady=(0, 4))
        ttk.Label(inner_bg, text="Đăng nhập để tiếp tục", style="Muted.TLabel", background=config.COLOR_PANEL
                  ).pack(pady=(0, 12))

        self.notebook = ttk.Notebook(inner_bg)
        self.notebook.pack(fill="both", expand=True)
        self._build_login_tab()
        self._build_register_tab()
        ttk.Label(inner_bg, text="Tài khoản demo: xem file README.md", style="Muted.TLabel",
                  background=config.COLOR_PANEL).pack(pady=(12, 0))

    # ------------------------------------------------------------------
    def _build_login_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Đăng nhập")
        self.username = LabeledEntry(tab, "Tên đăng nhập")
        self.password = LabeledEntry(tab, "Mật khẩu", show="*")
        self.username.grid(row=0, column=0, sticky="ew")
        self.password.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.message = ttk.Label(tab, text="", style="Error.TLabel", wraplength=300, justify="left")
        self.message.grid(row=2, column=0, sticky="w", pady=(4, 4))
        ttk.Button(tab, text="Đăng nhập", style="Primary.TButton", command=self._login).grid(
            row=3, column=0, sticky="ew")
        for entry in (self.username.entry, self.password.entry):
            entry.bind("<Return>", lambda _e: self._login())
        self.username.focus()

    def _build_register_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Tạo tài khoản")
        self.reg_username = LabeledEntry(tab, "Tên đăng nhập (4-20 ký tự)", validator=v.validate_username)
        self.reg_name = LabeledEntry(tab, "Họ và tên", validator=lambda s: v.validate_text(s, "Họ tên", 2, 60))
        self.reg_email = LabeledEntry(tab, "Email", validator=v.validate_email)
        self.reg_phone = LabeledEntry(tab, "Số điện thoại (không bắt buộc)",
                                      validator=lambda s: v.validate_phone(s, required=False))
        self.reg_password = LabeledEntry(tab, "Mật khẩu (>= 6 ký tự, có chữ và số)",
                                         validator=v.validate_password, show="*")
        self.reg_confirm = LabeledEntry(tab, "Nhập lại mật khẩu", show="*")
        fields = (self.reg_username, self.reg_name, self.reg_email, self.reg_phone,
                  self.reg_password, self.reg_confirm)
        for row, widget in enumerate(fields):
            widget.grid(row=row, column=0, sticky="ew")
        ttk.Button(tab, text="Tạo tài khoản", style="Primary.TButton", command=self._register).grid(
            row=len(fields), column=0, sticky="ew", pady=(8, 0))

    # ------------------------------------------------------------------
    def _login(self) -> None:
        try:
            user = self.ctx.auth.login(self.username.get(), self.password.get())
        except AuthError as exc:
            self.message.configure(text=str(exc))
            self.password.clear()
            self.password.focus()
            return
        self.on_login(user)        # chuyển sang màn hình chính (view này sẽ bị hủy)

    def _register(self) -> None:
        try:
            self.ctx.auth.register(self.reg_username.get(), self.reg_name.get(), self.reg_email.get(),
                                   self.reg_phone.get(), self.reg_password.get(), self.reg_confirm.get())
        except AppError as exc:
            messagebox.showerror("Không thể tạo tài khoản", str(exc), parent=self)
            return
        messagebox.showinfo("Thành công", "Đã tạo tài khoản. Bạn có thể đăng nhập ngay.", parent=self)
        self.username.set(self.reg_username.get())
        for widget in (self.reg_username, self.reg_name, self.reg_email, self.reg_phone,
                       self.reg_password, self.reg_confirm):
            widget.clear()
        self.notebook.select(0)
        self.password.focus()
