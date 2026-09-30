# Pop-up (toast) góc màn hình Windows cho hook Stop/Notification và cho cron job lỗi.
# Phải chạy bằng Windows PowerShell 5.1 (powershell.exe) — pwsh 7 không có WinRT projection.
# Đọc JSON của hook từ stdin (nếu có); -Title/-Message cho phép gọi trực tiếp (VD từ cron).
# Lỗi WinRT → fallback MessageBox (ví dụ chính thức trong docs hooks của Claude Code).
param(
    [string]$Event = "stop",
    [string]$Title = "",
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

if (-not $Message -and [Console]::IsInputRedirected) {
    try {
        $raw = [Console]::In.ReadToEnd()
        if ($raw) {
            $payload = $raw | ConvertFrom-Json
            if ($payload.last_assistant_message) { $Message = [string]$payload.last_assistant_message }
            elseif ($payload.message) { $Message = [string]$payload.message }
        }
    } catch { }
}

if (-not $Title) {
    switch ($Event) {
        "stop"         { $Title = "Claude: done" }
        "notification" { $Title = "Claude: needs your input" }
        default        { $Title = "Claude: $Event" }
    }
}
if (-not $Message) { $Message = "threads-ai-content" }
$Message = ($Message -replace "\s+", " ").Trim()
if ($Message.Length -gt 120) { $Message = $Message.Substring(0, 117) + "..." }

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $t = [System.Security.SecurityElement]::Escape($Title)
    $m = [System.Security.SecurityElement]::Escape($Message)
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$m</text></binding></visual></toast>")
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($Message, $Title) | Out-Null
}
