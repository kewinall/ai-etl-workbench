export type Route = {page: string; projectId?: string; tab?: string; taskId?: string};
export function readRoute(): Route {
  let path: string;
  try {path = decodeURIComponent(window.location.hash.slice(1))} catch {return {page: 'projects'}}
  const parts = path.split('/').filter(Boolean);
  if (parts[0] === 'projects') {
    if (parts[2] === 'tasks' && parts[3]) return {page: parts[3] === 'new' ? 'new' : 'task', projectId: parts[1], taskId: parts[3] === 'new' ? undefined : parts[3], tab: parts[4]};
    return {page: 'projects', projectId: parts[1], tab: parts[2] === 'history' ? 'history' : 'settings'};
  }
  if (parts[0] === 'dashboard') return {page: 'projects'};
  if (parts[0] === 'usage') return {page: 'pilot'};
  if (parts[0] === 'models' || parts[0] === 'database') return {page: 'system'};
  if (['pilot','system','guide'].includes(parts[0])) return {page: parts[0]};
  return {page: 'projects'};
}
