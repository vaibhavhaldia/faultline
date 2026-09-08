import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { analyze, validate, brief } from '../lib/impact.ts';
const demo=JSON.parse(readFileSync(new URL('../lib/demo.json',import.meta.url),'utf8'));
test('API change reaches event consumers along evidence paths',()=>{
 const r=analyze(demo,['payments-api']);
 assert.equal(r.affected.length,6);
 assert.deepEqual(r.affected.find(n=>n.id==='analytics')?.path,['payments-api','checkout','orders-topic','analytics']);
 assert.equal(r.affected.find(n=>n.id==='analytics')?.confidence,'inferred');
 assert.ok(r.unaffected.includes('payments'));
});
test('consumer does not affect its producer or other subscribers',()=>assert.deepEqual(analyze(demo,['fulfillment']).affected.map(n=>n.id),['fulfillment']));
test('filter and truncation are explicit',()=>{
 assert.ok(analyze(demo,['payments-api'],12,false).unaffected.includes('analytics'));
 assert.equal(analyze(demo,['payments-api'],1).truncated,true);
 assert.equal(analyze(demo,['payments-api']).truncated,false);
});
test('multi-seed preserves changed status and terminates cycles',()=>{
 const r=analyze(demo,['payments','ledger','payments']);
 assert.equal(r.affected.find(n=>n.id==='ledger')?.depth,0);
 assert.equal(r.affected.length,new Set(r.affected.map(n=>n.id)).size);
});
test('untrusted import rejects malformed data',()=>{
 for (const d of [{},null,{...demo,nodes:[]},{...demo,nodes:[...demo.nodes,demo.nodes[0]]},{...demo,edges:[{...demo.edges[0],target:'missing'}]},{...demo,edges:[{...demo.edges[0],evidence:'certain'}]}]) assert.throws(()=>validate(d));
});
test('brief includes limits and evidence',()=>{
 const b=brief(demo,['payments-api'],analyze(demo,['payments-api'],1));
 assert.match(b,/Depth limit/);assert.match(b,/faultline.json/);assert.match(b,/Checkout/);
});
test('invalid seeds and bounds rejected',()=>{
 assert.throws(()=>analyze(demo,[]));assert.throws(()=>analyze(demo,['absent']));assert.throws(()=>analyze(demo,['payments'],-1));
});

test('Python and browser engines agree across changes, limits and inference settings',async()=>{
 const {execFileSync}=await import('node:child_process');
 const python=process.env.FAULTLINE_PYTHON||'python3';
 const cases=JSON.parse(execFileSync(python,['-c',`
import json
from faultline.engine import analyze
from pathlib import Path
d=json.loads(Path('examples/commerce/topology.json').read_text())
print(json.dumps([{'seeds':[n['id']],'depth':depth,'inferred':inferred,'result':analyze(d,[n['id']],max_depth=depth,include_inferred=inferred)} for n in d['nodes'] for depth in [0,1,12] for inferred in [True,False]]))
`],{cwd:new URL('../../',import.meta.url),encoding:'utf8'}));
 for (const c of cases) {
  const actual=analyze(demo,c.seeds,c.depth,c.inferred);
  assert.deepEqual(actual.affected,c.result.affected.map((n:{id:string;depth:number;path:string[];edge_indices:number[];confidence:string})=>({id:n.id,depth:n.depth,path:n.path,edge_indices:n.edge_indices,confidence:n.confidence})));
  for (const key of ['owners','tests','truncated','unaffected'] as const) assert.deepEqual(actual[key],c.result[key]);
 }
});
