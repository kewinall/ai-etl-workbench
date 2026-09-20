"""Resolve explicit settings without reading environment or developer defaults."""
from hashlib import sha256
import json

from .model_gateway import completion_options, GatewayError


def resolve_settings(repo, task, overrides=None):
    overrides = {} if overrides is None else overrides
    if not isinstance(overrides, dict):
        return {'status': 'BLOCKED', 'issues': [{'code': 'TASK_SETTINGS_INVALID'}], 'snapshot': None}
    project = repo.get_project(task.get('project_id'))
    if not project:
        return {'status': 'BLOCKED', 'issues': [{'code': 'PROJECT_NOT_FOUND'}], 'snapshot': None}
    strategy = repo.setting('ai_provider_model_strategy', {})
    connections = repo.setting('data_connections_targets', {})
    invalid_groups = [name for name, value in (
        ('ai_provider_model_strategy', strategy), ('data_connections_targets', connections)
    ) if not isinstance(value, dict)]
    if invalid_groups:
        return {'status': 'BLOCKED', 'issues': [
            {'code': 'SETTINGS_GROUP_INVALID', 'group': name} for name in invalid_groups
        ], 'snapshot': None}
    def select(key, project_key, fallback):
        if key in overrides:
            return overrides[key], 'TASK'
        if project.get(project_key):
            return project[project_key], 'PROJECT'
        return fallback, 'PLATFORM'
    ai_id, ai_origin = select('ai_profile_id', 'default_ai_profile', strategy.get('default_profile'))
    default_connection = connections.get('etl_qa')
    fallback = default_connection.get('connection_id') if isinstance(default_connection, dict) else default_connection
    connection_id, connection_origin = select('connection_id', 'default_connection', fallback)
    issues = []
    profile = repo.ai_profile(ai_id) if isinstance(ai_id, str) and ai_id.strip() else None
    routes = {}
    if profile is None:
        issues.append({'code': 'AI_PROFILE_NOT_FOUND'})
    else:
        # Resolve all Pilot roles independently; never copy another role's model.
        for role in ('requirement_gate', 'etl_specification', 'qa_review'):
            try:
                # Configuration validation only. No secret is decrypted or sent.
                probe = {**profile, 'secret_ref': None}
                options = completion_options(probe, role, 'CONFIGURATION_CHECK_ONLY' if profile.get('provider_type') == 'LITELLM_PROXY' else None)
                routes[role] = options['model']
            except GatewayError as exc:
                issues.append({'code': str(exc), 'role': role})
        if profile.get('provider_type') == 'LITELLM_PROXY' and not profile.get('secret_ref'):
            issues.append({'code': 'AI_SECRET_UNAVAILABLE'})
    connection = next((item for item in connections.values() if isinstance(item, dict) and item.get('connection_id') == connection_id), None)
    connection_snapshot = None
    if connection is None or not connection_id:
        issues.append({'code': 'CONNECTION_NOT_CONFIGURED'})
    else:
        # PostgreSQL deployment settings must never become the ETL target.
        if connection is not connections.get('etl_qa'):
            issues.append({'code': 'ETL_CONNECTION_NOT_ALLOWED'})
        for field in ('host', 'database', 'user'):
            if not isinstance(connection.get(field), str) or not connection[field].strip():
                issues.append({'code': 'CONNECTION_FIELD_MISSING', 'field': field})
        port = connection.get('port')
        if isinstance(port, str) and port.isdigit():
            port = int(port)
        if type(port) is not int or not 1 <= port <= 65535:
            issues.append({'code': 'CONNECTION_PORT_INVALID'})
        # Missing TLS stays explicit as None: preparation must not infer a mode.
        connection_snapshot = {key: connection.get(key) for key in ('connection_id', 'host', 'database', 'user', 'tlsmode')}
        connection_snapshot.update(type='VERTICA', port=port)
    secret_version = getattr(repo, 'secret_version', lambda _: None)
    snapshot = {'version': 1, 'project_id': str(task.get('project_id')),
                'ai_profile_version': str(profile.get('updated_at')) if profile and profile.get('updated_at') else None,
                'credential_versions': {
                    'ai': secret_version(profile['secret_ref']) if profile and profile.get('secret_ref') else None,
                    'connection': secret_version('connection:' + connection_id) if isinstance(connection_id, str) else None,
                },
                'ai_profile_id': ai_id, 'connection_id': connection_id,
                'origins': {'ai_profile': ai_origin, 'connection': connection_origin},
                'ai': {key: profile.get(key) for key in ('provider_type', 'region', 'endpoint')} if profile else None,
                'model_routes': routes, 'connection': connection_snapshot}
    # Never return a partially valid snapshot suitable for execution.
    if issues:
        return {'status': 'BLOCKED', 'issues': issues, 'snapshot': None}
    snapshot['checksum'] = sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'status': 'CONFIGURED_NOT_TESTED', 'issues': [], 'snapshot': snapshot}
