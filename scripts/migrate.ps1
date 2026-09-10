$ErrorActionPreference='Stop'; $Root=Split-Path -Parent $PSScriptRoot
if(!$env:DATABASE_URL){throw 'Please set DATABASE_URL before migration.'}
Get-ChildItem "$Root\database\migrations\*.sql" | Sort-Object Name | ForEach-Object {
 Write-Host "Applying $($_.Name)..."
 psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f $_.FullName
 if($LASTEXITCODE -ne 0){throw "Migration failed: $($_.Name)"}
}
