# Exercise the real bootstrap with a single python.exe command, no py/uv and no
# model/dependency downloads. A prewritten dependency stamp isolates dispatch.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$scratch = Join-Path $env:RUNNER_TEMP "doc-reader-launcher-test"
$env:DOC_READER_VENV_DIR = Join-Path $scratch "test env"
$env:DOC_READER_SKIP_WINGET = "1"
New-Item -ItemType Directory -Force $env:DOC_READER_VENV_DIR | Out-Null
$hash = (Get-FileHash -Algorithm SHA256 (Join-Path $repo "requirements-windows.txt")).Hash + (Get-FileHash -Algorithm SHA256 (Join-Path $repo "requirements.txt")).Hash
Set-Content (Join-Path $env:DOC_READER_VENV_DIR ".requirements-windows.sha256") $hash -Encoding ascii

function Get-Command {
    [CmdletBinding()]
    param([string] $Name)
    if ($Name -in @("uv", "py", "winget")) { return $null }
    Microsoft.PowerShell.Core\Get-Command $Name -ErrorAction SilentlyContinue
}

& (Join-Path $repo "run-doc-reader.ps1") --prepare-only
if ($LASTEXITCODE -ne 0) { throw "Bootstrap failed: $LASTEXITCODE" }
$python = Join-Path $env:DOC_READER_VENV_DIR "Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Bootstrap did not create the venv" }

& (Join-Path $repo "run-doc-reader.ps1") cli --help
if ($LASTEXITCODE -ne 0) { throw "CLI help failed: $LASTEXITCODE" }

# Bare cli must pass no synthetic 'cli' filename through the PowerShell slice.
$info = New-Object System.Diagnostics.ProcessStartInfo
$info.FileName = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$info.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $repo "run-doc-reader.ps1") + '" cli'
$info.UseShellExecute = $false
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$process = [System.Diagnostics.Process]::Start($info)
$output = $process.StandardOutput.ReadToEnd() + $process.StandardError.ReadToEnd()
$process.WaitForExit()
if ($process.ExitCode -ne 2 -or $output -notmatch "required") {
    throw "Bare CLI did not report its missing input: $output"
}
Write-Host "Windows launcher smoke checks passed"
