# StreamHub CI/CD Test Script
Write-Host "=============================="
Write-Host "  StreamHub CI/CD Test"
Write-Host "=============================="
Write-Host ""

# Step 1: Backend
Write-Host "Step 1: Backend dependencies installation" -ForegroundColor Yellow
Set-Location backend
pip install -r requirements.txt
Write-Host "Backend dependencies installed"
Write-Host ""

# Step 2: Frontend
Write-Host "Step 2: Frontend dependencies installation" -ForegroundColor Yellow
Set-Location ..
npm ci
Write-Host "Frontend dependencies installed"
Write-Host ""

# Step 3: TypeScript check
Write-Host "Step 3: TypeScript type checking" -ForegroundColor Yellow
npm run typecheck
Write-Host "TypeScript check completed"
Write-Host ""

# Step 4: Build
Write-Host "Step 4: Frontend build" -ForegroundColor Yellow
npm run build
Write-Host "Frontend build completed"
Write-Host ""

# Step 5: Check results
Write-Host "Step 5: Check build results" -ForegroundColor Yellow
if (Test-Path "dist") {
    Write-Host "[OK] dist directory created" -ForegroundColor Green
    Get-ChildItem "dist" | ForEach-Object { Write-Host "  - $($_.Name)" }
} else {
    Write-Host "[ERROR] dist directory not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=============================="
Write-Host "  Test completed!"
Write-Host "=============================="

Read-Host "Press Enter to exit"