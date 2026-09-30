#!/usr/bin/env bash
# Stop / Notification hook → pop-up góc màn hình Windows (toast).
# Chạy được từ Git Bash (Windows) lẫn từ WSL (gọi powershell.exe qua Windows interop).
# stdin (JSON của hook) được chuyển nguyên cho toast.ps1. Luôn exit 0: thông báo lỗi
# không được phép làm hỏng phiên làm việc.
event="${1:-stop}"
script="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/toast.ps1"
if command -v wslpath >/dev/null 2>&1; then
  script="$(wslpath -w "$script")"
fi
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$script" -Event "$event" >/dev/null 2>&1
exit 0
