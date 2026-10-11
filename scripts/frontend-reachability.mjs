// Usage: node scripts/frontend-reachability.mjs frontend  (read-only: lists src files not statically reachable from src/main.tsx)
// Static import reachability from the entry; also reports dynamic import() usage.
import fs from 'fs';import path from 'path';
const root=path.resolve(process.argv[2]),entry=path.join(root,'src/main.tsx');
const seen=new Set(),dyn=[];
const resolve=(from,spec)=>{if(!spec.startsWith('.'))return null;const base=path.resolve(path.dirname(from),spec);for(const ext of ['','.tsx','.ts','.css','.mjs','/index.ts','/index.tsx'])if(fs.existsSync(base+ext)&&fs.statSync(base+ext).isFile())return base+ext;return 'MISSING:'+base};
const walk=f=>{if(seen.has(f))return;seen.add(f);if(!/\.(tsx?|mjs)$/.test(f))return;const s=fs.readFileSync(f,'utf8');
 for(const m of s.matchAll(/(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]/g)){const r=resolve(f,m[1]||m[2]);if(r)walk(r)}
 for(const m of s.matchAll(/import\(\s*['"]([^'"]+)['"]\s*\)/g)){dyn.push([path.relative(root,f),m[1]]);const r=resolve(f,m[1]);if(r)walk(r)}};
walk(entry);
const all=[];const list=d=>{for(const e of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,e.name);if(e.isDirectory())list(p);else all.push(p)}};list(path.join(root,'src'));
console.log(JSON.stringify({reachable:[...seen].map(f=>path.relative(root,f)).sort(),unreachable:all.filter(f=>!seen.has(f)).map(f=>path.relative(root,f)).sort(),dynamic:dyn},null,1));
