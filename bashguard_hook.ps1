<#
.SYNOPSIS
    BashGuard PowerShell Hook - Intercepts dangerous commands in real-time
.USAGE
    1. Start server:   python server.py
    2. Load hook:      . .\bashguard_hook.ps1
    3. Type commands - BashGuard watches everything
    4. To disable:     bashguard-off
#>

$Global:BashGuardEnabled = $true
$Global:BashGuardServerUrl = "http://localhost:8000"

$Global:BashGuardBlockList = @(
    "rm -rf /", "rm -rf /*", "rm -rf ~",
    "del /f /s /q C:\", "format c:", "format d:",
    ":(){:|:&};:", "> /dev/sda", "dd if=/dev/zero",
    "mkfs.ext4 /dev/sda", "shutdown", "reboot", "halt",
    "Remove-Item -Recurse -Force C:\", "Stop-Computer", "Restart-Computer"
)

$Global:BashGuardDangerousKeywords = @(
    "rm ", "del ", "rmdir", "remove-item",
    "format ", "fdisk", "drop ", "delete from", "truncate",
    "git push -f", "git push --force",
    "kill", "stop-process", "taskkill",
    "chmod", "icacls", "takeown",
    "curl | bash", "wget | sh",
    "reg delete"
)

$Global:BashGuardSafeCommands = @(
    "ls", "dir", "get-childitem", "echo", "write-host", "write-output",
    "cat", "type", "get-content", "pwd", "get-location", "cd", "set-location",
    "cls", "clear", "help", "get-help", "man", "history", "get-history",
    "whoami", "hostname", "date", "get-date", "git status", "git log",
    "git branch", "git diff", "python --version", "node --version",
    "pip list", "npm list", "code", "notepad", "bashguard"
)

function Test-IsSafeCommand {
    param([string]$Command)
    $cmdLower = $Command.Trim().ToLower()
    foreach ($safe in $Global:BashGuardSafeCommands) {
        if ($cmdLower.StartsWith($safe)) { return $true }
    }
    return $false
}

function Test-IsHardBlocked {
    param([string]$Command)
    $cmdLower = $Command.Trim().ToLower()
    foreach ($blocked in $Global:BashGuardBlockList) {
        if ($cmdLower.Contains($blocked.ToLower())) { return $true }
    }
    return $false
}

function Test-HasDangerousKeyword {
    param([string]$Command)
    $cmdLower = $Command.Trim().ToLower()
    foreach ($keyword in $Global:BashGuardDangerousKeywords) {
        if ($cmdLower.Contains($keyword.ToLower())) { return $true }
    }
    return $false
}

function Invoke-BashGuardSimulation {
    param([string]$Command)
    try {
        $body = @{ command = $Command } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$Global:BashGuardServerUrl/simulate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
        return $response
    } catch {
        return $null
    }
}

function Show-BashGuardWarning {
    param($Sim)
    $color = switch ($Sim.risk_level) { "CRITICAL" {"Red"} "HIGH" {"Red"} "MEDIUM" {"Yellow"} default {"White"} }
    
    Write-Host ""
    Write-Host "  ========== BASHGUARD - COMMAND INTERCEPTED ==========" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Command: $($Sim.planned_command)" -ForegroundColor White
    Write-Host "  Risk:    $($Sim.risk_level) ($($Sim.risk_score)/100)" -ForegroundColor $color
    $undoText = if ($Sim.is_reversible) { "Possible" } else { "IMPOSSIBLE" }
    $undoColor = if ($Sim.is_reversible) { "Green" } else { "Red" }
    Write-Host "  Undo:    $undoText" -ForegroundColor $undoColor
    Write-Host ""
    if ($Sim.risk_reasons) {
        Write-Host "  Why this is risky:" -ForegroundColor Yellow
        $i = 1
        foreach ($reason in $Sim.risk_reasons) {
            Write-Host "    $i. $reason" -ForegroundColor Yellow
            $i++
        }
        Write-Host ""
    }
    if ($Sim.warnings) {
        foreach ($w in $Sim.warnings) {
            Write-Host "  WARNING: $w" -ForegroundColor Red
        }
        Write-Host ""
    }
    if ($Sim.safer_command) {
        Write-Host "  Safer alternative: $($Sim.safer_command)" -ForegroundColor Green
        Write-Host ""
    }
    Write-Host "  =====================================================" -ForegroundColor Cyan
}

# THE HOOK - intercepts Enter key
Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    $command = $line.Trim()

    if ([string]::IsNullOrWhiteSpace($command)) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }

    if (-not $Global:BashGuardEnabled) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }

    # Safe command - let through
    if (Test-IsSafeCommand $command) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }

    # Hard blocked - STOP immediately
    if (Test-IsHardBlocked $command) {
        Write-Host ""
        Write-Host ""
        Write-Host "  ========== BASHGUARD - BLOCKED ==========" -ForegroundColor Red
        Write-Host "  This command is PERMANENTLY BLOCKED." -ForegroundColor Red
        Write-Host "  Command: $command" -ForegroundColor White
        Write-Host "  ==========================================" -ForegroundColor Red
        Write-Host ""
        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
        [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
        return
    }

    # Dangerous keyword - full simulation
    if (Test-HasDangerousKeyword $command) {
        Write-Host ""
        Write-Host ""
        Write-Host "  [BashGuard] Dangerous command detected. Simulating..." -ForegroundColor Cyan

        $sim = Invoke-BashGuardSimulation $command

        if ($null -eq $sim) {
            Write-Host "  [BashGuard] Server offline. Allow command? (y/n): " -ForegroundColor Yellow -NoNewline
            $choice = Read-Host
            if ($choice -eq "y") {
                [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                [Microsoft.PowerShell.PSConsoleReadLine]::Insert($command)
                [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
            } else {
                [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
            }
            return
        }

        if ($sim.risk_level -in @("CRITICAL", "HIGH", "MEDIUM")) {
            Show-BashGuardWarning $sim

            if ($sim.safer_command) {
                Write-Host "  [A]pprove  [S]afer  [C]ancel: " -ForegroundColor White -NoNewline
            } else {
                Write-Host "  [A]pprove  [C]ancel: " -ForegroundColor White -NoNewline
            }
            $choice = Read-Host

            switch ($choice.ToLower()) {
                { $_ -in "a", "approve", "y", "yes" } {
                    Write-Host "  [BashGuard] Approved." -ForegroundColor Green
                    [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                    [Microsoft.PowerShell.PSConsoleReadLine]::Insert($command)
                    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
                }
                { $_ -in "s", "safer", "safe" } {
                    if ($sim.safer_command) {
                        Write-Host "  [BashGuard] Using safer command." -ForegroundColor Green
                        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                        [Microsoft.PowerShell.PSConsoleReadLine]::Insert($sim.safer_command)
                        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
                    } else {
                        Write-Host "  [BashGuard] No safer option. Cancelled." -ForegroundColor Yellow
                        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                        [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
                    }
                }
                default {
                    Write-Host "  [BashGuard] CANCELLED." -ForegroundColor Red
                    [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                    [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
                }
            }
            return
        }

        Write-Host ""
        Write-Host "  [BashGuard] LOW risk. Proceeding." -ForegroundColor Green
    }

    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
}

function bashguard-off { $Global:BashGuardEnabled = $false; Write-Host "  [BashGuard] DISABLED." -ForegroundColor Yellow }
function bashguard-on { $Global:BashGuardEnabled = $true; Write-Host "  [BashGuard] ENABLED." -ForegroundColor Green }
function bashguard-status {
    $s = if ($Global:BashGuardEnabled) { "ACTIVE" } else { "DISABLED" }
    $c = if ($Global:BashGuardEnabled) { "Green" } else { "Red" }
    Write-Host "  BashGuard: $s" -ForegroundColor $c
    try { Invoke-RestMethod -Uri "$Global:BashGuardServerUrl/" -TimeoutSec 3 | Out-Null; Write-Host "  Server: RUNNING" -ForegroundColor Green } catch { Write-Host "  Server: OFFLINE" -ForegroundColor Red }
}

Write-Host ""
Write-Host "  ========== BashGuard - Terminal Protection ==========" -ForegroundColor Cyan
Write-Host "  Status: ACTIVE" -ForegroundColor Green
Write-Host "  Every command is checked before execution." -ForegroundColor White
Write-Host "  Type 'bashguard-off' to disable." -ForegroundColor Gray
Write-Host "  =====================================================" -ForegroundColor Cyan
Write-Host ""
