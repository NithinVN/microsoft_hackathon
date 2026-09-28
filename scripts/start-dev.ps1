# Start IncidentMind Development Environment
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Starting IncidentMind Services (Dev Mode)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$backendPath = Join-Path $PSScriptRoot "..\backend"
$frontendPath = Join-Path $PSScriptRoot "..\frontend"

Write-Host "`n[1/2] Starting Backend FastAPI on http://localhost:8000..." -ForegroundColor Green
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"

Write-Host "`n[2/2] Starting Frontend Vite on http://localhost:5173..." -ForegroundColor Green
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"

Write-Host "`nAll processes initiated. Open http://localhost:5173 in your browser." -ForegroundColor Yellow
