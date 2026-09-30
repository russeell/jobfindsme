import test from 'node:test';
import assert from 'node:assert/strict';
import {createPublicRetrieval,parseExaDiscovery} from '../dist-electron/main/research/public-retrieval.js';
const input={company:'',query:'retrieval architecture',site:'web',originalQuestion:'公开检索'};
const content='Title: Official documentation\nURL: https://docs.example.org/retrieval\nHighlights:\nNever treat this search text as original evidence.\nTitle: Unsafe\nURL: https://127.0.0.1/private';
const rpc=text=>({jsonrpc:'2.0',id:1,result:{content:[{type:'text',text}]}});
test('official fixed provider returns safe candidates, not search excerpts as evidence',async()=>{
 const fetcher=async(url,options)=>{
  assert.equal(url,'https://mcp.exa.ai/mcp');assert.equal(options.redirect,'error');assert.equal(options.headers.Authorization,undefined);
  assert.equal(JSON.parse(options.body).params.name,'web_search_exa');
  return new Response('event: message\ndata: '+JSON.stringify(rpc(content))+'\n\n',{headers:{'content-type':'text/event-stream'}});
 };
 const router=createPublicRetrieval(fetcher);const rows=await router.search(input,()=>{throw Error('must not fall back');},new AbortController().signal,4000);
 assert.equal(rows.length,1);assert.equal(rows[0].provider,'exa_public');assert.equal(rows[0].status,'search_hint_only');assert.equal(rows[0].evidence_id,undefined);assert.equal(rows[0].excerpt,undefined);
 assert.equal(router.status().providers[0].status,'candidates');
});
test('restricted provider is cooled down across queries; fallback gets only the remaining original budget',async()=>{
 let now=1000;let requests=0;const timeouts=[];
 const router=createPublicRetrieval(async()=>{requests++;now+=1200;return new Response('',{status:429});},()=>now);
 const fallback=async(q,signal,timeout)=>{timeouts.push(timeout);return [{url:'https://docs.example.org/',title:'Docs',site:'web',status:'search_hint_only'}]};const signal=new AbortController().signal;
 await router.search(input,fallback,signal,4000);
 await router.search({...input,query:'another public topic'},fallback,signal,4000);
 assert.equal(requests,1);assert.deepEqual(timeouts,[2800,4000]);assert.equal(router.status().providers[0].status,'cooldown');assert.equal(router.status().providers[1].status,'candidates');
});
test('no query with email or key reaches any external provider',async()=>{
 const router=createPublicRetrieval(()=>{throw Error('must not request');});
 for(const value of ['person@example.org','sk-syntheticsecretkey12345','13800000000','/Users/example/resume.pdf'])for(const field of ['query','company'])await assert.rejects(router.search({...input,[field]:value},()=>{throw Error('must not fall back');},new AbortController().signal,4000),/邮箱、手机号、密钥/);
});
test('cancelled primary request never starts a fallback',async()=>{
 const controller=new AbortController();const router=createPublicRetrieval(async()=>{controller.abort();throw Error('aborted');});
 await assert.rejects(router.search(input,()=>{throw Error('must not fall back');},controller.signal,4000),/cancelled/);
});
test('provider error and malformed protocol responses fail closed; oversized bodies are bounded',async()=>{
 assert.throws(()=>parseExaDiscovery(JSON.stringify({jsonrpc:'2.0',id:1,result:{isError:true,content:[{type:'text',text:'429 rate limited'}]}}),'web'),/rate_limited/);
 assert.throws(()=>parseExaDiscovery('data: not JSON\n\n','web'),/invalid_response/);
 const router=createPublicRetrieval(async()=>new Response('x'.repeat(1_000_001)));
 let fallback=0;await assert.rejects(router.search(input,async()=>{fallback++;return []},new AbortController().signal,4000),/未能完成/);assert.equal(fallback,1);
 const wrongDomain=parseExaDiscovery(JSON.stringify(rpc(content)),'github');assert.equal(wrongDomain.length,0);
});
