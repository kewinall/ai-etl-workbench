$ErrorActionPreference='Stop'; $PSNativeCommandUseErrorActionPreference=$true; $Root=Split-Path -Parent $PSScriptRoot
Push-Location "$Root\backend"; & "$Root\.venv\Scripts\python.exe" -m pytest -q; Pop-Location
$Runtime='C:\Users\kewin\.cache\codex-runtimes\codex-primary-runtime\dependencies'; $env:PATH="$Runtime\node\bin;$env:PATH"; Push-Location "$Root\frontend"; & "$Runtime\bin\fallback\pnpm.cmd" build; if($LASTEXITCODE -ne 0){throw 'Frontend build failed'}; Pop-Location
