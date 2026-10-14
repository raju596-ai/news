# ==============================================================================
# Windows Task Scheduler Setup for Autonomous Daily YouTube Video Publishing
# ==============================================================================
# Registers 2 native daily tasks in Windows Task Scheduler:
#   1. NewsIntel_Morning_Edition (Runs every day at 08:30 AM)
#   2. NewsIntel_Evening_Edition (Runs every day at 05:00 PM)
#
# Features:
#   - Zero human interaction: Runs automatically even if no terminal is open.
#   - StartWhenAvailable: If computer was asleep/off at 8:30 AM, runs immediately on wake.
#   - Battery friendly: Configured to run whether plugged in or on battery.
# ==============================================================================

$RootPath = $PSScriptRoot
$RunBat = Join-Path $RootPath "run_scheduler.bat"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " NewsIntel - Production Windows Task Scheduler Installer" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "Project Directory: $RootPath" -ForegroundColor Gray
Write-Host "Runner Script:     $RunBat" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $RunBat)) {
    Write-Error "Could not find run_scheduler.bat at $RunBat"
    Exit 1
}

# Define task actions
$ActionMorning = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$RunBat`" --now --edition `"Morning Edition (08:30 AM)`"" `
    -WorkingDirectory $RootPath

$ActionEvening = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$RunBat`" --now --edition `"Evening Edition (05:00 PM)`"" `
    -WorkingDirectory $RootPath

# Define triggers
$TriggerMorning = New-ScheduledTaskTrigger -Daily -At "08:30AM"
$TriggerEvening = New-ScheduledTaskTrigger -Daily -At "05:00PM"

# Define production settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register Morning Task
try {
    Register-ScheduledTask `
        -TaskName "NewsIntel_Morning_Edition" `
        -Action $ActionMorning `
        -Trigger $TriggerMorning `
        -Settings $Settings `
        -Description "Autonomous AI News Video Generation & YouTube Upload (Morning 8:30 AM Edition)" `
        -Force | Out-Null
    Write-Host "[SUCCESS] Registered: NewsIntel_Morning_Edition (Daily at 08:30 AM)" -ForegroundColor Green
} catch {
    Write-Error "Failed to register Morning Task: $_"
}

# Register Evening Task
try {
    Register-ScheduledTask `
        -TaskName "NewsIntel_Evening_Edition" `
        -Action $ActionEvening `
        -Trigger $TriggerEvening `
        -Settings $Settings `
        -Description "Autonomous AI News Video Generation & YouTube Upload (Evening 5:00 PM Edition)" `
        -Force | Out-Null
    Write-Host "[SUCCESS] Registered: NewsIntel_Evening_Edition (Daily at 05:00 PM)" -ForegroundColor Green
} catch {
    Write-Error "Failed to register Evening Task: $_"
}

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " Zero-Human-Interaction Setup Complete!" -ForegroundColor Green
Write-Host " Windows will now automatically generate and upload videos daily at:" -ForegroundColor White
Write-Host "   - 08:30 AM (Morning Edition)" -ForegroundColor Yellow
Write-Host "   - 05:00 PM (Evening Edition)" -ForegroundColor Yellow
Write-Host " You can view these tasks in Windows by running: taskschd.msc" -ForegroundColor Gray
Write-Host "==============================================================================" -ForegroundColor Cyan
