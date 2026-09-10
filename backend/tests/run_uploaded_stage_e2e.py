"""Verify a browser-style JSON upload is transferred to Vertica Flex storage."""
import json, os, sys
from pathlib import Path
import vertica_python
from dotenv import load_dotenv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));load_dotenv()
from app.task_uploads import save_and_profile
from app.sample_data import materialize_stage_server_sample
from app.execution import build_stage_hwf,static_validate

source_file=Path(__file__).resolve().parents[2]/"examples"/"stage-flex-upload.json"
profile=save_and_profile(source_file.name,source_file.read_bytes())
source={"id":"source_1","alias":"uploaded_json","type":"JSON","has_actual_data":True,**profile}
target={"stage_mode":"FLEX","format":"JSON","data_directory":"/data/ai_agents_v2_flex_20260820_v4","reject_path":"/data/ai_agents_v2_reject","exception_path":"/data/ai_agents_v2_exception","schema":"public","table":"uploaded_flex_e2e"}
target=materialize_stage_server_sample("UPLOADED-FLEX-E2E",target,source)
artifact=build_stage_hwf({"id":"UPLOADED-FLEX-E2E","category":"STAGE","source":"JSON","source_config":{"sources":[source]},"target_config":target},[x["name"] for x in source["fields"]]);assert static_validate(artifact)["valid"]
cfg={"host":os.getenv("VERTICA_HOST"),"port":int(os.getenv("VERTICA_PORT","5433")),"database":os.getenv("VERTICA_DATABASE"),"user":os.getenv("VERTICA_USER"),"password":os.getenv("VERTICA_PASSWORD"),"tlsmode":os.getenv("VERTICA_TLSMODE")}
with vertica_python.connect(**cfg) as conn:
 cur=conn.cursor();cur.execute("DROP TABLE IF EXISTS public.uploaded_flex_e2e")
 for statement in [x.strip() for x in artifact["sql"].split(";") if x.strip()]:cur.execute(statement)
 cur.execute("SELECT COUNT(*) FROM public.uploaded_flex_e2e");rows=cur.fetchone()[0]
print(json.dumps({"uploaded":source["original_name"],"server_path":target["data_path"],"rows":rows,"artifact":artifact["path"]},ensure_ascii=False,indent=2))
