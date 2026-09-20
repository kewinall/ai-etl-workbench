"""Fixed-member formal archive. Caller must enforce persisted human approval."""
from io import BytesIO
from hashlib import sha256
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED,BadZipFile
import json
from .release_bundle import MEMBERS,MAX_BUNDLE_BYTES,MAX_MEMBER_BYTES
from .sa_contract import digest


def candidate_parts(content,manifest):
    if type(content) is not bytes or not 0<len(content)<=MAX_BUNDLE_BYTES:raise ValueError('RELEASE_SIZE_INVALID')
    try:
        with ZipFile(BytesIO(content)) as archive:
            infos=archive.infolist()
            if len(infos)!=6 or {i.filename for i in infos}!=set(MEMBERS.values())|{'release-manifest.json'}:
                raise ValueError('RELEASE_MEMBERS_CHANGED')
            if any(i.file_size>MAX_MEMBER_BYTES or i.flag_bits&1 for i in infos) or sum(i.file_size for i in infos)>MAX_BUNDLE_BYTES:
                raise ValueError('RELEASE_SIZE_INVALID')
            if json.loads(archive.read('release-manifest.json'))!=manifest:raise ValueError('RELEASE_MANIFEST_CHANGED')
            content_by_name={name:archive.read(name) for name in MEMBERS.values()}
    except (BadZipFile,UnicodeDecodeError,json.JSONDecodeError):raise ValueError('RELEASE_INVALID_ARCHIVE') from None
    artifacts=manifest.get('artifacts') or []
    if len(artifacts)!=5 or {a.get('name') for a in artifacts}!=set(MEMBERS.values()):raise ValueError('RELEASE_MANIFEST_CHANGED')
    for artifact in artifacts:
        data=content_by_name[artifact['name']]
        if artifact['checksum']!=sha256(data).hexdigest() or artifact['size_bytes']!=len(data):raise ValueError('RELEASE_ARTIFACT_CHANGED')
    return content_by_name


def build_formal_bundle(candidate_content,candidate_manifest,final_sdm,binding):
    parts=candidate_parts(candidate_content,candidate_manifest)
    if candidate_manifest.get('status')!='CANDIDATE_NOT_RELEASED' or sha256(candidate_content).hexdigest()!=binding['candidate_checksum']:
        raise ValueError('RELEASE_CANDIDATE_CHANGED')
    if candidate_manifest['run_id']!=binding['run_id'] or candidate_manifest['specification_checksum']!=binding['specification_checksum']:
        raise ValueError('RELEASE_BINDING_CHANGED')
    if type(final_sdm) is not bytes or not 0<len(final_sdm)<=MAX_MEMBER_BYTES:raise ValueError('RELEASE_SIZE_INVALID')
    parts[MEMBERS['SDM']]=final_sdm
    manifest={**candidate_manifest,'document_type':'ReleaseBundleV1','status':'RELEASE_READY',
        'qa_passed':True,'release_ready':True,'portability':'ISOLATED_HOP_RESULT_VERIFIED',
        'approval_binding':binding,'approval_binding_checksum':digest(binding),
        'artifacts':[{'name':name,'type':kind,'checksum':sha256(parts[name]).hexdigest(),'size_bytes':len(parts[name])} for kind,name in MEMBERS.items()]}
    parts['release-manifest.json']=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if sum(map(len,parts.values()))>MAX_BUNDLE_BYTES:raise ValueError('RELEASE_SIZE_INVALID')
    stream=BytesIO()
    with ZipFile(stream,'w',compression=ZIP_DEFLATED,compresslevel=6) as archive:
        for name,data in parts.items():
            info=ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data,compresslevel=6)
    result=stream.getvalue()
    return {'content':result,'checksum':sha256(result).hexdigest(),'file_size':len(result),'manifest':manifest}
