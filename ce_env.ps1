# Windows environment for the office PC (dot-sourced by make_videos.ps1 and start_form.ps1).
# Tools live next to the repo:  <parent>\ce_env (Python 3.12), <parent>\tools\ffmpeg-*\bin. n8n runs in Docker.
$CE_REPO = $PSScriptRoot
$CE_HOME = Split-Path $PSScriptRoot -Parent
$env:CE_REPO = $CE_REPO
$env:CE_PROFILE = "home"
$env:PYTHONUTF8 = "1"
if (-not $env:CE_PYTHON) { $env:CE_PYTHON = Join-Path $CE_HOME "ce_env\Scripts\python.exe" }
if (-not $env:FFMPEG_BIN) {
    $ff = Get-ChildItem (Join-Path $CE_HOME "tools") -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ff) { $env:FFMPEG_BIN = $ff.FullName }
}
if ($env:FFMPEG_BIN) { $env:PATH = (Split-Path $env:FFMPEG_BIN) + ";" + $env:PATH }   # ffprobe next to it
$CE_LOG = Join-Path $CE_REPO "workspace\last_run.log"
$CE_JOBS = Join-Path $CE_REPO "workspace\jobs"          # the form (n8n in Docker) drops one .json per request here
