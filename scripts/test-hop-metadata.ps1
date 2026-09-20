param([string]$Distribution = 'RockyLinux9')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'hop'
$linuxSource = [string](& wsl -d $Distribution -u root -- wslpath -a $source.Replace('\', '/'))
$linuxSource = $linuxSource.Trim()
if ($LASTEXITCODE -ne 0 -or !$linuxSource.StartsWith('/')) { throw 'Cannot resolve validation fixture directory.' }
$cases = @(
    @{Name='minimal'; Code=0; Marker='HOP_METADATA_LOADED transforms=2 hops=1 execution=false'},
    @{Name='missing-plugin'; Code=2; Marker='HOP_METADATA_REJECTED'},
    @{Name='invalid-edge'; Code=2; Marker='HOP_METADATA_REJECTED'},
    @{Name='doctype'; Code=2; Marker='HOP_METADATA_REJECTED'}
)
foreach ($case in $cases) {
    $output = & wsl -d $Distribution -u root -- docker run --rm --pull never --network none --hostname hop-validation --add-host hop-validation:127.0.0.1 --entrypoint java -w /opt/hop -v "${linuxSource}:/validation:ro" apache/hop:2.12.0 -DHOP_AUTO_CREATE_CONFIG=Y -cp 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*' /validation/ValidatePipeline.java "/validation/fixtures/$($case.Name).hpl" 2>&1
    $code = $LASTEXITCODE
    $result = $output -join "`n"
    if ($code -ne $case.Code -or !$result.Contains($case.Marker)) {
        throw "Native metadata case $($case.Name) failed (exit=$code); no ETL execution was requested."
    }
    Write-Output "PASS $($case.Name) exit=$code"
}
Write-Output 'PASS 4 native Hop metadata cases; NOT row processing, DB QA, or Release validation.'
