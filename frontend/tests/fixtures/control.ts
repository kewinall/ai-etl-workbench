import {execFileSync} from 'node:child_process';

// Run one control-only pass (the same Python the isolated API image runs) for a single approved Run.
// Default keeps the original target: the isolated compose API container on the Windows/WSL host.
// WORKBENCH_CONTROL_PYTHON=<python> runs it against a local isolated API instead; the caller's environment
// (DATABASE_URL, WORKBENCH_EXECUTION_ENABLED=false, ...) and WORKBENCH_CONTROL_CWD must point at that API.
export function controlOnce(script: string, runId: string): string {
  const python = process.env.WORKBENCH_CONTROL_PYTHON;
  if (python) return execFileSync(python, ['-c', script, runId], {encoding: 'utf8', timeout: 30000, cwd: process.env.WORKBENCH_CONTROL_CWD, env: process.env});
  return execFileSync('wsl', ['-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'exec',
    process.env.WORKBENCH_CONTROL_CONTAINER || 'ai-etl-ui-regression-api-1', 'python', '-c', script, runId], {encoding: 'utf8', timeout: 30000});
}

// These tests rewrite platform settings and create synthetic data, so they only run where explicitly allowed.
export const syntheticWritesAllowed = () => process.env.WORKBENCH_ALLOW_SYNTHETIC_UI === '1';
