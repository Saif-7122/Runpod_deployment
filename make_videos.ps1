# Windows version of make_videos.sh (run by start_form.ps1 for each form request; editors never type this).
#   .\make_videos.ps1 -N <how_many> -Langs <"en te" | en | te | hi ...> [-Style weekend_home] [-Analyse yes|no]
param([int]$N = 10, [string]$Langs = "en te", [string]$Style = "weekend_home", [string]$Analyse = "no")
. "$PSScriptRoot\ce_env.ps1"
Set-Location $CE_REPO
$env:PYTHONUNBUFFERED = "1"
New-Item -ItemType Directory -Force (Split-Path $CE_LOG) | Out-Null
function Say($m) { $l = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $m"; Write-Host $l; Add-Content $CE_LOG $l -Encoding UTF8 }
# the pipeline logs to stderr; turn every line into plain text so PowerShell 5.1 does not treat it as an error
function Py { & $env:CE_PYTHON @args 2>&1 | ForEach-Object { "$_" } | Add-Content $CE_LOG -Encoding UTF8 }
Set-Content $CE_LOG "" -Encoding UTF8
Say "start: $N videos, languages: $Langs, style: $Style, analyse: $Analyse"
if ($Analyse -eq "yes") { Py analyze.py --drive }    # only new clips are analysed; old ones are cached
Py run.py --brief brief.json --style $Style --variants $N --languages ($Langs -split " ") --upload --cleanup
Say "finished - videos and captions are in the Drive OUTPUT folder"
