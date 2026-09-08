export type Node = { id: string; label?: string; kind: string; owner?: string; paths?: string[]; tests?: string[] };
export type Edge = { source: string; target: string; kind: string; evidence: string; location: string };
export type Topology = { version: number; name?: string; nodes: Node[]; edges: Edge[] };
export type Affected = { id: string; depth: number; path: string[]; edge_indices: number[]; confidence: string };
export function validate(input: unknown): Topology {
  if (!input || typeof input !== 'object') throw Error('Choose a Faultline topology JSON file.');
  const d = input as Topology;
  if (d.version !== 1 || !Array.isArray(d.nodes) || !Array.isArray(d.edges)) throw Error('Expected version: 1, nodes and edges.');
  if (!d.nodes.length || d.nodes.length > 500 || d.edges.length > 5000) throw Error('Use 1–500 nodes and at most 5,000 edges.');
  if (d.name !== undefined && typeof d.name !== 'string') throw Error('System name must be text.');
  const ids = new Set<string>();
  for (const n of d.nodes) {
    if (!n || typeof n.id !== 'string' || !n.id.trim() || ids.has(n.id) || !['service','api','topic','database','external'].includes(n.kind)) throw Error('Invalid node kind or duplicate node ID.');
    for (const key of ['label','owner'] as const) if (n[key] !== undefined && typeof n[key] !== 'string') throw Error(`${key} must be text.`);
    for (const key of ['paths','tests'] as const) if (n[key] !== undefined && (!Array.isArray(n[key]) || n[key]!.some(v => typeof v !== 'string'))) throw Error(`${key} must be a list of strings.`);
    if (n.paths?.some(p => p.startsWith('/') || p.split('/').includes('..'))) throw Error('Paths must be repository-relative.');
    ids.add(n.id);
  }
  const keys = new Set<string>();
  for (const e of d.edges) {
    if (!e || !ids.has(e.source) || !ids.has(e.target) || !['calls','consumes','publishes','reads','writes','implements','depends_on'].includes(e.kind) || !['declared','observed','inferred'].includes(e.evidence) || typeof e.location !== 'string' || !e.location.trim()) throw Error('Each edge needs valid endpoints, kind, evidence and location.');
    const key = JSON.stringify([e.source,e.target,e.kind]);
    if (keys.has(key)) throw Error('Duplicate dependency edge.');
    keys.add(key);
  }
  return d;
}
export function analyze(data: Topology, seeds: string[], maxDepth = 12, includeInferred = true) {
  validate(data);
  if (!Number.isInteger(maxDepth) || maxDepth < 0 || maxDepth > 50) throw Error('Depth must be an integer from 0 to 50.');
  if (!seeds.length || seeds.some(s => !data.nodes.some(n => n.id === s))) throw Error('Select at least one changed node.');
  const adj = new Map<string, {id:string; index:number}[]>();
  function add(from:string,to:string,index:number) { adj.set(from,[...(adj.get(from)||[]),{id:to,index}]); }
  data.edges.forEach((e,i) => {
    if (!includeInferred && e.evidence === 'inferred') return;
    if (['calls','consumes','reads','writes','depends_on'].includes(e.kind)) add(e.target,e.source,i);
    if (['publishes','writes','implements'].includes(e.kind)) add(e.source,e.target,i);
  });
  const rows = new Map<string,Affected>();
  [...new Set(seeds)].sort().forEach(id => rows.set(id,{id,depth:0,path:[id],edge_indices:[],confidence:'changed'}));
  const queue = [...rows.keys()]; let truncated = false;
  for (let q=0;q<queue.length;q++) {
    const row = rows.get(queue[q])!;
    for (const next of (adj.get(row.id)||[]).sort((a,b)=>a.id < b.id ? -1 : a.id > b.id ? 1 : a.index-b.index)) {
      if (rows.has(next.id)) continue;
      if (row.depth >= maxDepth) { truncated = true; continue; }
      const edges = [...row.edge_indices,next.index];
      rows.set(next.id,{id:next.id,depth:row.depth+1,path:[...row.path,next.id],edge_indices:edges,confidence:edges.some(i=>data.edges[i].evidence==='inferred')?'inferred':edges.some(i=>data.edges[i].evidence==='declared')?'declared':'observed'});
      queue.push(next.id);
    }
  }
  const affected = [...rows.values()].sort((a,b)=>a.depth-b.depth || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const tests = [...new Set(data.nodes.filter(n=>rows.has(n.id)).flatMap(n=>n.tests||[]))].sort();
  const owners = [...new Set(data.nodes.filter(n=>rows.has(n.id)).map(n=>n.owner||'Unassigned'))].sort();
  return {affected,tests,owners,truncated,unaffected:data.nodes.filter(n=>!rows.has(n.id)).map(n=>n.id).sort()};
}
export function brief(data: Topology, seeds: string[], result: ReturnType<typeof analyze>) {
  return [`# Faultline impact brief — ${data.name||'System'}`,'',`Changed: ${seeds.join(', ')}`,'','## Potential impact',...result.affected.flatMap(r=>{
    const n=data.nodes.find(n=>n.id===r.id)!;
    return [`- ${n.label||n.id} (${n.kind}; ${n.owner||'Unassigned'}; ${r.confidence}): ${r.path.join(' → ')}`,...r.edge_indices.map(i=>`  - ${data.edges[i].kind}: ${data.edges[i].location} [${data.edges[i].evidence}]`)];
  }),'','## Suggested checks',...result.tests.map(t=>`- ${t}`),'','## Limits','- Potential impact from supplied topology, not a prediction of failure.','- One shortest evidence path per node; missing dependencies are not discoverable here.',...(result.truncated?['- Depth limit reached. Expand traversal before making a release decision.']:[])].join('\n')+'\n';
}
