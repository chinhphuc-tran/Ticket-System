"""Tiện ích dùng module `sys`: thông tin môi trường, tham số dòng lệnh, mã thoát."""
import platform
import sys
from typing import Dict, List, Optional

import config

EXIT_OK = 0
EXIT_BAD_ARGS = 1
EXIT_BAD_PYTHON = 2
EXIT_CANCELLED = 3

USAGE = f"""{config.APP_TITLE} v{config.APP_VERSION}

Cách dùng:  python main.py [tùy chọn]

Tùy chọn:
  -h, --help          Hiển thị trợ giúp này
  -v, --version       Hiển thị phiên bản
      --sample N      Sinh N ticket mẫu bằng module random (mặc định 40)
      --seed S        Hạt giống ngẫu nhiên để tái lập dữ liệu mẫu
      --no-gui        Chỉ xử lý dữ liệu (ví dụ --sample), không mở giao diện
      --reset-data    Sao lưu rồi xóa dữ liệu hiện tại để tạo lại từ đầu
      --yes           Không hỏi xác nhận (dùng cùng --reset-data)
      --data-dir DIR  Dùng thư mục dữ liệu khác
"""


def environment_summary() -> str:
    """Chuỗi mô tả môi trường chạy (hiển thị trong menu Trợ giúp)."""
    frozen = "Có (file .exe)" if getattr(sys, "frozen", False) else "Không (chạy từ mã nguồn)"
    return (
        f"Phiên bản ứng dụng : {config.APP_VERSION}\n"
        f"Python             : {sys.version.split()[0]} ({platform.python_implementation()})\n"
        f"Hệ điều hành       : {platform.system()} {platform.release()}\n"
        f"Nền tảng           : {sys.platform}\n"
        f"Đã đóng gói        : {frozen}\n"
        f"Thư mục dữ liệu    : {config.DATA_DIR}\n"
        f"Mã hóa mặc định    : {sys.getdefaultencoding()}"
    )


def check_python_version(minimum=config.MIN_PYTHON) -> None:
    """Thoát với mã EXIT_BAD_PYTHON nếu phiên bản Python quá cũ."""
    if sys.version_info < minimum:
        need = ".".join(map(str, minimum))
        print(f"Cần Python >= {need}, hiện tại là {sys.version.split()[0]}.", file=sys.stderr)
        sys.exit(EXIT_BAD_PYTHON)


def parse_args(argv: Optional[List[str]] = None) -> Dict:
    """Đọc tham số dòng lệnh từ `sys.argv` (không dùng thư viện ngoài)."""
    args = list(sys.argv[1:] if argv is None else argv)
    opts = {"help": False, "version": False, "sample": None, "seed": None,
            "no_gui": False, "reset": False, "yes": False, "data_dir": None}

    def _need_value(flag: str, index: int) -> str:
        if index + 1 >= len(args):
            raise ValueError(f"Tùy chọn {flag} cần một giá trị.")
        return args[index + 1]

    i = 0
    try:
        while i < len(args):
            a = args[i]
            if a in ("-h", "--help"):
                opts["help"] = True
            elif a in ("-v", "--version"):
                opts["version"] = True
            elif a == "--no-gui":
                opts["no_gui"] = True
            elif a == "--reset-data":
                opts["reset"] = True
            elif a == "--yes":
                opts["yes"] = True
            elif a == "--sample":
                # giá trị là tùy chọn: nếu thiếu thì dùng 40
                if i + 1 < len(args) and args[i + 1].isdigit():
                    opts["sample"] = int(args[i + 1])
                    i += 1
                else:
                    opts["sample"] = 40
            elif a == "--seed":
                opts["seed"] = int(_need_value(a, i))
                i += 1
            elif a == "--data-dir":
                opts["data_dir"] = _need_value(a, i)
                i += 1
            else:
                raise ValueError(f"Tùy chọn không hợp lệ: {a}")
            i += 1
    except ValueError as exc:
        print(f"Lỗi tham số: {exc}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(EXIT_BAD_ARGS)
    return opts
