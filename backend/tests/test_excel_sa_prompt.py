"""SA prompt binding tests with synthetic completion; not real model acceptance."""
import json
from types import SimpleNamespace as NS
import pytest
from app.sa_contract import build_sa_context,digest
from app.sa_gateway import sa_material,complete_sa_review,SAInvocationError,PROMPT,PROMPT_VERSION
from app.sa_work_queue import authorization_offer
from test_excel_specification import excel_design
from test_sa_gateway import values


def setup():
    _,run,_=excel_design()
    template,profile=values()
    run.update({k:template[k] for k in ('state','write_started','matches_current','approval','settings_snapshot')})
    run['settings_snapshot']['ai']={'provider_type':profile['provider_type']}
    return run,profile


def test_excel_gateway_offer_and_trace_share_exact_material():
    run,profile=setup()
    context=build_sa_context(run)
    material=sa_material(context)
    assert context['deterministic_gate']['status']=='CHECKED'
    assert material['prompt_version']==7
    assert 'source.0.excel_input' in material['prompt'] and 'not a CSV conversion' in material['prompt']
    assert authorization_offer(run)['prompt_checksum']==material['prompt_checksum']
    calls=[]
    def completion(**kwargs):
        calls.append(kwargs)
        assert kwargs['messages'][0]['content']==material['prompt']
        assert json.loads(kwargs['messages'][1]['content'])['context']==context
        output=dict(version=1,run_id=context['run_id'],input_checksum=context['input_checksum'],
                    context_checksum=context['context_checksum'],status='READY_FOR_REVIEW',
                    summary='Synthetic review',evidence_ids=['requirement','source.0.excel_input'],issues=[])
        return NS(choices=[NS(message=NS(content=json.dumps(output)))],usage=NS(prompt_tokens=3,completion_tokens=4,total_tokens=7))
    result,trace=complete_sa_review(run,profile,completion=completion)
    assert len(calls)==1 and result['status']=='READY_FOR_REVIEW'
    assert trace['prompt_version']==7 and trace['prompt_checksum']==material['prompt_checksum']
    assert not trace['execution_authorized']


def test_excel_missing_contract_blocks_before_model_call():
    run,profile=setup()
    run['input_snapshot']['source_config'].pop('excel_input_contract_v1')
    with pytest.raises(SAInvocationError,match='SA_GATE_BLOCKED'):
        complete_sa_review(run,profile,completion=lambda **k:pytest.fail('Blocked context invoked provider'))


def test_csv_prompt_bytes_and_version_remain_unchanged():
    run,_=values()
    assert sa_material(build_sa_context(run))==dict(prompt=PROMPT,prompt_version=PROMPT_VERSION,prompt_checksum=digest(PROMPT))
    assert PROMPT_VERSION==6
