"""Thiết lập style ttk thống nhất về font, màu sắc, khoảng cách."""
import tkinter as tk
from tkinter import ttk

import config


def apply_style(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass        # theme không có sẵn: dùng theme mặc định của hệ điều hành

    bg, panel = config.COLOR_BG, config.COLOR_PANEL
    root.configure(background=bg)
    root.option_add("*Font", config.FONT_NORMAL)

    style.configure(".", font=config.FONT_NORMAL, background=bg, foreground=config.COLOR_TEXT)
    style.configure("TFrame", background=bg)
    style.configure("Card.TFrame", background=panel, relief="solid", borderwidth=1)
    style.configure("TLabel", background=bg)
    style.configure("Card.TLabel", background=panel)
    style.configure("Title.TLabel", font=config.FONT_TITLE, foreground=config.COLOR_PRIMARY)
    style.configure("Heading.TLabel", font=config.FONT_BOLD)
    style.configure("Muted.TLabel", foreground=config.COLOR_MUTED)
    style.configure("Error.TLabel", foreground=config.COLOR_DANGER)
    style.configure("KPI.TLabel", font=config.FONT_KPI, background=panel, foreground=config.COLOR_PRIMARY)
    style.configure("Status.TLabel", background="#e5e7eb", foreground=config.COLOR_TEXT)

    style.configure("TButton", padding=(10, 5))
    style.configure("Primary.TButton", background=config.COLOR_PRIMARY, foreground="white")
    style.map("Primary.TButton",
              background=[("disabled", "#9ca3af"), ("active", config.COLOR_PRIMARY_DARK)],
              foreground=[("disabled", "#f3f4f6")])
    style.configure("Danger.TButton", background=config.COLOR_DANGER, foreground="white")
    style.map("Danger.TButton",
              background=[("disabled", "#9ca3af"), ("active", "#b91c1c")],
              foreground=[("disabled", "#f3f4f6")])

    style.configure("TLabelframe", background=bg)
    style.configure("TLabelframe.Label", background=bg, font=config.FONT_BOLD)
    style.configure("TCheckbutton", background=bg)
    style.configure("TRadiobutton", background=bg)
    style.configure("Card.TCheckbutton", background=panel)
    style.configure("TNotebook", background=bg)
    style.configure("TNotebook.Tab", padding=(14, 6), font=config.FONT_NORMAL)

    style.configure("Treeview", rowheight=26, background="white", fieldbackground="white")
    style.configure("Treeview.Heading", font=config.FONT_BOLD, padding=4)
    style.map("Treeview", background=[("selected", config.COLOR_PRIMARY)],
              foreground=[("selected", "white")])
    return style
