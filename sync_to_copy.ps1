# Synchronize workspace from D:\news to D:\news - Copy
$srcDir = "D:\news"
$dstDir = "D:\news - Copy"

Write-Host "Syncing updated files from $srcDir to $dstDir..." -ForegroundColor Cyan

$files = @(
    "src\news\config.py",
    "src\news\agents\base.py",
    "src\news\agents\video_clip_agent\__init__.py",
    "src\news\agents\video_clip_agent\agent.py",
    "src\news\agents\video_assembler\agent.py",
    "src\news\agents\orchestrator\agent.py",
    "src\news\tools\hardware_encoder.py",
    "src\news\tools\news_fetcher.py",
    "src\news\tools\youtube_metadata.py",
    "src\news\tools\youtube_uploader.py",
    "src\news\tools\meta_uploader.py",
    "src\news\scheduler.py",
    "src\news\api\main.py",
    "src\news\static\index.html",
    "src\news\static\style.css",
    "src\news\static\app.js",
    "src\news\agents\image_agent\__init__.py",
    "src\news\agents\image_agent\agent.py",
    "src\news\agents\image_agent\ai_generator.py",
    "src\news\agents\image_agent\prompt_agent.py",
    "src\news\agents\image_agent\verifier.py",
    "src\news\agents\image_agent\thumbnail_generator.py",
    "src\news\agents\voice_agent\__init__.py",
    "src\news\agents\voice_agent\agent.py",
    "src\news\agents\voice_agent\tts_engine.py",
    "src\news\tools\maintenance.py",
    "src\news\agents\news_collector\__init__.py",
    "src\news\agents\news_collector\agent.py",
    "src\news\agents\news_collector\ranker.py",
    "src\news\agents\news_collector\rss_fetcher.py",
    "data\start_normalized.mp4",
    "data\end_normalized.mp4",
    "data\background_music.mp3",
    "data\sfx_transition.wav",
    "data\client_secret.json",
    "data\meta_credentials.template.json",
    "YOUTUBE_API_SETUP_GUIDE.md",
    "META_API_SETUP_GUIDE.md",
    "README.md",
    "run.bat",
    "run.ps1",
    "run_scheduler.bat",
    "run_scheduler.ps1"
)

foreach ($f in $files) {
    $src = Join-Path $srcDir $f
    $dst = Join-Path $dstDir $f
    if (Test-Path $src) {
        $parent = Split-Path -Parent $dst
        if (-not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  Synced: $f" -ForegroundColor Green
    }
}

Write-Host "Synchronization complete!" -ForegroundColor Cyan
