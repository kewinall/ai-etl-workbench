param([switch]$SkipFrontend)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$Runtime='C:\Users\kewin\.cache\codex-runtimes\codex-primary-runtime\dependencies'
$env:PATH="$Runtime\node\bin;$env:PATH"
$Python=if(Test-Path "$Runtime\python\python.exe"){"$Runtime\python\python.exe"}else{'python'}
$Pnpm=if(Test-Path "$Runtime\bin\fallback\pnpm.cmd"){"$Runtime\bin\fallback\pnpm.cmd"}else{'pnpm'}
if(!(Test-Path "$Root\.env")){Copy-Item "$Root\.env.example" "$Root\.env"}
& $Python -m venv "$Root\.venv"
& "$Root\.venv\Scripts\python.exe" -m pip install -r "$Root\backend\requirements.txt"
if(!$SkipFrontend){Push-Location "$Root\frontend"; & $Pnpm install; Pop-Location}
New-Item -ItemType Directory -Force "$Root\runtime-temp","$Root\hop-project\pipelines","$Root\hop-project\workflows" | Out-Null
$VerticaDriver="$Root\hop\lib\jdbc\vertica-jdbc-24.2.0-1.jar"
$VerticaPluginLib="$Root\hop\plugins\databases\generic\lib"
if((Test-Path "$Root\hop") -and !(Test-Path $VerticaDriver)){
 New-Item -ItemType Directory -Force (Split-Path $VerticaDriver),$VerticaPluginLib | Out-Null
 Invoke-WebRequest 'https://www.vertica.com/client_drivers/24.2.x/24.2.0-1/vertica-jdbc-24.2.0-1.jar' -OutFile $VerticaDriver
}
if(Test-Path $VerticaDriver){New-Item -ItemType Directory -Force $VerticaPluginLib | Out-Null;Copy-Item $VerticaDriver "$VerticaPluginLib\vertica-jdbc-24.2.0-1.jar" -Force}
Write-Host 'Setup complete. Update .env with PostgreSQL and optional Vertica values.' -ForegroundColor Green
