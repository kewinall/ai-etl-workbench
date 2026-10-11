#!/usr/bin/env python3
"""Top-level declaration reachability inside main.tsx (regex based; reports, never edits)."""
import re,sys,json
src=open(sys.argv[1]).read().split('\n')
decl=re.compile(r'^(?:async )?(?:function|const|let|type) ([A-Za-z0-9_]+)')
blocks={};order=[];cur=None
for i,line in enumerate(src):
    m=decl.match(line)
    if m: cur=m.group(1);order.append((cur,i+1));blocks.setdefault(cur,[]).append(line)
    elif cur: blocks[cur].append(line)
reassign={};tail=[]
for line in src:
    m=re.match(r'^([A-Za-z0-9_]+)=([A-Za-z0-9_]+);',line)
    if m: reassign[m.group(1)]=m.group(2)
    if line.startswith('createRoot'): tail.append(line)
names=list(blocks)
refs={n:{o for o in names if o!=n and re.search(r'\b'+o+r'\b','\n'.join(blocks[n]))} for n in names}
for a,b in reassign.items(): refs.setdefault(a,set()).add(b)  # conservative: original body may be captured by aliases (const Base=X) before reassignment
seen=set();stack=['App']
while stack:
    n=stack.pop()
    if n in seen: continue
    seen.add(n); stack+=list(refs.get(n,()))
dead=[(n,l,len('\n'.join(blocks[n]))) for n,l in order if n not in seen]
print(json.dumps({'reassign':reassign,'live':sorted(seen),'dead':dead},ensure_ascii=False,indent=0))
