"""Deterministic local engine metadata, verified against Hop 2.12.

This is not sufficient to execute a database pipeline: etl_target metadata
must be supplied separately from the resolved, authorized connection.
"""
import json
import re


def vertica_metadata_json(connection):
    """Private runtime metadata, not a releasable artifact or execution grant.

    Caller must supply the authorized snapshot and separately inject the secret
    into the child environment. No password or arbitrary JDBC options accepted.
    """
    if not isinstance(connection, dict) or connection.get('type') != 'VERTICA':
        raise ValueError('VERTICA_CONNECTION_REQUIRED')
    if any(key in connection for key in ('password', 'secret', 'url', 'options')):
        raise ValueError('UNEXPECTED_CONNECTION_INPUT')
    for key in ('host', 'database', 'user'):
        value = connection.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,253}', value):
            raise ValueError('INVALID_CONNECTION_FIELD')
    port = connection.get('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('INVALID_CONNECTION_PORT')
    mode = connection.get('tlsmode')
    if mode not in ('disable', 'require', 'verify-ca', 'verify-full'):
        raise ValueError('EXPLICIT_TLS_MODE_REQUIRED')
    metadata = local_metadata()
    metadata['rdbms'] = [{'name': 'etl_target', 'virtualPath': None, 'rdbms': {'VERTICA5': {
        'databaseName': connection['database'], 'pluginId': 'VERTICA5', 'pluginName': 'Vertica 5',
        'accessType': 0, 'hostname': connection['host'], 'port': str(port),
        'username': connection['user'], 'password': '${WORKBENCH_VERTICA_PASSWORD}',
        'indexTablespace': None, 'dataTablespace': None, 'servername': None, 'manualUrl': None,
        'attributes': {'SUPPORTS_TIMESTAMP_DATA_TYPE': 'Y', 'SUPPORTS_BOOLEAN_DATA_TYPE': 'Y',
                       'EXTRA_OPTION_VERTICA5.TLSmode': mode},
    }}}]
    return json.dumps(metadata, sort_keys=True, separators=(',', ':'))


def local_metadata():
    return {'pipeline-run-configuration': [{
        'name':'local', 'defaultSelection':False, 'configurationVariables':[],
        'engineRunConfiguration':{'Local':{
            'feedback_size':'50000', 'rowset_size':'10000', 'wait_time':'20',
            'sample_size':'100', 'sample_type_in_gui':'Last',
            'safe_mode':False, 'show_feedback':False, 'topo_sort':False,
            'gather_metrics':True, 'transactional':False,
        }},
    }]}


def local_metadata_json():
    return json.dumps(local_metadata(),sort_keys=True,separators=(',',':'))
