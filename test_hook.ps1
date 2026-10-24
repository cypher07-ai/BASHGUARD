Set-Location "C:\Users\ayan kaushik\.gemini\antigravity\scratch\ai-agent-hackathon"

$Global:BashGuardEnabled = $true
$Global:BashGuardServerUrl = "http://localhost:8000"
$Global:BashGuardBlockList = @("rm -rf /", "rm -rf /*", "del /f /s /q C:\", "format c:", "shutdown", "reboot")
$Global:BashGuardDangerousKeywords = @("rm ", "del ", "rmdir", "remove-item", "drop ", "delete from", "git push -f", "git push --force", "kill", "chmod", "format ")
$Global:BashGuardSafeCommands = @("ls", "dir", "get-childitem", "echo", "write-host", "cat", "type", "pwd", "cd", "cls", "clear", "help", "whoami", "git status", "git log")

function Test-IsSafeCommand { param([string]$Command); $c = $Command.Trim().ToLower(); foreach ($s in $Global:BashGuardSafeCommands) { if ($c.StartsWith($s)) { return $true } }; return $false }
function Test-IsHardBlocked { param([string]$Command); $c = $Command.Trim().ToLower(); foreach ($b in $Global:BashGuardBlockList) { if ($c.Contains($b.ToLower())) { return $true } }; return $false }
function Test-HasDangerousKeyword { param([string]$Command); $c = $Command.Trim().ToLower(); foreach ($k in $Global:BashGuardDangerousKeywords) { if ($c.Contains($k.ToLower())) { return $true } }; return $false }

Write-Host ""
Write-Host "  BashGuard Hook - Test Results" -ForegroundColor Cyan
Write-Host "  -------------------------------------------" -ForegroundColor Cyan

Write-Host "  TEST 1: dir -> Safe:" (Test-IsSafeCommand "dir") -ForegroundColor Green
Write-Host "  TEST 2: git status -> Safe:" (Test-IsSafeCommand "git status") -ForegroundColor Green
Write-Host "  TEST 3: rm -rf / -> Blocked:" (Test-IsHardBlocked "rm -rf /") -ForegroundColor Red
Write-Host "  TEST 4: format c: -> Blocked:" (Test-IsHardBlocked "format c:") -ForegroundColor Red
Write-Host "  TEST 5: del /s /q -> Dangerous:" (Test-HasDangerousKeyword "del /s /q files") -ForegroundColor Yellow
Write-Host "  TEST 6: git push --force -> Dangerous:" (Test-HasDangerousKeyword "git push --force origin main") -ForegroundColor Yellow
Write-Host "  TEST 7: echo hello -> Safe:" (Test-IsSafeCommand "echo hello") -ForegroundColor Green

Write-Host ""
Write-Host "  TEST 8: Full API Simulation" -ForegroundColor Cyan
try {
    $body = @{ command = "delete all python files" } | ConvertTo-Json
    $sim = Invoke-RestMethod -Uri "http://localhost:8000/simulate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
    Write-Host "  Command:    $($sim.planned_command)" -ForegroundColor White
    Write-Host "  Risk Level: $($sim.risk_level)" -ForegroundColor Red
    Write-Host "  Risk Score: $($sim.risk_score)/100" -ForegroundColor Red
    if ($sim.safer_command) { Write-Host "  Safer:      $($sim.safer_command)" -ForegroundColor Green }
} catch {
    Write-Host "  Server not reachable" -ForegroundColor Red
}

Write-Host ""
Write-Host "  All 8 tests complete!" -ForegroundColor Green
Write-Host ""
