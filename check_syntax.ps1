$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot "bashguard_hook.ps1"),
    [ref]$tokens,
    [ref]$errors
)
if ($errors.Count -eq 0) {
    Write-Host "SYNTAX OK - No parse errors found" -ForegroundColor Green
} else {
    Write-Host "ERRORS FOUND:" -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "  $($e.Message)" -ForegroundColor Red
    }
}
