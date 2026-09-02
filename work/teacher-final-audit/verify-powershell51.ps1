$files = @(Get-ChildItem -Path . -Recurse -Filter *.ps1 -File | Where-Object {
    $_.FullName -notmatch '\\(node_modules|\.venv-ms|\.venv|\.ci-results|work)\\'
})
$errors = @()
foreach ($file in $files) {
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -gt 0) {
        $errors += $parseErrors | ForEach-Object { "$($file.Name):$($_.Message)" }
    }
}
Write-Output "POWERSHELL51_FILES=$($files.Count) PARSE_ERRORS=$($errors.Count)"
if ($errors.Count -gt 0) {
    $errors | Select-Object -First 10
    exit 1
}
