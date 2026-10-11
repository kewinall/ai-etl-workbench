// One-shot write tests must never target the operator's shared deployments.
// An explicit URL is necessary but insufficient: each caller also verifies the
// server's execution-disabled status, unique fixture Task/Run and retained proof.
export function requireDedicatedReconciliationURL(baseURL:string|undefined,expected:string|undefined){
 if(!baseURL||!expected)throw new Error('Explicit dedicated reconciliation URL is required');
 const actual=new URL(baseURL),configured=new URL(expected);
 for(const value of [actual,configured]){
  if(value.protocol!=='http:'||value.hostname!=='127.0.0.1'||value.username||value.password||
    value.pathname!=='/'||value.search||value.hash||Number(value.port)<5201||Number(value.port)>5299)
   throw new Error('Reconciliation writes require a dedicated loopback port 5201–5299; shared environments are forbidden');
 }
 if(actual.origin!==configured.origin)throw new Error('Dedicated reconciliation URL does not match the selected browser environment');
}
