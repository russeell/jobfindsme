import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {modelHistoryWithinBudget,runPiResearchAgent} from '../dist-electron/main/research/pi-research-agent.mjs';

function sse(response,delta,reason){
 response.write(`data: ${JSON.stringify({id:'chatcmpl-mock',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta,finish_reason:null}]})}\n\n`);
 response.write(`data: ${JSON.stringify({id:'chatcmpl-mock',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta:{},finish_reason:reason}]})}\n\n`);
 response.end('data: [DONE]\n\n');
}
function tool(name,args,number){return {role:'assistant',tool_calls:[{index:0,id:`call_${number}`,type:'function',function:{name,arguments:JSON.stringify(args)}}]};}
const source={evidence_id:'ev_real',url:'https://www.zhihu.com/p/123',platform:'知乎',published_at:null,retrieved_at:'2026-09-25T00:00:00+00:00',company:'示例公司',team:null,excerpt:'示例公司在上海设立了研发团队，并介绍了产品方向。',evidence_kind:'public_source',verification_status:'independently_retrieved',relevance:'company',limitations:'个人陈述，法律主体未核实',context:{source_type:'personal_account',research_topic:'company'},status:'read_original'};
source.evidence_id='ev_'+createHash('sha256').update(`${source.url}\0${source.excerpt}`).digest('hex').slice(0,24);
test('model context budget leaves the full 15 round history intact',()=>{
 const full=Array.from({length:30},(_,index)=>({role:index%2?'assistant':'user',text:`turn ${index} `+'x'.repeat(1000)}));
 const model=modelHistoryWithinBudget(full,12000);
 assert.equal(full.length,30);assert(model.length<full.length);assert.equal(model.at(-1).text,full.at(-1).text);
 assert(model.reduce((sum,turn)=>sum+turn.text.length,0)<=12000);
});
test('Pi uses bounded tools and saves only a verified quote',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});
  turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'zhihu',question:'研发'},turn):turn===3?tool('read_page',{site:'zhihu',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}],limitations:['法律主体未核实']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port,actions=[],executions=[],reports=[];
 const tools={findEvidence:async()=>{actions.push('find');return [];},searchWeb:async(_company,question)=>{actions.push('search');assert.match(question,/示例公司研发如何/);assert.match(question,/研发/);return [{url:source.url,site:'zhihu',title:'原页',status:'search_hint_only'}];},readPage:async()=>{actions.push('read');return source;},readJob:async()=>{throw Error('unexpected job read');},readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>{executions.push(state);},saveReport:async state=>{reports.push(state);return {...state,report_id:'report_1'};}};
 try{
  const deltas=[];
  const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_12345678',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,value=>deltas.push(value),new AbortController().signal);
  assert.deepEqual(actions,['find','search','read']);
  assert.equal(reports.length,1);assert.equal(reports[0].claims.length,1);
  assert.equal(result.report.report_id,'report_1');assert.match(result.text,/示例公司在上海设立了研发团队/);
  assert.equal(executions.at(-1).status,'complete');assert.equal(deltas.join(''),result.text);
 }finally{server.close();}
});

test('a fabricated final claim is dropped and no report is saved',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});
  turn++;
  const next=turn===1?tool('find_evidence',{},turn):{role:'assistant',content:JSON.stringify({claims:[{quote:'公司已经上市且利润翻倍',evidence_ids:['fake'],category:'listing',scope:'全国'}],limitations:['未取得原文']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let saved=0;const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>[],readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>{saved++;return null;}};
 try{
  const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_abcdefgh',question:'公司上市吗',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(saved,0);assert.equal(result.report,undefined);assert.match(result.text,/没有生成事实性结论/);assert.equal(executions.at(-1).status,'complete');
 }finally{server.close();}
});

test('ordinary follow-up stays a conversation without research tools or report',async()=>{
 const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});
  sse(response,{role:'assistant',content:'还需要你说明想了解哪个团队。'},'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const invoked=[];
 const unexpected=async()=>{invoked.push('research');throw Error('ordinary chat called a research tool');};
 const tools={findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveExecution:unexpected,saveReport:unexpected};
 try{
  const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_followup',question:'那这个团队呢？',company:'示例公司',history:[{role:'user',text:'示例公司的团队如何？'},{role:'assistant',text:'请说明想了解哪个团队。'}],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.match(result.text,/哪个团队/);assert.equal(result.report,undefined);assert.deepEqual(invoked,[]);
 }finally{server.close();}
});

test('retrieved evidence survives a later model failure without a verified answer',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{
  turn++;
  if(turn>1){response.writeHead(500);response.end('mock model failed');return;}
  response.writeHead(200,{'Content-Type':'text/event-stream'});sse(response,tool('find_evidence',{},1),'tool_calls');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];let saved=0;
 const tools={findEvidence:async()=>[source],searchWeb:async()=>[],readPage:async()=>source,readJob:async()=>null,readBrowserPage:async()=>source,saveExecution:async state=>executions.push(state),saveReport:async()=>{saved++;return null;}};
 try{
  await assert.rejects(runPiResearchAgent({workspaceId:'w1',sessionId:'session-a',requestId:'req_failure',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal));
  assert.equal(saved,0);assert.equal(executions.at(-1).status,'failed');
  assert.equal(executions.at(-1).evidence.length,1);
  assert.equal(executions.at(-1).context.evidence_status,'originals_retrieved');
  assert.equal(executions.at(-1).context.answer_status,'none');
  assert.equal(executions.at(-1).conversation_id,'session-a');
 }finally{server.close();}
});

test('fabricated citation to an otherwise readable page cannot save a report',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'zhihu',question:'研发'},turn):turn===3?tool('read_page',{site:'zhihu',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:['ev_fabricated'],category:'business',scope:'上海'}]})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let saved=0;const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:source.url,site:'zhihu',title:'原页',status:'search_hint_only'}],readPage:async()=>({...source,evidence_id:'ev_fabricated'}),readJob:async()=>null,readBrowserPage:async()=>source,saveExecution:async()=>{},saveReport:async()=>{saved++;return null;}};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_fabricated',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.equal(saved,0);assert.equal(result.report,undefined);}
 finally{server.close();}
});
