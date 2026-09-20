"""SA gateway dispatch, always after durable intent. No ETL execution authority."""
from .sa_journal import SAJournal
from .sa_gateway import complete_sa_review, SAInvocationError
from .run_queue import RunConflict


def dispatch_sa(queue, repo, task_id, run_id, *, authorize_model_call=False, completion=None):
    if authorize_model_call is not True:
        raise RunConflict('SA_MODEL_CALL_CONSENT_REQUIRED')
    journal = SAJournal(queue)
    reserved = journal.reserve(task_id, run_id)
    return execute_reserved_sa(queue, repo, task_id, run_id, reserved, completion=completion)


def execute_reserved_sa(queue, repo, task_id, run_id, reserved, *, completion=None):
    journal = SAJournal(queue)
    invocation_id = reserved['invocation_id']
    try:
        run = queue.detail(task_id, run_id)
        profile = repo.ai_profile(run['settings_snapshot']['ai_profile_id'])
        if not profile:
            raise RunConflict('SA_PROFILE_NOT_FOUND')
        secret = repo.read_secret(profile['secret_ref']) if profile.get('secret_ref') else None
        # Recheck after loading credentials; never retain a transaction during network I/O.
        run = queue.detail(task_id, run_id)
        if not run['matches_current']:
            raise RunConflict('SA_SETTINGS_CHANGED')
        if reserved.get('claim_token'):
            from .sa_work_queue import SAWorkQueue, authorization_offer
            if reserved['input_json']['authorization'] != authorization_offer(run):
                raise RunConflict('SA_AUTHORIZATION_VERSION_MISMATCH')
            SAWorkQueue(queue).heartbeat(invocation_id, reserved['claim_token'])
            provider = completion
            def guarded_completion(**kwargs):
                # Every bounded retry must still own its lease and current authorization.
                current = queue.detail(task_id, run_id)
                if not current['matches_current'] or current['state'] != 'NEEDS_REVIEW':
                    raise RunConflict('SA_SETTINGS_CHANGED')
                SAWorkQueue(queue).heartbeat(invocation_id, reserved['claim_token'])
                if provider is not None:
                    return provider(**kwargs)
                from litellm import completion as real_completion
                return real_completion(**kwargs)
            completion = guarded_completion
        result, trace = complete_sa_review(run, profile, secret=secret, completion=completion)
        status = journal.finish(task_id, invocation_id, result, trace, reserved.get('claim_token'))
        return {'invocation_id': str(invocation_id), 'status': status, 'execution_authorized': False}
    except Exception as error:
        trace = error.trace if isinstance(error, SAInvocationError) else {'error_code': 'SA_DISPATCH_INTERRUPTED', 'usage': None}
        # If final persistence is unavailable, the original reservation still prevents a repeat call.
        try:
            journal.hold_uncertain(task_id, invocation_id, trace)
        except Exception:
            pass
        return {'invocation_id': str(invocation_id), 'status': 'OUTCOME_REQUIRES_RECONCILIATION', 'execution_authorized': False}
