# Trỏ 2 cron job sang pythonw.exe (không console) — ADR-0013.
# Chỉ đổi Action; lịch chạy, giới hạn 30 phút, IgnoreNew giữ nguyên.
# Chạy từ checkout CHÍNH (không phải worktree): powershell -File scripts\set_job_actions.ps1
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
# Worktree có DB riêng (có thể cũ) và bị xoá khi dọn → cron phải trỏ vào checkout chính
$gitDir = git -C $repo rev-parse --path-format=absolute --git-dir
$commonDir = git -C $repo rev-parse --path-format=absolute --git-common-dir
if ($gitDir -ne $commonDir) { throw "Run from the main checkout, not a worktree ($repo)." }
if (-not (Test-Path $pythonw)) { throw "Missing $pythonw - run 'uv sync' first." }  # PS 5.1 đọc file không BOM theo ANSI → thông báo để ASCII

$jobs = @{
    'ThreadsAI_SnapshotJob_4h'      = '-m src.pipeline.scheduled_job --log data\logs\scheduled_job.log'
    'ThreadsAI_NLPClusterJob_Daily' = '-m src.pipeline.nlp_cluster_job --log data\logs\nlp_cluster_job.log'
}
foreach ($name in $jobs.Keys) {
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument $jobs[$name] -WorkingDirectory $repo
    Set-ScheduledTask -TaskName $name -Action $action | Out-Null
    $a = (Get-ScheduledTask -TaskName $name).Actions[0]
    "{0}: {1} {2} [wd={3}]" -f $name, $a.Execute, $a.Arguments, $a.WorkingDirectory
}
