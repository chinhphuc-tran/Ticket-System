"""Điểm khởi động của ứng dụng: python main.py [tùy chọn]  (xem --help)."""
import sys

import config
from utils import sys_info


def _reset_data(ctx_dir, assume_yes: bool) -> None:
    """Sao lưu rồi xóa dữ liệu hiện tại để ứng dụng tạo lại từ đầu."""
    from services.context import AppContext
    if not assume_yes:
        answer = input("Thao tác này sẽ xóa dữ liệu hiện tại (có sao lưu trước). Tiếp tục? [y/N]: ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Đã hủy.")
            sys.exit(sys_info.EXIT_CANCELLED)
    ctx = AppContext(ctx_dir)
    ctx.backup_all()
    for store in ctx.stores + [ctx.api_store]:
        try:
            store.path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"Không xóa được {store.path.name}: {exc}", file=sys.stderr)
            sys.exit(sys_info.EXIT_BAD_ARGS)
    print("Đã đặt lại dữ liệu. Tài khoản và nhóm mặc định sẽ được tạo lại khi chạy.")


def main() -> int:
    sys_info.check_python_version()
    opts = sys_info.parse_args()

    if opts["help"]:
        print(sys_info.USAGE)
        return sys_info.EXIT_OK
    if opts["version"]:
        print(f"{config.APP_TITLE} v{config.APP_VERSION}")
        return sys_info.EXIT_OK

    from pathlib import Path
    data_dir = Path(opts["data_dir"]) if opts["data_dir"] else None

    if opts["reset"]:
        _reset_data(data_dir, opts["yes"])

    from services.context import AppContext
    ctx = AppContext(data_dir)

    if opts["sample"] is not None:
        from services import sample_data
        added = sample_data.generate(ctx.tickets, ctx.users, ctx.groups, opts["sample"], opts["seed"])
        print(f"Đã sinh {added} ticket mẫu (seed={opts['seed']}).")

    if opts["no_gui"]:
        return sys_info.EXIT_OK

    try:
        from views.app import TicketApp
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("tkinter"):
            print("Python của bạn chưa có Tkinter. Hãy cài lại Python kèm tcl/tk.", file=sys.stderr)
            return sys_info.EXIT_BAD_PYTHON
        raise
    TicketApp(ctx).run()
    return sys_info.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
