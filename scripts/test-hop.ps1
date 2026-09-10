$Root=Split-Path -Parent $PSScriptRoot; $hop=(Get-Content "$Root\.env"|Where-Object{$_ -like 'HOP_RUN_PATH=*'}).Substring(13)
if(!(Test-Path $hop)){throw "hop-run.bat not found: $hop"}
$output=& $hop -v 2>&1 | Out-String
if($output -notmatch '\d+\.\d+\.\d+'){throw "Hop did not report a version.`n$output"}
Write-Host ("Apache Hop ready: " + $Matches[0]) -ForegroundColor Green
