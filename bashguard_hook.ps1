<#
.SYNOPSIS
    BashGuard PowerShell Hook — Intercepts dangerous commands IN REAL-TIME
    
.DESCRIPTION
    This script hooks into PowerShell's Enter key. Every time you press Enter,
    BashGuard checks the command BEFORE it runs. If it's dangerous, it blocks
    it and shows a warning. If it's safe, it runs normally.

.USAGE
    1. Start the BashGuard server:  python server.py
    2. In another PowerShell:       . .\bashguard_hook.ps1
    3. Now type any command — BashGuard is watching.
    
    To uninstall: bashguard-off
#>

# ============================================================
#  CONFIG
# ============================================================
$Global:BashGuardEnabled = $true
$Global:BashGuardServerUrl = "http://localhost:8000"

# Commands that are ALWAYS blocked locally (no API needed)
$Global:BashGuardBlockList = @(
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "del /f /s /q C:\",
    "format c:",
    "format d:",
    ":(){:|:&};:",
    "> /dev/sda",
    "dd if=/dev/zero",
    "mkfs.ext4 /dev/sda",
    "shutdown",
    "reboot",
    "halt",
    "Remove-Item -Recurse -Force C:\",
    "Remove-Item -Recurse -Force /",
    "Stop-Computer",
    "Restart-Computer"
)

# Keywords that trigger a FULL simulation
$Global:BashGuardDangerousKeywords = @(
    "rm ", "del ", "rmdir", "remove-item",
    "format ", "fdisk",
    "drop ", "delete from", "truncate",
    "git push -f", "git push --force",
    "kill", "stop-process", "taskkill",
    "chmod", "icacls", "takeown",
    "curl | bash", "wget | sh",
    "disable-", "set-executionpolicy",
    "reg delete", "regedit"
)

# Safe command prefixes that NEVER need checking
$Global:BashGuardSafeCommands = @(
    "ls", "dir", "get-childitem", "echo", "write-host", "write-output",
    "cat", "type", "get-content", "pwd", "get-location", "cd", "set-location",
    "cls", "clear", "help", "get-help", "man", "history", "get-history",
    "whoami", "hostname", "date", "get-date", "git status", "git log",
    "git branch", "git diff", "python --version", "node --version",
    "pip list", "npm list", "code", "notepad"
)

# ============================================================
#  CORE FUNCTIONS
# ============================================================

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
        $response = Invoke-RestMethod -Uri "$Global:BashGuardServerUrl/simulate" `
            -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
        return $response
    }
    catch {
        Write-Host ""
        Write-Host "  [BashGuard] Could not reach server. Running command without check." -ForegroundColor Yellow
        return $null
    }
}

function Show-BashGuardWarning {
    param($Simulation)
    
    $riskColors = @{
        "CRITICAL" = "Red"
        "HIGH"     = "Red"
        "MEDIUM"   = "Yellow"
        "LOW"      = "Green"
    }
    
    $color = $riskColors[$Simulation.risk_level]
    if (-not $color) { $color = "White" }
    
    Write-Host ""
    Write-Host "  =============================================" -ForegroundColor Cyan
    Write-Host "  BASHGUARD — COMMAND INTERCEPTED" -ForegroundColor Cyan
    Write-Host "  =============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Command: $($Simulation.planned_command)" -ForegroundColor White
    Write-Host "  Risk:    $($Simulation.risk_level) ($($Simulation.risk_score)/100)" -ForegroundColor $color
    Write-Host "  Undo:    $(if ($Simulation.is_reversible) { 'Possible' } else { 'IMPOSSIBLE' })" -ForegroundColor $(if ($Simulation.is_reversible) { "Green" } else { "Red" })
    Write-Host ""
    
    # Show risk reasons
    if ($Simulation.risk_reasons) {
        Write-Host "  Why this is risky:" -ForegroundColor Yellow
        $i = 1
        foreach ($reason in $Simulation.risk_reasons) {
            Write-Host "    $i. $reason" -ForegroundColor Yellow
            $i++
        }
        Write-Host ""
    }
    
    # Show warnings
    if ($Simulation.warnings) {
        foreach ($w in $Simulation.warnings) {
            Write-Host "  WARNING: $w" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    # Show safer alternative
    if ($Simulation.safer_command) {
        Write-Host "  Safer alternative: $($Simulation.safer_command)" -ForegroundColor Green
        Write-Host ""
    }
    
    Write-Host "  =============================================" -ForegroundColor Cyan
}

# ============================================================
#  PSREADLINE HOOK — THE MAGIC
# ============================================================

Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
    # Get the current command line
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    
    $command = $line.Trim()
    
    # Skip empty lines
    if ([string]::IsNullOrWhiteSpace($command)) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }
    
    # Skip if BashGuard is disabled
    if (-not $Global:BashGuardEnabled) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }
    
    # CHECK 1: Is it a known safe command? → Let it through
    if (Test-IsSafeCommand $command) {
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
        return
    }
    
    # CHECK 2: Is it hard-blocked? → BLOCK immediately
    if (Test-IsHardBlocked $command) {
        Write-Host ""
        Write-Host ""
        Write-Host "  =============================================" -ForegroundColor Red
        Write-Host "  BASHGUARD — COMMAND BLOCKED" -ForegroundColor Red
        Write-Host "  =============================================" -ForegroundColor Red
        Write-Host "  This command is on the PERMANENT block list." -ForegroundColor Red
        Write-Host "  It cannot be executed under any circumstances." -ForegroundColor Red
        Write-Host "  Command: $command" -ForegroundColor White
        Write-Host "  =============================================" -ForegroundColor Red
        Write-Host ""
        
        # Clear the line and don't execute
        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
        [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
        return
    }
    
    # CHECK 3: Does it contain dangerous keywords? → Full simulation
    if (Test-HasDangerousKeyword $command) {
        Write-Host ""
        Write-Host ""
        Write-Host "  [BashGuard] Dangerous keyword detected. Running simulation..." -ForegroundColor Cyan
        
        $sim = Invoke-BashGuardSimulation $command
        
        if ($null -eq $sim) {
            # Server not reachable — ask user
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
        
        # Show warning if risky
        if ($sim.risk_level -in @("CRITICAL", "HIGH", "MEDIUM")) {
            Show-BashGuardWarning $sim
            
            if ($sim.safer_command) {
                Write-Host "  [A]pprove  |  [S]afer alternative  |  [C]ancel" -ForegroundColor White
            } else {
                Write-Host "  [A]pprove  |  [C]ancel" -ForegroundColor White
            }
            Write-Host "  Choice: " -ForegroundColor Cyan -NoNewline
            $choice = Read-Host
            
            switch ($choice.ToLower()) {
                { $_ -in "a", "approve", "y", "yes" } {
                    Write-Host "  [BashGuard] Approved. Executing..." -ForegroundColor Green
                    [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                    [Microsoft.PowerShell.PSConsoleReadLine]::Insert($command)
                    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
                }
                { $_ -in "s", "safer", "safe" } {
                    if ($sim.safer_command) {
                        Write-Host "  [BashGuard] Using safer alternative..." -ForegroundColor Green
                        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                        [Microsoft.PowerShell.PSConsoleReadLine]::Insert($sim.safer_command)
                        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
                    } else {
                        Write-Host "  [BashGuard] No safer alternative. Cancelled." -ForegroundColor Yellow
                        [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                        [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
                    }
                }
                default {
                    Write-Host "  [BashGuard] Command CANCELLED." -ForegroundColor Red
                    [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                    [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
                }
            }
            return
        }
        
        # Low risk with dangerous keyword — let through with note
        Write-Host ""
        Write-Host "  [BashGuard] Checked — LOW risk. Proceeding." -ForegroundColor Green
    }
    
    # Default: execute the command
    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
}

# ============================================================
#  HELPER COMMANDS
# ============================================================

function bashguard-off {
    $Global:BashGuardEnabled = $false
    Write-Host "  [BashGuard] Protection DISABLED." -ForegroundColor Yellow
}

function bashguard-on {
    $Global:BashGuardEnabled = $true
    Write-Host "  [BashGuard] Protection ENABLED." -ForegroundColor Green
}

function bashguard-status {
    $status = if ($Global:BashGuardEnabled) { "ACTIVE" } else { "DISABLED" }
    $color = if ($Global:BashGuardEnabled) { "Green" } else { "Red" }
    Write-Host ""
    Write-Host "  BashGuard Status: $status" -ForegroundColor $color
    Write-Host "  Server: $Global:BashGuardServerUrl" -ForegroundColor White
    
    try {
        $health = Invoke-RestMethod -Uri "$Global:BashGuardServerUrl/" -TimeoutSec 3
        Write-Host "  Server Status: RUNNING" -ForegroundColor Green
    } catch {
        Write-Host "  Server Status: OFFLINE" -ForegroundColor Red
    }
    Write-Host ""
}

# ============================================================
#  STARTUP
# ============================================================

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "  BashGuard — Real-Time Terminal Protection" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "  Status: ACTIVE" -ForegroundColor Green
Write-Host "  Every command is checked before execution." -ForegroundColor White
Write-Host ""
Write-Host "  Commands:" -ForegroundColor White
Write-Host "    bashguard-status  — Check status" -ForegroundColor Gray
Write-Host "    bashguard-off     — Disable protection" -ForegroundColor Gray
Write-Host "    bashguard-on      — Enable protection" -ForegroundColor Gray
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""
