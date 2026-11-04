# Daily HOI content on the office PC. Windows Task Scheduler runs this once a day.
#   powershell -ExecutionPolicy Bypass -File daily_content\run_daily.ps1
# Output: $env:HOI_OUTPUT_DIR (default: Documents\HOI Daily Content)\<yyyy-MM-dd>\
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
. (Join-Path $repo "ce_env.ps1")                       # sets CE_PYTHON and PYTHONUTF8

$out = if ($env:HOI_OUTPUT_DIR) { $env:HOI_OUTPUT_DIR } else { Join-Path ([Environment]::GetFolderPath("MyDocuments")) "HOI Daily Content" }
$date = Get-Date -Format "yyyy-MM-dd"
New-Item -ItemType Directory -Force -Path (Join-Path $out "logs") | Out-Null
$log = Join-Path $out "logs\$date.log"

git pull -q origin main-rpcp44 2>&1 | Out-File -Append $log

$prompt = @"
Daily HOI content run for $date, LOCAL mode. Read daily_content/DAILY_RUN.md in full and follow it exactly.
Output folder: "$out\$date". Python: "$env:CE_PYTHON" (use it for daily_content/fetch_feed.py).
Example carousel JSON: daily_content/example_day.json.
"@

claude -p $prompt `
  --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" "WebSearch" "WebFetch" `
  --permission-mode acceptEdits 2>&1 | Out-File -Append -Encoding utf8 $log
