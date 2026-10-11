// Evaluation includes an explicit null-run row even for tasks with no runs.
// A missing row is therefore an inconsistent read, never evidence of NO_RUN.
export function mergeProjectHistory(projectId:string, items:any[], evaluation:any) {
  if(evaluation.project_id!==projectId||evaluation.basis!=='ALL_PERSISTED_RUNS'||!Array.isArray(evaluation.cases)||!Array.isArray(items))
    throw Error('版本摘要與目前專案不一致');
  const latest=new Map<string,any>();
  for(const entry of evaluation.cases)if(!latest.has(entry.task_id))latest.set(entry.task_id,entry);
  if(items.length!==latest.size||items.some(task=>!latest.has(task.id)))
    throw Error('Task 清單與版本摘要更新時間不一致，請重新讀取歷史 Task。');
  return items.map(task=>{
    const run=latest.get(task.id);
    if((run.run_id==null)!==(run.state==null))throw Error('執行版本狀態不完整，請重新讀取歷史 Task。');
    return {...task,latest_run:run,display_state:run.state??'NO_RUN'};
  });
}

// Attach the server workflow projection (same reader as Task pages). Missing or unverified rows stay 待確認.
export function attachWorkflow(rows:any[], overview:any, projectId:string) {
  const valid=overview&&overview.project_id===projectId&&Array.isArray(overview.tasks);
  const byTask=new Map<string,any>((valid?overview.tasks:[]).map((t:any)=>[t.task_id,t]));
  return rows.map(row=>{
    const workflow=byTask.get(row.id);
    const runId=row.latest_run?.run_id??null;
    const consistent=workflow&&(workflow.run_id??null)===(runId==null?null:String(runId));
    return {...row,workflow:consistent&&!workflow.stale?workflow:null,
      display_state:consistent?workflow.category:'待確認'};
  });
}
