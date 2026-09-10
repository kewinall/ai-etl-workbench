from pathlib import Path
import os
import psycopg
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[2]
load_dotenv(ROOT/'.env')

def restore():
 runtime=Path(os.getenv('RUNTIME_TEMP',ROOT/'runtime-temp'));runtime.mkdir(parents=True,exist_ok=True)
 with psycopg.connect(os.environ['DATABASE_URL']) as conn:
  rows=conn.execute("select setting_value from platform.system_setting where setting_key like 'demo.csv.%' order by setting_key").fetchall()
 for (item,) in rows:
  filename=Path(item['filename']).name
  (runtime/filename).write_text(item['content'],encoding='utf-8',newline='')
 return len(rows)

if __name__=='__main__':print(f'Restored {restore()} demo CSV fixtures')
