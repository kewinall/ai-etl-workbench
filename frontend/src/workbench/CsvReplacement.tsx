import {useState} from 'react';
import {request} from './api';

export function CsvReplacement({onChange, onPending, disabled=false}: {onChange:(value:any)=>void; onPending:(value:boolean)=>void; disabled?:boolean}) {
  const [file, setFile] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const upload = async (selected:File) => {
    setBusy(true); setError(''); setFile(null); setConfirmed(false); onChange(null); onPending(true);
    try {
      const body = new FormData(); body.append('file', selected);
      const result = await request('/api/task-sources/upload',{method:'POST',body});
      if(result.source_type !== 'CSV') throw new Error('本次修訂只支援單一 CSV，請選擇 CSV 檔案。');
      setFile(Object.fromEntries(['upload_id','checksum','size','original_name','fields'].map(key=>[key,result[key]])));
    } catch(e:any) {setError(e.message)} finally {setBusy(false)}
  };
  const cancel = () => {setFile(null);setConfirmed(false);setError('');onChange(null);onPending(false)};
  return <fieldset aria-label="更換 CSV 來源" disabled={disabled}><legend>更換來源檔案（選用）</legend>
    <p>只支援單一 CSV。上傳不會替換舊檔；確認後再保存補正，才會建立新版本。舊核准不沿用。</p>
    <label>新 CSV 檔案<input type="file" accept=".csv" disabled={busy} onChange={e=>{const selected=e.target.files?.[0];if(selected)void upload(selected);e.target.value=''}}/></label>
    {busy && <p role="status">正在上傳與分析新檔案…</p>}
    {error && <p role="alert">{error}</p>}
    {file && <><p>新檔案：{file.original_name} · {file.size} bytes</p>
      <p>偵測欄位（樣本推定，不是完整型別驗證）：</p>
      <ul>{file.fields.map((field:any,index:number)=><li key={index}>{field.name} · {field.type}</li>)}</ul>
      <label><input type="checkbox" checked={confirmed} onChange={e=>{setConfirmed(e.target.checked);onChange(e.target.checked?file:null);onPending(!e.target.checked)}}/>我已核對新檔案與欄位，確認此修訂改用新 CSV</label>
      <p>請另核對 CSV 編碼、分隔與欄位政策。若格式不符，新版 Gate 仍會阻擋。</p>
    </>}
    <button type="button" disabled={busy} onClick={cancel}>取消換檔，保留原來源</button>
  </fieldset>;
}
