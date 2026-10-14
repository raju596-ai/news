# Remove the scheduled tasks
Unregister-ScheduledTask -TaskName "NewsIntel_Morning_Edition" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "NewsIntel_Evening_Edition" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed NewsIntel_Morning_Edition and NewsIntel_Evening_Edition scheduled tasks." -ForegroundColor Green
