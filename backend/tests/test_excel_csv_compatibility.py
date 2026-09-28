"""Compare actual pre-Excel commit compiler output; no network or runtime execution."""
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import pytest
from app.hpl_compiler import compile_hpl
from app.hwf_compiler import compile_hwf
from app.sa_contract import build_sa_context
from test_etl_specification import design
from test_join_semantics import join_design
from test_source_order_compilation import ordered_design

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '25120fc520cd14d01004e20aa9a8a1718fe3ddc5'
pytestmark = pytest.mark.skipif(not (ROOT / '.git').exists(), reason='Git checkout required for immutable baseline comparison')


def baseline_module(name):
    result = subprocess.run(['git', '-c', 'safe.directory=' + ROOT.as_posix(), '-C', str(ROOT),
                             'show', BASELINE + ':backend/app/' + name + '.py'],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    module = ModuleType('app._excel_baseline_' + name)
    module.__package__ = 'app'
    sys.modules[module.__name__] = module
    exec(compile(result.stdout, BASELINE + '/' + name, 'exec'), module.__dict__)
    return module


@pytest.mark.parametrize('factory', [design, join_design, ordered_design])
def test_csv_v1_v2_v3_outputs_exactly_match_previous_commit(factory):
    baseline_spec = baseline_module('etl_specification')
    baseline_compiler = baseline_module('hpl_compiler')
    baseline_sa = baseline_module('sa_contract')
    baseline_hwf = baseline_module('hwf_compiler')
    baseline_compiler.compilation_plan = baseline_spec.compilation_plan
    baseline_hwf.compile_hpl = baseline_compiler.compile_hpl
    try:
        args = factory()
        before = baseline_compiler.compile_hpl(*args)
        assert before['status'] == 'VALIDATED_NOT_APPROVED'
        assert compile_hpl(*args) == before
        assert compile_hwf(*args) == baseline_hwf.compile_hwf(*args)
        assert build_sa_context(args[1]) == baseline_sa.build_sa_context(args[1])
    finally:
        for module in (baseline_spec, baseline_compiler, baseline_sa, baseline_hwf):
            sys.modules.pop(module.__name__, None)
