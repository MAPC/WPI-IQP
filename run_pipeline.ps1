param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PipelineArgs)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$MapcPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $MapcPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv .venv }
    else { throw 'Install Python 3.12 or newer, then run this launcher again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project Python environment.' }
}
$MapcRequirements = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt') -Algorithm SHA256).Hash
$MapcInstalledStamp = Join-Path $PSScriptRoot '.venv\requirements.sha256'
if (-not (Test-Path -LiteralPath $MapcInstalledStamp) -or (Get-Content -LiteralPath $MapcInstalledStamp -Raw).Trim() -ne $MapcRequirements) {
    & $MapcPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network access and the Python version.' }
    Set-Content -LiteralPath $MapcInstalledStamp -Value $MapcRequirements
}
& $MapcPython -m src.pipeline @PipelineArgs
exit $LASTEXITCODE
