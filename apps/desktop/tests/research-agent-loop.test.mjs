import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {explainResearchGap,modelHistoryWithinBudget,researchBudgetFor,jobSourceStatus,runPiResearchAgent} from '../dist-electron/main/research/pi-research-agent.mjs';

function sse(response,delta,reason){
 response.write(`data: ${JSON.stringify({id:'chatcmpl-mock',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta,finish_reason:null}]})}\n\n`);
 response.write(`data: ${JSON.stringify({id:'chatcmpl-mock',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta:{},finish_reason:reason}]})}\n\n`);
 response.end('data: [DONE]\n\n');
}
function tool(name,args,number){return {role:'assistant',tool_calls:[{index:0,id:`call_${number}`,type:'function',function:{name,arguments:JSON.stringify(args)}}]};}
const source={evidence_id:'ev_real',url:'https://www.zhihu.com/p/123',platform:'知乎',published_at:null,retrieved_at:'2026-09-25T00:00:00+00:00',company:'示例公司',team:null,excerpt:'示例公司在上海设立了研发团队，并介绍了产品方向。',evidence_kind:'public_source',verification_status:'independently_retrieved',relevance:'company',limitations:'个人陈述，法律主体未核实',context:{source_type:'personal_account',research_topic:'company'},status:'read_original'};
source.evidence_id='ev_'+createHash('sha256').update(`${source.url}\0${source.excerpt}`).digest('hex').slice(0,24);
test('simple and comprehensive questions receive distinct bounded budgets',()=>{
 const simple=researchBudgetFor('示例公司上市了吗');
 const comprehensive=researchBudgetFor('全面研究示例公司的经营、福利和岗位发展');
 assert(simple.searches<comprehensive.searches);
 assert(simple.reads<comprehensive.reads);
 assert(simple.milliseconds<comprehensive.milliseconds);
});
test('saved job liveness never becomes a current-open claim',()=>{
 const now='2026-09-25T10:00:00Z';
 const job=value=>({apply_url:'https://careers.example.org/job/1',source:{liveness:value,fetched_at:'2026-09-25T09:00:00Z'}});
 assert.equal(jobSourceStatus(job('closed'),now),'closed');
 assert.equal(jobSourceStatus(job('stale'),now),'expired');
 assert.equal(jobSourceStatus(job('unknown'),now),'unknown');
 assert.equal(jobSourceStatus(job('active'),now),'recently_observed');
 assert.equal(jobSourceStatus({...job('active'),source:{liveness:'active',fetched_at:'2026-09-22T09:00:00Z'}},now),'expired');
});
test('fixed synthetic job sample counts no unverified vacancy as currently valid',()=>{
 const fixture=JSON.parse(readFileSync(new URL('../../../tests/fixtures/research_eval_cases.json',import.meta.url),'utf8'));
 const now='2026-09-25T10:00:00Z';
 for(const item of fixture.jobs){assert.equal(jobSourceStatus({source:{liveness:item.liveness,fetched_at:item.fetched_at}},now),item.expected_status,item.id);assert.equal(item.currently_valid,'unverified',item.id);}
 assert.equal(fixture.jobs.filter(item=>item.currently_valid==='verified_open').length,0);
});
test('model context budget leaves the full 15 round history intact',()=>{
 const full=Array.from({length:30},(_,index)=>({role:index%2?'assistant':'user',text:`turn ${index} `+'x'.repeat(1000)}));
 const model=modelHistoryWithinBudget(full,12000);
 assert.equal(full.length,30);assert(model.length<full.length);assert.equal(model.at(-1).text,full.at(-1).text);
 assert(model.reduce((sum,turn)=>sum+turn.text.length,0)<=12000);
});
test('search tool passes the full 700 character question and a separate search query',async()=>{
 const question='问'.repeat(700);let turn=0;const seen=[];
 const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'zhihu',question},turn):{role:'assistant',content:JSON.stringify({claims:[],limitations:['无原页']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async(_company,searchQuery,_site,originalQuestion)=>{seen.push({searchQuery,originalQuestion});return [];},readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>null};
 try{
  await runPiResearchAgent({workspaceId:'w1',requestId:'req_700chars',question,company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(seen,[{searchQuery:question,originalQuestion:question}]);
 }finally{server.close();}
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
 const tools={findEvidence:async()=>{actions.push('find');return [];},searchWeb:async(_company,searchQuery,_site,originalQuestion)=>{actions.push('search');assert.equal(searchQuery,'研发');assert.equal(originalQuestion,'示例公司研发如何');return [{url:source.url,site:'zhihu',title:'原页',status:'search_hint_only'}];},readPage:async()=>{actions.push('read');return source;},readJob:async()=>{throw Error('unexpected job read');},readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>{executions.push(state);},saveReport:async state=>{reports.push(state);return {...state,report_id:'report_1'};}};
 try{
  const deltas=[];
  const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_12345678',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,value=>deltas.push(value),new AbortController().signal);
  assert.deepEqual(actions,['find','search','read']);
  assert.equal(reports.length,1);assert.equal(reports[0].claims.length,1);
  assert.equal(result.report.report_id,'report_1');assert.match(result.text,/示例公司在上海设立了研发团队/);
  assert.equal(executions.at(-1).status,'complete');assert.equal(deltas.join(''),result.text);
 }finally{server.close();}
});
test('empty official discovery can replan through public web and cite the read original',async()=>{
 let turn=0;const webSource={...source,url:'https://example.org/company/story',platform:'公开网页',context:{source_type:'public_web',research_topic:'company'}};
 webSource.evidence_id='ev_'+createHash('sha256').update(`${webSource.url}\0${webSource.excerpt}`).digest('hex').slice(0,24);
 const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'研发团队 官方披露'},turn):turn===3?tool('search_web',{site:'web',question:'研发团队 公开资料'},turn):turn===4?tool('read_page',{site:'web',url:webSource.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[webSource.evidence_id],category:'business',scope:'上海'}]})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const searches=[],executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async(_company,query,site)=>{searches.push({query,site});return site==='cninfo'?[]:[{url:webSource.url,site:'web',title:'原页',status:'search_hint_only'}];},readPage:async()=>webSource,readJob:async()=>null,readBrowserPage:async()=>{throw Error('public web browser fallback is disallowed');},saveExecution:async state=>executions.push(state),saveReport:async()=>({report_id:'report_web'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_fallback',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(searches.map(item=>item.site),['cninfo','web']);assert.notEqual(searches[0].query,searches[1].query);
  assert.equal(executions.at(-1).status,'complete');assert.equal(executions.at(-1).budgets.searches,2);assert(executions.at(-1).budgets.model_turns<=7);assert(executions.at(-1).budgets.seconds<75);assert.equal(result.report.report_id,'report_web');
 }finally{server.close();}
});

test('discovery provider error is recorded separately from no results',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'研发'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];const tools={findEvidence:async()=>[],searchWeb:async()=>{throw Error('mock search outage');},readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_search_error',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(executions.at(-1).status,'search_service_error');assert.equal(executions.at(-1).actions.at(-1).status,'search_service_error');
  assert.match(result.text,/不能把它当作没有结果/);
 }finally{server.close();}
});
test('search outage stops the shared provider while a known original remains readable',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'经营'},turn):turn===3?tool('search_web',{site:'web',question:'经营 改写'},turn):turn===4?tool('read_page',{site:'web',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let searches=0,reads=0;const executions=[];
 const tools={findEvidence:async()=>[source],searchWeb:async()=>{searches++;throw Error('mock provider outage');},readPage:async()=>{reads++;return source;},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>({report_id:'known_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_direct_after_outage',question:'示例公司经营情况',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,1);assert.equal(reads,1);assert.equal(result.report.report_id,'known_1');assert(executions.at(-1).actions.some(item=>item.tool==='read_page'&&item.origin==='known_url'));
 }finally{server.close();}
});
test('a blocked public host does not block another discovered host',async()=>{
 const blocked='https://blocked.example.org/a';const available={...source,url:'https://available.example.org/b',platform:'公开网页'};
 available.evidence_id='ev_'+createHash('sha256').update(`${available.url}\0${available.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):turn===3?tool('read_page',{site:'web',url:blocked},turn):turn===4?tool('read_page',{site:'web',url:available.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[available.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const reads=[];const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:blocked,site:'web',title:'受限',status:'search_hint_only'},{url:available.url,site:'web',title:'可读',status:'search_hint_only'}],readPage:async(_company,_site,url)=>{reads.push(url);return url===blocked?{status:'rate_limited',url}:available;},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>({report_id:'host_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_host_limit',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.deepEqual(reads,[blocked,available.url]);assert.equal(result.report.report_id,'host_1');}finally{server.close();}
});
test('saved job URL can be read directly and its liveness is qualified',async()=>{
 const jobUrl='https://careers.example.org/jobs/42';const original={...source,url:jobUrl,platform:'招聘原页'};
 original.evidence_id='ev_'+createHash('sha256').update(`${original.url}\0${original.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('read_job',{},turn):turn===3?tool('read_page',{site:'web',url:jobUrl},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[original.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];const tools={findEvidence:async()=>[],searchWeb:async()=>{throw Error('search should not run');},readPage:async()=>original,readJob:async()=>({apply_url:jobUrl,source:{liveness:'closed',fetched_at:'2026-09-25T00:00:00Z'}}),readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>({report_id:'job_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_job_direct',jobId:'job-42',question:'示例公司岗位怎么样',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.match(result.text,/标记为关闭/);assert(executions.at(-1).actions.some(item=>item.tool==='read_page'&&item.origin==='known_url'));}finally{server.close();}
});

test('cancelling a run aborts an in-flight source request',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const controller=new AbortController();let aborted=false;const tools={findEvidence:async()=>[],searchWeb:async(_company,_query,_site,_original,signal)=>new Promise((_resolve,reject)=>{signal.addEventListener('abort',()=>{aborted=true;reject(Error('aborted'));},{once:true});setTimeout(()=>controller.abort(),10);}),readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>null};
 try{await assert.rejects(runPiResearchAgent({workspaceId:'w1',requestId:'req_cancel_fetch',question:'示例公司研发如何',company:'示例公司',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},controller.signal));assert.equal(aborted,true);}finally{server.close();}
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
  assert.equal(saved,0);assert.equal(result.report,undefined);assert.match(result.text,/只检查了已保存的材料/);assert.match(result.text,/没有发起网页检索/);assert.equal(executions.at(-1).status,'unsupported_claim');
 }finally{server.close();}
});

test('no-evidence answer states what was attempted and offers a next step',()=>{
 assert.match(explainResearchGap(0,[{tool:'find_evidence'}],[]),/没有发起网页检索/);
 assert.match(explainResearchGap(0,[{tool:'search_web'},{tool:'read_page',status:'read_failed'}],['read failed']),/原页读取失败/);
 assert.match(explainResearchGap(0,[{tool:'search_web',status:'search_service_error'}],['outage']),/检索服务未能完成/);
 assert.match(explainResearchGap(0,[{tool:'search_web'},{tool:'read_page',status:'entity_mismatch'}],[]),/主体/);
 assert.match(explainResearchGap(0,[{tool:'find_evidence'},{tool:'read_page',status:'no_text_layer'}],[]),/没有可提取的文字层/);
 assert.match(explainResearchGap(1,[{tool:'find_evidence'}],[]),/不足以支持|没有足够依据/);
 assert.match(explainResearchGap(0,[],[]),/找工作/);
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
