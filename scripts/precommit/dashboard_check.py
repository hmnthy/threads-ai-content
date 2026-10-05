"""Pre-commit: kiểm dashboard Next.js khi có file `src/dashboard/**` thay đổi.

Chạy `npm run lint` + `npm run typecheck` trong `src/dashboard`. Bọc bằng Python để chạy được
cả Windows (npm là `npm.cmd` — CreateProcess không tự tìm, cần shell) lẫn Linux/WSL.

`typecheck` = `next typegen && tsc --noEmit`: kiểu toàn cục của Next (`LayoutProps`, `PageProps`…)
sinh vào `.next/types/` (gitignored) — checkout sạch/worktree mới chưa có thì `tsc` trần báo lỗi.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[2] / "src" / "dashboard"
STEPS = (["npm", "run", "lint", "--silent"], ["npm", "run", "typecheck", "--silent"])


def main() -> int:
    if not (DASHBOARD / "node_modules").exists():
        print("src/dashboard/node_modules chưa có — chạy `npm install` trong src/dashboard trước.")
        return 1
    for cmd in STEPS:
        result = subprocess.run(cmd, cwd=DASHBOARD, shell=os.name == "nt", check=False)
        if result.returncode != 0:
            print(f"✗ {' '.join(cmd)} (src/dashboard) thất bại")
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
