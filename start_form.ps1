# Start the editors' form on the office PC (Windows version of /workspace/start.sh).
# Double-click "Start Content Engine.bat", or run:  powershell -ExecutionPolicy Bypass -File start_form.ps1
# n8n runs in Docker (container ce-n8n) and only queues requests as files in workspace\jobs;
# this window runs them one at a time on the PC's GPU. Keep it open while videos are being made.
. "$PSScriptRoot\ce_env.ps1"
$image = "docker.n8n.io/n8nio/n8n:1.97.1"
New-Item -ItemType Directory -Force $CE_JOBS | Out-Null
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker is not running. Start Docker Desktop, then try again."; exit 1 }

$port = 5680                                 # 5678 is taken by another n8n on this PC
$ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1).IPv4Address.IPAddress
docker rm -f ce-n8n *> $null
docker run -d --name ce-n8n --restart unless-stopped -p "${port}:5678" `
    -v ce_n8n_data:/home/node/.n8n -v "${CE_JOBS}:/jobs" `
    -e CE_JOBS_DIR=/jobs -e NODE_FUNCTION_ALLOW_BUILTIN=fs -e NODES_EXCLUDE="[]" -e N8N_RUNNERS_ENABLED=false `
    -e N8N_SECURE_COOKIE=false -e GENERIC_TIMEZONE=Asia/Kolkata -e "WEBHOOK_URL=http://${ip}:${port}/" `
    $image | Out-Null
docker cp "$CE_REPO\n8n_blueprint.json" ce-n8n:/tmp/blueprint.json | Out-Null
docker exec ce-n8n n8n import:workflow --input=/tmp/blueprint.json *> $null
docker exec ce-n8n n8n update:workflow --id=ceReelsForm00001 --active=true *> $null
docker restart ce-n8n | Out-Null            # activation takes effect on restart

Write-Host ""
Write-Host "=================================================================="
Write-Host "  EDITORS' FORM (this PC):        http://localhost:${port}/form/oxygen-forest-reels"
Write-Host "  EDITORS' FORM (office network): http://${ip}:${port}/form/oxygen-forest-reels"
Write-Host "  Videos land in the Drive OUTPUT folder. Progress log: $CE_LOG"
Write-Host "  Keep this window open while videos are being made."
Write-Host "=================================================================="
Write-Host "Waiting for form requests..."
while ($true) {
    $job = Get-ChildItem $CE_JOBS -Filter *.json | Sort-Object Name | Select-Object -First 1
    if ($job) {
        $j = Get-Content $job.FullName -Raw | ConvertFrom-Json
        Move-Item $job.FullName "$($job.FullName).taken" -Force
        Write-Host "[$(Get-Date -Format 'HH:mm')] making $($j.n) videos ($($j.langs), $($j.style), new clips: $($j.analyse))"
        & "$CE_REPO\make_videos.ps1" -N $j.n -Langs $j.langs -Style $j.style -Analyse $j.analyse
        Write-Host "[$(Get-Date -Format 'HH:mm')] done. Waiting for form requests..."
    }
    Start-Sleep -Seconds 5
}
