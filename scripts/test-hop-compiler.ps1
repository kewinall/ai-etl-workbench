param([string]$Distribution = 'RockyLinux9')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root 'backend')
try {
    & ../.venv/Scripts/python.exe -m pytest tests/test_hpl_compiler.py tests/test_etl_specification.py -q
    if ($LASTEXITCODE -ne 0) { throw 'Compiler unit tests failed.' }
    & ../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'tests'); from pathlib import Path; from test_etl_specification import design; from app.hpl_compiler import compile_hpl; p=Path('../outputs/hop-compiler'); p.mkdir(parents=True,exist_ok=True); r=compile_hpl(*design()); (p/'candidate.hpl').write_text(r['hpl'],encoding='utf-8'); print('candidate_sha256='+r['hpl_checksum'])"
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic candidate generation failed.' }
    & ../.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'tests'); from pathlib import Path; from test_etl_specification import design; from app.csv_content_validation import validate_csv_content; _,r,_=design(); c=r['input_snapshot']['source_config']; result=validate_csv_content(Path('../scripts/hop/fixtures/compiler-input.csv').read_bytes(),c['csv_input_contract_v1'],[f['name'] for f in c['sources'][0]['fields']]); assert result['complete'] and not result['issues'],result; print('CSV_PREFLIGHT_PASSED records='+str(result['records_checked'])+' sha256='+result['content_checksum'])"
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic CSV content preflight failed.' }
} finally { Pop-Location }
$linuxRoot = [string](& wsl -d $Distribution -u root -- wslpath -a $root.Replace('\', '/'))
if ($LASTEXITCODE -ne 0 -or !$linuxRoot.StartsWith('/')) { throw 'Cannot resolve workspace path.' }
$linuxRoot = $linuxRoot.Trim()
$output = & wsl -d $Distribution -u root -- docker run --rm --pull never --network none --hostname hop-validation --add-host hop-validation:127.0.0.1 --entrypoint java -w /opt/hop -v "${linuxRoot}/scripts/hop:/validation:ro" -v "${linuxRoot}/outputs/hop-compiler:/candidate:ro" apache/hop:2.12.0 -DHOP_AUTO_CREATE_CONFIG=Y -cp 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*' /validation/ValidatePipeline.java /candidate/candidate.hpl --compiler-probe 2>&1
$code = $LASTEXITCODE
$result = $output -join "`n"
if ($code -ne 0 -or !$result.Contains('HOP_COMPILER_PROBE_PASSED fields=3 execution=false') -or !$result.Contains('HOP_METADATA_LOADED transforms=7 hops=6 execution=false')) {
    throw "Native compiler probe failed (exit=$code)."
}
Write-Output $result
Write-Output 'PASS compiler metadata; starting fixed synthetic Hop row probe (no database target).'
$output = & wsl -d $Distribution -u root -- docker run --rm --pull never --network none --hostname hop-validation --add-host hop-validation:127.0.0.1 --entrypoint java -w /opt/hop -v "${linuxRoot}/scripts/hop:/validation:ro" -v "${linuxRoot}/outputs/hop-compiler:/candidate:ro" apache/hop:2.12.0 -DHOP_AUTO_CREATE_CONFIG=Y -cp 'lib/core/*:lib/beam/*:lib/swt/linux/x86_64/*' /validation/ExecuteCompilerProbe.java 2>&1
$code = $LASTEXITCODE
$result = $output -join "`n"
if ($code -ne 0 -or !$result.Contains('HOP_ROW_PROBE_PASSED rows=3 errors=0 target=TEST_COLLECTOR vertica=false release=false')) {
    throw "Native row probe failed (exit=$code)."
}
Write-Output $result
Write-Output 'PASS fixed synthetic row result; Vertica QA and Release remain unverified.'
