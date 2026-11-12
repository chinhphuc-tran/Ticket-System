"""Chạy bộ kiểm thử và sinh bảng kiểm thử docs/BANG_KIEM_THU.md (đầu vào, mong đợi, thực tế, trạng thái)."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class Collector(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = {}

    def _doc(self, test):
        parts = [p.strip() for p in (test.shortDescription() or "").split("|")]
        return (parts + ["", "", ""])[:3]

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows[test.id()] = (*self._doc(test), "Đạt", "Đúng như mong đợi")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows[test.id()] = (*self._doc(test), "Không đạt", str(err[1]).splitlines()[0][:120])

    def addError(self, test, err):
        super().addError(test, err)
        self.rows[test.id()] = (*self._doc(test), "Lỗi", f"{err[0].__name__}: {err[1]}"[:120])


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    runner = unittest.TextTestRunner(resultclass=Collector, verbosity=1)
    result = runner.run(suite)
    lines = ["# Bảng kiểm thử", "",
             f"Sinh tự động bởi `run_tests.py` lúc {datetime.now().strftime('%d/%m/%Y %H:%M')}. "
             f"Tổng: {result.testsRun} ca, đạt: {result.testsRun - len(result.failures) - len(result.errors)}.", "",
             "| Mã | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Trạng thái |", "|---|---|---|---|---|"]
    for row in sorted(result.rows.values(), key=lambda r: r[0]):
        code, inp, exp, status, actual = row
        code = code.split(" ")[0] if code.startswith("TC") else code
        lines.append(f"| {code} | {inp} | {exp} | {actual} | {status} |")
    out = ROOT / "docs" / "BANG_KIEM_THU.md"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Đã ghi {out.relative_to(ROOT)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
