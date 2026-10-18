#Requires -Version 5.1
<#
.SYNOPSIS
  EARSHOT quickstart for Windows — clone → one command → demo + live MCP server.

  Mirrors quickstart.sh step for step:
    1. virtualenv (.venv-quickstart)
    2. pip install -e .            (stdlib only)
    3. earshot-demo                (5-beat sealed-speech demo)
    4. earshot-server in background (dev token from its stderr, by design)
    5. MCP initialize → 200 + protocol 2025-11-25
    6. notifications/initialized → 202, tools/list → 200, all 6 tools present
    7. stop server, print QUICKSTART SUCCESS + timing

  Usage:  powershell -ExecutionPolicy Bypass -File quickstart.ps1 [-Fresh] [-Port 8000]

# UNTESTED ON WINDOWS — mirrors the verified quickstart.sh; the windows-latest
# CI job must run this file before it is trusted. Kept deliberately simple:
# no advanced functions, no pipeline tricks.
#>

param(
  [switch]$Fresh,
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

function Die([string]$msg) { Write-Error "QUICKSTART FAILED: $msg"; exit 1 }
function Step([string]$msg) { Write-Host "==> $msg" }

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

# repo root: this script lives there
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Root = (Get-Location).Path

# --- 0. preflight -----------------------------------------------------------
Step "[0/7] preflight"
$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) { $Python = "py -3" } else { $Python = "python" }
try { $ver = & python --version 2>&1 } catch { Die "python not found on PATH (need 3.10+)" }
if ($ver -notmatch "Python 3\.(1\d|[1-9]\d)") { Die "Python >= 3.10 required, found: $ver" }
try { curl.exe --version | Out-Null } catch { Die "curl.exe not found (stock on Windows 10+)" }
Write-Host "    $ver, curl.exe OK"

# --- 1. venv -----------------------------------------------------------------
Step "[1/7] virtualenv"
$Venv = Join-Path $Root ".venv-quickstart"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
if ($Fresh -and (Test-Path $Venv)) { Remove-Item -Recurse -Force $Venv }
$venvOk = (Test-Path $VenvPy)
if ($venvOk) {
  try { & $VenvPy -c "import earshot" 2>$null; $venvOk = ($LASTEXITCODE -eq 0) } catch { $venvOk = $false }
}
if ($venvOk) {
  Write-Host "    reusing $Venv (pass -Fresh to rebuild)"
} else {
  if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
  & python -m venv $Venv || Die "venv creation failed"
  Write-Host "    created $Venv"
}
$VenvPip = Join-Path $Venv "Scripts\python.exe"  # python -m pip, no PATH games

# --- 2. install ---------------------------------------------------------------
Step "[2/7] pip install -e ."
& $VenvPip -m pip install -q -e $Root || Die "pip install -e . failed"
& $VenvPip -c "import earshot; print('    earshot importable OK')"

# --- 3. demo ------------------------------------------------------------------
Step "[3/7] earshot-demo (5-beat sealed-speech demo)"
$DemoExe = Join-Path $Venv "Scripts\earshot-demo.exe"
$demoOut = & $DemoExe 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { Die "earshot-demo exited non-zero: $demoOut" }
if ($demoOut -notmatch "ALL 5 BEATS PASSED") { Die "demo did not report ALL 5 BEATS PASSED: $demoOut" }
Write-Host "    ALL 5 BEATS PASSED"

# --- 4. server -----------------------------------------------------------------
Step "[4/7] earshot-server on port $Port"
try {
  $probe = curl.exe -s -o NUL --max-time 2 "http://127.0.0.1:$Port/mcp" 2>$null
  if ($LASTEXITCODE -eq 0) { Die "port $Port already answers — another server running? stop it first" }
} catch { }
$ServerExe = Join-Path $Venv "Scripts\earshot-server.exe"
$errFile = [System.IO.Path]::GetTempFileName()
$server = Start-Process -FilePath $ServerExe -ArgumentList "--port $Port" `
  -RedirectStandardError $errFile -PassThru -WindowStyle Hidden
$deadline = (Get-Date).AddSeconds(15)
$up = $false
while ((Get-Date) -lt $deadline) {
  curl.exe -s -o NUL --max-time 1 "http://127.0.0.1:$Port/mcp" 2>$null
  if ($LASTEXITCODE -eq 0) { $up = $true; break }
  Start-Sleep -Milliseconds 500
}
if (-not $up) { Get-Content $errFile; Die "server did not open port $Port" }
Write-Host "    server up (pid $($server.Id))"

$tokenLine = Select-String -Path $errFile -Pattern "token=(esh_dev_\S+)" | Select-Object -First 1
if (-not $tokenLine) { Get-Content $errFile; Die "no dev token in server stderr" }
$Token = $tokenLine.Matches[0].Groups[1].Value
Write-Host "    dev token acquired (not shown)"

$baseHeaders = @{
  "Content-Type"          = "application/json"
  "Accept"                = "application/json, text/event-stream"
  "Authorization"         = "Bearer $Token"
  "MCP-Protocol-Version"  = "2025-11-25"
}
$mcp = "http://127.0.0.1:$Port/mcp"

# --- 5. initialize --------------------------------------------------------------
Step "[5/7] MCP initialize handshake (spec 2025-11-25)"
$initBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"quickstart-ps","version":"1"}}}'
$hdrFile = [System.IO.Path]::GetTempFileName()
$bodyFile = [System.IO.Path]::GetTempFileName()
$code = curl.exe -s -D $hdrFile -o $bodyFile -w "%{http_code}" --max-time 10 `
  -X POST $mcp -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Authorization: Bearer $Token" -d $initBody
if ($code -ne "200") { Get-Content $bodyFile; Die "initialize: expected HTTP 200, got $code" }
$body = Get-Content $bodyFile -Raw
if ($body -notmatch "2025-11-25") { Write-Host $body; Die "initialize: protocolVersion 2025-11-25 not in response" }
$session = (Select-String -Path $hdrFile -Pattern "^Mcp-Session-Id:\s*(\S+)" | Select-Object -First 1)
if (-not $session) { Die "initialize: no Mcp-Session-Id response header" }
$SessionId = $session.Matches[0].Groups[1].Value.Trim()
Write-Host "    200 OK, protocol 2025-11-25, session established"

# --- 6. notifications/initialized + tools/list ------------------------------------
Step "[6/7] notifications/initialized + tools/list"
$code = curl.exe -s -o NUL -w "%{http_code}" --max-time 10 -X POST $mcp `
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" `
  -H "Authorization: Bearer $Token" -H "Mcp-Session-Id: $SessionId" `
  -H "MCP-Protocol-Version: 2025-11-25" `
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
if ($code -ne "202") { Die "notifications/initialized: expected HTTP 202, got $code" }
$code = curl.exe -s -o $bodyFile -w "%{http_code}" --max-time 10 -X POST $mcp `
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" `
  -H "Authorization: Bearer $Token" -H "Mcp-Session-Id: $SessionId" `
  -H "MCP-Protocol-Version: 2025-11-25" `
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
if ($code -ne "200") { Get-Content $bodyFile; Die "tools/list: expected HTTP 200, got $code" }
$body = Get-Content $bodyFile -Raw
foreach ($tool in @("prepare_day_brief","resolve_day_change","continue_on_personal_device","withdraw_request","room","keep_secret")) {
  if ($body -notmatch $tool) { Write-Host $body; Die "tools/list: missing tool $tool" }
}
Write-Host "    202 + 200 OK, all 6 tools listed"
Remove-Item $hdrFile, $bodyFile -ErrorAction SilentlyContinue

# --- 7. shutdown ------------------------------------------------------------------
Step "[7/7] shutdown"
Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
Remove-Item $errFile -ErrorAction SilentlyContinue

$stopwatch.Stop()
$secs = [int]$stopwatch.Elapsed.TotalSeconds
Write-Host ""
Write-Host "======================================================================"
Write-Host "QUICKSTART SUCCESS in ${secs}s"
Write-Host "  pip install ......... OK (stdlib only)"
Write-Host "  earshot-demo ........ ALL 5 BEATS PASSED"
Write-Host "  earshot-server ...... MCP 2025-11-25 handshake OK, 6 tools live"
Write-Host "======================================================================"
