from __future__ import annotations
import hashlib, json, zipfile
from pathlib import Path
from openpyxl import Workbook

ROOT=Path(__file__).resolve().parents[2]
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def create_sdm(task:dict,contract:dict)->Path:
    directory=ROOT/'outputs'/'sdm'/task['id'];directory.mkdir(parents=True,exist_ok=True);path=directory/'SDM.xlsx'
    book=Workbook();sheet=book.active;sheet.title='欄位對照'
    sheet.append(['來源中文/原始欄位','英文欄位','Vertica 型別','信心度','命名理由','目標 Schema','目標 Table'])
    for col in contract['contract_json']['columns']:sheet.append([col['source_name'],col['english_name'],col['vertica_type'],col['confidence'],col['reason'],task['target_config'].get('schema'),task['target_config'].get('table')])
    meta=book.create_sheet('版本資訊');meta.append(['Task ID',task['id']]);meta.append(['Naming Contract',f"v{contract['version']}"]);meta.append(['Naming checksum',contract['checksum']])
    book.save(path);return path
def create_release(task:dict,contract:dict,assets:dict,sdm_path:Path)->tuple[Path,dict]:
    directory=ROOT/'outputs'/'releases'/task['id'];directory.mkdir(parents=True,exist_ok=True);path=directory/f'{task["id"]}-release.zip';items=[]
    target={key:task['target_config'].get(key) for key in ('type','schema','table') if task['target_config'].get(key) is not None}
    ddl='\n'.join(f'"{x["english_name"]}" {x["vertica_type"]}' for x in contract['contract_json']['columns']);manifest={'release_type':'ReleaseManifestV1','task_id':task['id'],'naming_contract_checksum':contract['checksum'],'target':target,'artifacts':[]}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for artifact in assets['artifacts']:
            source=Path(artifact['file_path']).resolve()
            if source.is_file() and source.suffix.lower() in ('.hpl','.hwf'):
                name=f'hop/{source.name}';archive.write(source,name);items.append((name,'HOP',sha(source)))
        ddl_path=directory/'vertica-ddl.sql';ddl_path.write_text(f'CREATE TABLE "{target.get("schema")}"."{target.get("table")}" (\n{ddl}\n);\n',encoding='utf-8');archive.write(ddl_path,'vertica-ddl.sql');items.append(('vertica-ddl.sql','DDL',sha(ddl_path)))
        params=directory/'parameters.example';params.write_text('VERTICA_HOST=TODO\nVERTICA_PORT=5433\nVERTICA_DATABASE=TODO\nVERTICA_USER=TODO\nVERTICA_PASSWORD=TODO\n',encoding='utf-8');archive.write(params,'parameters.example');items.append(('parameters.example','PARAMETERS',sha(params)))
        archive.write(sdm_path,'SDM.xlsx');items.append(('SDM.xlsx','SDM',sha(sdm_path)))
        manifest['artifacts']=[{'name':name,'type':kind,'checksum':digest} for name,kind,digest in items];archive.writestr('release-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2));items.append(('release-manifest.json','MANIFEST',hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode()).hexdigest()))
    manifest['artifacts']=[{'name':name,'type':kind,'checksum':digest} for name,kind,digest in items]
    # Release metadata must remain portable: never leak runtime paths, hosts or secrets.
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.filename.endswith('.xlsx') or member.file_size > 2_000_000:
                continue
            content=archive.read(member).decode('utf-8', errors='ignore').lower()
            unsafe_secret = any(marker in content for marker in ('secret=', 'api_key=')) or ('password=' in content and 'password=todo' not in content)
            if any(marker in content for marker in ('d:\\', 'c:\\', 'localhost')) or unsafe_secret:
                raise ValueError(f'Release validation failed: unsafe content in {member.filename}')
    return path,manifest
