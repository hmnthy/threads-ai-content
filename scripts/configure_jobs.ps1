# Đặt cấu hình 2 cron job trên Task Scheduler (task phải đã tồn tại) — chạy lại bao nhiêu lần cũng ra cùng kết quả.
# - Action: gọi thẳng pythonw.exe, không console (ADR-0013).
# - Job NLP 12:30 hằng ngày theo GIỜ MÁY (StartBoundary không offset → theo đổi giờ mùa đông/hè) +
#   chạy cả khi dùng pin (ADR-0017): máy dùng Modern Standby (S0) đóng băng tiến trình khi ngủ.
# - Đặt tường minh: giới hạn 30 phút, IgnoreNew (không chạy chồng chính nó), StartWhenAvailable (chạy bù).
# - Không đổi lịch 4h của snapshot (StartBoundary cũ có offset — vô hại với lưới 4h).
# Chạy từ checkout CHÍNH (không phải worktree): powershell -File scripts\configure_jobs.ps1
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
# Worktree có DB riêng (có thể cũ) và bị xoá khi dọn → cron phải trỏ vào checkout chính
$gitDir = git -C $repo rev-parse --path-format=absolute --git-dir
$commonDir = git -C $repo rev-parse --path-format=absolute --git-common-dir
if (-not $gitDir) { throw "git not found or $repo is not a git checkout." }
if ($gitDir -ne $commonDir) { throw "Run from the main checkout, not a worktree ($repo)." }
if (-not (Test-Path $pythonw)) { throw "Missing $pythonw - run 'uv sync' first." }  # PS 5.1 đọc file không BOM theo ANSI → thông báo để ASCII

$jobs = @{
    'ThreadsAI_SnapshotJob_4h'      = '-m src.pipeline.scheduled_job --log data\logs\scheduled_job.log'
    'ThreadsAI_NLPClusterJob_Daily' = '-m src.pipeline.nlp_cluster_job --log data\logs\nlp_cluster_job.log'
}
$nlpDailyAt = '12:30'  # giờ máy thường đang mở (Thy chọn 2026-10-04, ADR-0017)

foreach ($name in $jobs.Keys) {
    $task = Get-ScheduledTask -TaskName $name
    $settings = $task.Settings
    # Job ngắn (snapshot ~2 phút, NLP ~1 phút): pin không phải lý do bỏ lượt — snapshot bỏ lượt là mất hẳn
    $settings.DisallowStartIfOnBatteries = $false
    $settings.StopIfGoingOnBatteries = $false
    $settings.ExecutionTimeLimit = 'PT30M'
    $settings.MultipleInstances = 'IgnoreNew'
    $settings.StartWhenAvailable = $true
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument $jobs[$name] -WorkingDirectory $repo
    if ($name -eq 'ThreadsAI_NLPClusterJob_Daily') {
        $trigger = New-ScheduledTaskTrigger -Daily -At $nlpDailyAt
        # PS 5.1 ghi StartBoundary kèm offset (+02:00) = "đồng bộ theo múi giờ" → sau đổi giờ sẽ lệch 1h
        $trigger.StartBoundary = ([datetime]$nlpDailyAt).ToString('s')
        Set-ScheduledTask -TaskName $name -Action $action -Settings $settings -Trigger $trigger | Out-Null
    } else {
        Set-ScheduledTask -TaskName $name -Action $action -Settings $settings | Out-Null
    }
    $t = Get-ScheduledTask -TaskName $name
    $a = $t.Actions[0]
    "{0}: {1} {2} [wd={3}]" -f $name, $a.Execute, $a.Arguments, $a.WorkingDirectory
    $every = $t.Triggers[0].Repetition.Interval
    if (-not $every) { $every = 'daily' }
    $batteryOk = -not $t.Settings.DisallowStartIfOnBatteries -and -not $t.Settings.StopIfGoingOnBatteries
    "  start={0} every={1} battery-ok={2} limit={3} instances={4} start-when-available={5}" -f `
        $t.Triggers[0].StartBoundary, $every, $batteryOk, $t.Settings.ExecutionTimeLimit, `
        $t.Settings.MultipleInstances, $t.Settings.StartWhenAvailable
}
