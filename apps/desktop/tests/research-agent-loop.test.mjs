import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {explainResearchGap,modelHistoryWithinBudget,researchBudgetFor,jobSourceStatus,runPiResearchAgent} from '../dist-electron/main/research/pi-research-agent.mjs';
import {beginChat,finishChat,toStoredResearchChat,fromStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';

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
  await runPiResearchAgent({workspaceId:'w1',requestId:'req_700chars',question,company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(seen,[{searchQuery:question,originalQuestion:question}]);
 }finally{server.close();}
});
for(const skillId of [undefined,'deep-research'])test(`Pi ${skillId||'default'} uses bounded tools and saves only a verified quote`,async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});
  turn++;
  const step=turn-(skillId?1:0);const next=skillId&&turn===1?tool('read_skill',{skill_id:skillId},turn):step===1?tool('find_evidence',{},turn):step===2?tool('search_web',{site:'zhihu',question:'研发'},turn):step===3?tool('read_page',{site:'zhihu',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}],limitations:['法律主体未核实']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port,actions=[],executions=[],reports=[];
 const tools={findEvidence:async()=>{actions.push('find');return [];},searchWeb:async(_company,searchQuery,_site,originalQuestion)=>{actions.push('search');assert.equal(searchQuery,'研发');assert.equal(originalQuestion,'示例公司研发如何');return [{url:source.url,site:'zhihu',title:'原页',status:'search_hint_only'}];},readPage:async()=>{actions.push('read');return source;},readJob:async()=>{throw Error('unexpected job read');},readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>{executions.push(state);},saveReport:async state=>{reports.push(state);return {...state,report_id:'report_1'};}};
 try{
  const deltas=[],progress=[];
  const result=await runPiResearchAgent({skillId,workspaceId:'w1',requestId:'req_12345678',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,value=>deltas.push(value),new AbortController().signal,value=>progress.push(value));
  assert.deepEqual(actions,['find','search','read']);
  assert.equal(reports.length,1);assert.equal(reports[0].claims.length,1);
  assert.equal(result.report.report_id,'report_1');assert.match(result.text,/示例公司在上海设立了研发团队/);
  assert.equal(executions.at(-1).status,'complete');assert.equal(deltas.join(''),result.text);
  assert.deepEqual(progress.map(item=>`${item.tool}:${item.status}`),['find_evidence:started','find_evidence:completed','search_web:started','search_web:completed','read_page:started','read_page:completed']);
  assert.deepEqual(result.process.map(item=>item.tool),['find_evidence','search_web','read_page']);
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
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_fallback',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(searches.map(item=>item.site),['cninfo','web']);assert.notEqual(searches[0].query,searches[1].query);
  assert.equal(executions.at(-1).status,'complete');assert.equal(executions.at(-1).budgets.searches,2);assert(executions.at(-1).budgets.model_turns<=7);assert(executions.at(-1).budgets.seconds<75);assert.equal(result.report.report_id,'report_web');
 }finally{server.close();}
});

test('repeated discovery queries and URLs do not spend another search or read',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'示例公司 研发'},turn):turn===3?tool('search_web',{site:'web',question:'  示例公司   研发  '},turn):turn===4?tool('read_page',{site:'web',url:source.url},turn):turn===5?tool('read_page',{site:'web',url:source.url+'#duplicate'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let searches=0,reads=0;const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>{searches++;return [{url:source.url,site:'web',title:'原页',status:'search_hint_only'}];},readPage:async()=>{reads++;return source;},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_dedupe',question:'全面研究示例公司研发',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,1);assert.equal(reads,1);assert(executions.at(-1).actions.some(item=>item.status==='duplicate_query'));assert(executions.at(-1).actions.some(item=>item.status==='duplicate_url'));}
 finally{server.close();}
});

test('two searches with no new URLs stop further discovery without claiming an outage',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'示例公司 经营'},turn):turn===3?tool('search_web',{site:'web',question:'示例公司 经营'},turn):turn===4?tool('search_web',{site:'zhihu',question:'示例公司 经营'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let searches=0;const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>{searches++;return [];},readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_no_new',question:'全面研究示例公司的经营与岗位发展',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,2);assert(executions.at(-1).actions.some(item=>item.status==='no_new_information'));assert.equal(executions.at(-1).status,'no_results');assert(executions.at(-1).budgets.model_turns<=4);assert.match(result.text,/没有新增/);}
 finally{server.close();}
});

test('identical original text at another URL is retained only once',async()=>{
 const second={...source,url:'https://second.example.org/research'};
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'示例公司 研发'},turn):turn===3?tool('read_page',{site:'web',url:source.url},turn):turn===4?tool('read_page',{site:'web',url:second.url},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:source.url,site:'web',title:'一',status:'search_hint_only'},{url:second.url,site:'web',title:'二',status:'search_hint_only'}],readPage:async(_company,_site,url)=>url===source.url?source:{...second,evidence_id:'ev_second',status:'read_original'},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_same_text',question:'全面研究示例公司研发',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(executions.at(-1).evidence.length,1);assert(executions.at(-1).actions.some(item=>item.status==='duplicate_content'));}
 finally{server.close();}
});

test('duplicate search candidates differ from a genuine empty result',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'示例公司 研发'},turn):turn===3?tool('search_web',{site:'web',question:'示例公司 研发团队'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:source.url,site:'web',title:'同一原页',status:'search_hint_only'}],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_candidates',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  const searches=executions.at(-1).actions.filter(item=>item.tool==='search_web');assert.deepEqual(searches.map(item=>item.status),['candidates','no_new_information']);}
 finally{server.close();}
});

test('reposted identical text is not independent evidence despite changed publication metadata',async()=>{
 const other={...source,evidence_id:'ev_other',url:'https://another.example.org/2025/report',published_at:'2025-01-01',context:{...source.context,region:'北京'}};
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const executions=[];
 const tools={findEvidence:async()=>[source,other],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_scope',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(executions.at(-1).evidence.length,1);}
 finally{server.close();}
});

test('cached company evidence covers one direction while Pi reads a new job direction',async()=>{
 const role={...source,url:'https://careers.example.org/jobs/research',platform:'公司招聘页',excerpt:'示例公司招聘研发工程师，岗位地点为上海。',context:{source_type:'public_web',research_topic:'role'},status:'read_original'};
 role.evidence_id='ev_'+createHash('sha256').update(`${role.url}\0${role.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'示例公司 研发岗位'},turn):turn===3?tool('read_page',{site:'web',url:role.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'},{statement:'示例公司招聘研发工程师',quote:'示例公司招聘研发工程师',evidence_ids:[role.evidence_id],category:'role',scope:'团队、地区或法律主体未核实'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const searches=[],reports=[];
 const tools={findEvidence:async()=>[source],searchWeb:async(_company,query)=>{searches.push(query);return [{url:role.url,site:'web',title:'岗位',status:'search_hint_only'}];},readPage:async()=>role,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async state=>{reports.push(state);return {...state,report_id:'mixed_1'};}};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_mixed',question:'全面研究示例公司经营与研发岗位',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(searches,['示例公司 研发岗位']);assert.equal(reports[0].claims.length,2);assert.equal(result.report.report_id,'mixed_1');}
 finally{server.close();}
});

test('sufficient cached evidence lets Pi finish without another search',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let searched=false;
 const tools={findEvidence:async()=>[source],searchWeb:async()=>{searched=true;return [];},readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async state=>({...state,report_id:'cached_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_cached',question:'示例公司的研发团队如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searched,false);assert.equal(result.report.report_id,'cached_1');}
 finally{server.close();}
});

test('repeating the cached-evidence tool returns the cached rows',async()=>{
 let turn=0,finds=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn<=2?tool('find_evidence',{},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const executions=[];
 const tools={findEvidence:async()=>{finds++;return [source];},searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async state=>({...state,report_id:'cached_again'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_cached_again',question:'示例公司的研发团队如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(finds,1);assert.equal(executions.at(-1).evidence.length,1);assert.equal(result.report.report_id,'cached_again');}
 finally{server.close();}
});

test('discovery provider error is recorded separately from no results',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'研发'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];const tools={findEvidence:async()=>[],searchWeb:async()=>{throw Error('mock search outage');},readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_search_error',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(executions.at(-1).status,'search_service_error');assert.equal(executions.at(-1).actions.at(-1).status,'search_service_error');
  assert.match(result.text,/不能把它当作没有结果/);
 }finally{server.close();}
});
test('search outage allows another channel while a known original remains readable',async()=>{
 const official={...source,context:{source_type:'official_disclosure',research_topic:'company'},platform:'官方披露'};
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'cninfo',question:'经营'},turn):turn===3?tool('search_web',{site:'web',question:'经营 改写'},turn):turn===4?tool('read_page',{site:'web',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let searches=0,reads=0;const executions=[];
 const tools={findEvidence:async()=>[official],searchWeb:async()=>{searches++;throw Error('mock provider outage');},readPage:async()=>{reads++;return official;},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>({report_id:'known_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_direct_after_outage',question:'示例公司经营情况',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,2);assert.equal(reads,1);assert.equal(result.report.report_id,'known_1');assert(executions.at(-1).actions.some(item=>item.tool==='read_page'&&item.origin==='known_url'));assert(executions.at(-1).actions.some(item=>item.tool==='find_evidence'&&item.official_known_urls===1));
 }finally{server.close();}
});
test('a blocked public host does not block another discovered host',async()=>{
 const blocked='https://blocked.example.org/a';const available={...source,url:'https://available.example.org/b',platform:'公开网页'};
 available.evidence_id='ev_'+createHash('sha256').update(`${available.url}\0${available.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):turn===3?tool('read_page',{site:'web',url:blocked},turn):turn===4?tool('read_page',{site:'web',url:available.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[available.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const reads=[];const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:blocked,site:'web',title:'受限',status:'search_hint_only'},{url:available.url,site:'web',title:'可读',status:'search_hint_only'}],readPage:async(_company,_site,url)=>{reads.push(url);return url===blocked?{status:'rate_limited',url}:available;},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>({report_id:'host_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_host_limit',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.deepEqual(reads,[blocked,available.url]);assert.equal(result.report.report_id,'host_1');}finally{server.close();}
});
test('saved job URL can be read directly and its liveness is qualified',async()=>{
 const jobUrl='https://careers.example.org/jobs/42';const original={...source,url:jobUrl,platform:'招聘原页'};
 original.evidence_id='ev_'+createHash('sha256').update(`${original.url}\0${original.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('read_job',{},turn):turn===3?tool('read_page',{site:'web',url:jobUrl},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[original.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];const tools={findEvidence:async()=>[],searchWeb:async()=>{throw Error('search should not run');},readPage:async()=>original,readJob:async()=>({apply_url:jobUrl,source:{liveness:'closed',fetched_at:'2026-09-25T00:00:00Z'}}),readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>({report_id:'job_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_job_direct',jobId:'job-42',question:'示例公司岗位怎么样',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.match(result.text,/标记为关闭/);assert(executions.at(-1).actions.some(item=>item.tool==='read_page'&&item.origin==='known_url'));}finally{server.close();}
});

test('cancelling a run aborts an in-flight source request',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const controller=new AbortController();let aborted=false;const tools={findEvidence:async()=>[],searchWeb:async(_company,_query,_site,_original,signal)=>new Promise((_resolve,reject)=>{signal.addEventListener('abort',()=>{aborted=true;reject(Error('aborted'));},{once:true});setTimeout(()=>controller.abort(),10);}),readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>null};
 try{await assert.rejects(runPiResearchAgent({workspaceId:'w1',requestId:'req_cancel_fetch',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},controller.signal));assert.equal(aborted,true);}finally{server.close();}
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
  const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_abcdefgh',question:'公司上市吗',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(saved,0);assert.equal(result.report,undefined);assert.match(result.text,/尝试了公开来源检索/);assert.ok(executions.at(-1).actions.some(action=>action.tool==='search_web'));assert.equal(executions.at(-1).status,'unsupported_claim');
 }finally{server.close();}
});

test('mock interview repairs a recorded next question that was never asked',async()=>{
 let turn=0;const executions=[];
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('remember_interview',{asked:['第一题','第二题'],weaknesses:['异常记录验证未说明'],follow_up_reason:'核对细节',current_question:'你怎样确认异常记录没有被误删？'},turn):{role:'assistant',content:turn===2?'已记录，等你回答第二题。':'你说明了将异常记录单独输出，这一点具体。还缺少核对方法。你怎样确认异常记录没有被误删？'};
  sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w1',requestId:'req_interview_repair',question:'我用 pandas 处理了缺失值，异常记录单独输出。',history:[],research:false},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.match(result.text,/异常记录没有被误删？/);assert(executions.at(-1).actions.some(item=>item.reason==='interview_question_missing'));
 }finally{server.close();}
});

test('mock interview repairs a follow-up question without feedback on the candidate answer',async()=>{
 let turn=0;const executions=[];
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('remember_interview',{asked:['第一题','第二题'],weaknesses:['退款规则未说明'],follow_up_reason:'异常金额核对',current_question:'你怎样区分正常退款与数据错误？'},turn):{role:'assistant',content:turn===2?'你怎样区分正常退款与数据错误？':'你说清了用脚本筛出负数金额，这一点有效；但没有说明如何避免把退款当成错误。你怎样区分正常退款与数据错误？'};
  sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w1',requestId:'req_interview_feedback_repair',question:'我筛出了负数金额，发现其中一部分是退款。',history:[{role:'assistant',text:'请说说你如何核对异常金额？'}],research:false},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.match(result.text,/但没有说明如何避免把退款当成错误/);assert(executions.at(-1).actions.some(item=>item.reason==='interview_feedback_missing'));
 }finally{server.close();}
});

test('resume skill can read an unsaved local job named by the user',async()=>{
 let turn=0;const executions=[];
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_local_jobs',{title:'AI软件开发工程师'},turn):turn===2?tool('read_job',{job_id:'local-1'},turn):{role:'assistant',content:'本地找到目标岗位，但详情尚未读取；请提供简历和完整 JD，收到后我会先给可审阅草稿。'};
  sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findLocalJobs:async title=>{assert.equal(title,'AI软件开发工程师');return [{job_id:'local-1',title,company:'示例研究所',has_description:false}];},findEvidence:async()=>[],searchWeb:async()=>[],readPage:async()=>null,readJob:async id=>{assert.equal(id,'local-1');return {job_id:id,title:'AI软件开发工程师',company:'示例研究所',description:'岗位详情暂未读取'};},readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({skillId:'resume-tailor',workspaceId:'w1',requestId:'req_resume_local_job',question:'请结合示例研究所的「AI软件开发工程师」岗位修改简历。',history:[],research:false},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.match(result.text,/详情尚未读取/);assert(executions.at(-1).actions.some(item=>item.tool==='find_local_jobs'&&item.count===1));assert(executions.at(-1).actions.some(item=>item.tool==='read_job'&&item.job_id==='local-1'));
 }finally{server.close();}
});

test('deep research may read a bounded path on a discovered public origin',async()=>{
 const home='https://www.python.org/';const about='https://www.python.org/about/';const quote='Python is powerful and fast.';
 const original={...source,url:about,company:'',excerpt:quote,context:{source_type:'public_web',research_topic:'Python'},status:'read_original'};
 original.evidence_id='ev_'+createHash('sha256').update(`${about}\0${quote}`).digest('hex').slice(0,24);
 let turn=0;const reads=[],executions=[];
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('search_web',{site:'web',question:'Python official'},turn):turn===2?tool('read_page',{site:'web',url:about},turn):{role:'assistant',content:`官网原文描述 Python 为 powerful and fast [${original.evidence_id}]。`};
  sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:home,site:'web',title:'Python.org',status:'search_hint_only'}],readPage:async(_company,_site,url)=>{reads.push(url);return original;},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w1',requestId:'req_same_host',question:'研究 Python 官方定位',history:[],research:true},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(reads,[about]);assert.match(result.text,/\[1\]/);assert(executions.at(-1).actions.some(item=>item.origin==='same_host'));
 }finally{server.close();}
});

for(const readSite of [undefined,'web','papers'])test(`paper retrieval carries discovery site into ${readSite||'default'} reads, with workflow loading and a bounded origin`,async()=>{
 const abs='https://arxiv.org/abs/1234.56789',pdf='https://arxiv.org/pdf/1234.56789';
 const quote='This synthetic paper describes retrieval evaluation.';
 const original={...source,url:pdf,company:'',excerpt:quote,context:{source_type:'public_web',research_topic:'retrieval'},status:'read_original'};
 original.evidence_id='ev_'+createHash('sha256').update(`${pdf}\0${quote}`).digest('hex').slice(0,24);
 let turn=0,searches=0;const reads=[],executions=[];
 const server=http.createServer((request,response)=>{let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
  const messages=JSON.parse(body).messages;
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  if(turn===2){assert(messages.some(item=>item.role==='tool'&&item.content.includes('skill_loaded')));assert.equal(searches,0);}
  const next=turn<=2?tool('search_web',{site:'papers',query:'retrieval evaluation'},turn):turn===3?tool('read_page',{site:readSite,url:'https://another.example.org/pdf/1234.56789'},turn):turn===4?tool('read_page',{site:readSite,url:pdf},turn):{role:'assistant',content:`原文讨论检索评估 [${original.evidence_id}]。`};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async()=>{searches++;return [{url:abs,site:'papers',title:'Paper',status:'search_hint_only'}];},readPage:async(_company,site,url)=>{assert.equal(site,'papers');reads.push(url);return original;},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_paper_skill',question:'解释检证评估的方法',history:[],research:false},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,1);assert.deepEqual(reads,[pdf]);assert.match(result.text,/\[1\]/);
  const actions=executions.at(-1).actions;
  assert.equal(actions.filter(item=>item.tool==='read_skill'&&item.skill_id==='web-retrieval').length,1);
  assert(actions.some(item=>item.tool==='read_page'&&item.site==='papers'&&item.origin==='same_host'));
 }finally{server.close();}
});

test('retrieval reserves its last model turn for a cited answer without expanding tools or budget',async()=>{
 const original={...source,company:'',context:{source_type:'public_web'},status:'read_original'};
 let turn=0;const executions=[],requests=[];
 const server=http.createServer((request,response)=>{let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
  const input=JSON.parse(body);requests.push(input);response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('search_web',{site:'web',query:'public architecture'},turn):turn===2?tool('read_page',{url:source.url},turn):turn<=4?tool('retrieval_status',{},turn):{role:'assistant',content:`公开原文介绍研发团队 (${source.evidence_id})。`};sse(response,next,next.tool_calls?'tool_calls':'stop');
 });});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={retrievalStatus:()=>({status:'candidates'}),findEvidence:async()=>[],searchWeb:async()=>[{url:source.url,site:'web',title:'Original',status:'search_hint_only'}],readPage:async()=>original,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_answer_reserve',question:'检索公开架构资料',history:[],research:false},
  {protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(turn,5);assert.equal(requests.at(-1).tools?.length||0,0,JSON.stringify(executions.at(-1).actions));assert(requests.at(-1).messages.some(item=>item.role==='user'&&item.content.includes('最后一轮交付')));assert.match(result.text,/\[1\]/);assert.equal(executions.at(-1).status,'complete');assert.equal(executions.at(-1).budgets.max_turns,5);assert.equal(executions.at(-1).budgets.model_turns,5);
  assert(executions.at(-1).actions.some(item=>item.status==='answer_reserved'));
 }finally{server.close();}
});

test('no-evidence answer states what was attempted and offers a next step',()=>{
 assert.match(explainResearchGap(0,[{tool:'find_evidence'}],[]),/没有发起网页检索/);
 assert.match(explainResearchGap(0,[{tool:'search_web'},{tool:'read_page',status:'read_failed'}],['read failed']),/原页读取失败/);
 assert.match(explainResearchGap(0,[{tool:'search_web',status:'search_service_error'}],['outage']),/检索服务未能完成/);
 assert.match(explainResearchGap(0,[{tool:'search_web',status:'search_service_error',reason_code:'redirect_blocked'}],[]),/跳转被安全策略拦截/);
 assert.match(explainResearchGap(0,[{tool:'search_web',status:'candidates'},{tool:'read_page',status:'read_failed',http_status:503}],[]),/HTTP 503/);
 const mixed=explainResearchGap(0,[{tool:'search_web',status:'candidates'},{tool:'read_page',status:'restricted'},{tool:'read_page',status:'entity_mismatch'}],[],'查找星宇股份，看看怎么样');
 assert.match(mixed,/主体不符/);assert.match(mixed,/部分|另有/);assert.doesNotMatch(mixed,/这次来源要求验证或触发限流/);
 assert.match(explainResearchGap(0,[{tool:'search_web'},{tool:'read_page',status:'entity_mismatch'}],[]),/主体/);
 assert.match(explainResearchGap(0,[{tool:'find_evidence'},{tool:'read_page',status:'no_text_layer'}],[]),/没有可提取的文字层/);
 assert.match(explainResearchGap(1,[{tool:'find_evidence'}],[]),/不足以支持|没有足够依据/);
 assert.match(explainResearchGap(0,[],[],'想找工作'),/找工作/);
 const businessGap=explainResearchGap(0,[{tool:'search_web',status:'no_results'}],[],'腾讯经营与披露情况');
 assert.match(businessGap,/财报年份或报告期/);assert.doesNotMatch(businessGap,/找工作/);
});

test('a connection port ending in 403 is a service failure, not source restriction',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'示例公司'},turn):{role:'assistant',content:JSON.stringify({claims:[]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const executions=[];const tools={findEvidence:async()=>[],searchWeb:async()=>{throw Error('connect ECONNREFUSED 127.0.0.1:1403');},readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async state=>executions.push(state),saveReport:async()=>null};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_port_1403',question:'示例公司怎么样',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(executions.at(-1).actions.find(item=>item.tool==='search_web')?.status,'search_service_error');assert.match(result.text,/检索服务未能完成/);
 }finally{server.close();}
});

test('official index candidate from hkex search is read as official web original',async()=>{
 const official={...source,url:'https://static.www.tencent.com/uploads/2026/03/18/example.pdf',platform:'腾讯投资者关系',company:'腾讯',excerpt:'腾讯控股有限公司公布二零二五年度业绩。',context:{source_type:'official_disclosure',research_topic:'company',page:1}};
 official.evidence_id='ev_'+createHash('sha256').update(`${official.url}\0${official.excerpt}`).digest('hex').slice(0,24);
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'hkex',question:'腾讯 经营 披露'},turn):turn===3?tool('read_page',{site:'web',url:official.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'腾讯控股有限公司公布二零二五年度业绩',quote:'腾讯控股有限公司公布二零二五年度业绩',evidence_ids:[official.evidence_id],category:'business',scope:'腾讯控股有限公司二零二五年度'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const reads=[],executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async()=>[{url:official.url,site:'web',title:'业绩新闻',source_type:'official_disclosure',provider:'official_index',status:'search_hint_only'}],readPage:async(_company,site,url)=>{reads.push({site,url});return official;},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async item=>executions.push(item),saveReport:async()=>({report_id:'official_1'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_official',question:'腾讯经营与披露情况',company:'腾讯',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(reads,[{site:'web',url:official.url}]);assert.equal(executions.at(-1).actions.find(item=>item.tool==='search_web').provider,'official_index');assert.equal(result.report.report_id,'official_1');assert.match(result.text,/腾讯控股有限公司公布/);
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
test('ordinary answer streams before completion and stores one final assistant turn',async()=>{
 let turn=0,release,firstChunk;const gate=new Promise(resolve=>{release=resolve;});const sawChunk=new Promise(resolve=>{firstChunk=resolve;});
 const server=http.createServer(async(_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  if(turn===1){sse(response,tool('answer_in_chat',{},turn),'tool_calls');return;}
  response.write(`data: ${JSON.stringify({id:'chatcmpl-mock',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta:{role:'assistant',content:'你好，'},finish_reason:null}]})}\n\n`);
  firstChunk();await gate;sse(response,{role:'assistant',content:'可以直接聊。'},'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const unexpected=async()=>{throw Error('ordinary chat cannot read a source');};const deltas=[];let finished=false;
 try{const work=runPiResearchAgent({workspaceId:'w1',requestId:'req_stream_direct',question:'你好',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveExecution:async()=>{},saveReport:unexpected},delta=>deltas.push(delta),new AbortController().signal).then(value=>{finished=true;return value;});
  await sawChunk;await new Promise(resolve=>setTimeout(resolve,15));assert.equal(finished,false);assert.deepEqual(deltas,['你好，']);
  release();const result=await work;assert.equal(result.text,'你好，可以直接聊。');assert.equal(deltas.join(''),result.text);assert.equal(result.report,undefined);
  const chat=finishChat(beginChat(undefined,'stream-session','你好','2026-01-01').chat,result.text,undefined,'2026-01-01');
  const restored=fromStoredResearchChat({...toStoredResearchChat('w1',chat),updated_at:'2026-01-01'});assert.deepEqual(restored.turns.map(item=>item.text),['你好',result.text]);
 }finally{release();server.close();}
});

test('optional direct-chat marker does not block later source tools',async()=>{
 let turn=0,searches=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  sse(response,turn===1?tool('answer_in_chat',{},turn):turn<=3?tool('search_web',{site:'web',question:'示例公司'},turn):{role:'assistant',content:'继续普通交流。'},turn<=3?'tool_calls':'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async()=>{searches++;return [];},readPage:async()=>{throw Error('unexpected read');},readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async()=>null};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_direct_gate',question:'你好',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.equal(searches,1);}finally{server.close();}
});
test('resume drafting reads only a confirmed redacted copy and creates no research report',async()=>{
 let turn=0,reads=0,researchCalls=0;
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('read_confirmed_resume',{},turn):{role:'assistant',content:'可把已确认的 Python 项目经历写得更具体；这是草稿建议。'};
  sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const unexpected=async()=>{researchCalls++;throw Error('unexpected research call');};
 const tools={readResume:async()=>{reads++;return {source_version_id:'v1',text:'Python 项目 [已过滤:个人信息]',limitations:'脱敏副本'};},findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveExecution:async()=>{},saveReport:unexpected};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_resume_draft',question:'帮我写简历项目描述草稿',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(reads,1);assert.equal(researchCalls,0);assert.equal(result.report,undefined);assert.match(result.text,/草稿建议/);
 }finally{server.close();}
});
test('Pi asks a company scope question without inventing a research failure',async()=>{
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});sse(response,{role:'assistant',content:JSON.stringify({message:'你更关注腾讯的经营、岗位机会，还是工作体验？',claims:[]})},'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const unexpected=async()=>{throw Error('clarification should not call source tools');};
 const tools={findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveExecution:async()=>{},saveReport:unexpected};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_pi_clarify',question:'腾讯怎么样',company:'腾讯',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.equal(result.text,'你更关注腾讯的经营、岗位机会，还是工作体验？');assert.equal(result.report,undefined);}finally{server.close();}
});

test('the same Pi loop can choose research tools from a conversational turn',async()=>{
 let turn=0;const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('select_subject',{company:'示例公司'},turn):turn===2?tool('find_evidence',{},turn):turn===3?tool('search_web',{site:'zhihu',question:'研发'},turn):turn===4?tool('read_page',{site:'zhihu',url:source.url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const invoked=[];const tools={findEvidence:async()=>{invoked.push('find');return [];},searchWeb:async()=>{invoked.push('search');return [{url:source.url,site:'zhihu',title:'原页',status:'search_hint_only'}];},readPage:async()=>{invoked.push('read');return source;},readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async()=>{},saveReport:async()=>({report_id:'pi_unified'})};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_pi_unified',question:'示例公司的研发方向',history:[],research:false,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.deepEqual(invoked,['find','search','read']);assert.equal(result.report.report_id,'pi_unified');assert.equal(result.company,'示例公司');assert.equal(result.researched,true);}finally{server.close();}
});

test('one embedded Pi path continues after a tool outage and a cancelled turn',async()=>{
 let phase='chat',turn=0,modelCalls=0;const phases={chat:()=>({role:'assistant',content:'你好，我可以帮你查公开资料。'}),clarify:()=>({role:'assistant',content:JSON.stringify({message:'你更关注示例公司的经营，还是岗位机会？',claims:[]})}),outage:()=>++turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'经营'},turn):({role:'assistant',content:JSON.stringify({message:'你想先缩小到研发团队吗？',claims:[]})}),followup:()=>({role:'assistant',content:'可以，我们接着看研发团队。'}),cancel:()=>++turn===1?tool('find_evidence',{},turn):tool('search_web',{site:'web',question:'研发'},turn),retry:()=>++turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):turn===3?tool('read_page',{site:'web',url:source.url},turn):({role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})})};
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});modelCalls++;const next=phases[phase]();sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const connection={protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'};
 const history=[];let cancelController;const executions=[];
 const tools={findEvidence:async()=>[],searchWeb:async(_company,_query,site,_original,signal)=>{if(phase==='outage')throw Error('公开检索服务连接失败');if(phase==='cancel')return new Promise((_resolve,reject)=>{signal.addEventListener('abort',()=>reject(Error('cancelled')),{once:true});setTimeout(()=>cancelController.abort(),10);});return [{url:source.url,site,title:'原页',status:'search_hint_only'}];},readPage:async()=>source,readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser read');},saveExecution:async item=>executions.push(item),saveReport:async()=>({report_id:'retry-report'})};
 const ask=async(question,research,controller=new AbortController())=>runPiResearchAgent({workspaceId:'w1',sessionId:'session-1',requestId:`req_${phase}`,question,company:research?'示例公司':undefined,history:[...history],research,reportRequested:true},connection,'',tools,()=>{},controller.signal);
 try{
  let value=await ask('你好',false);assert.match(value.text,/你好/);history.push({role:'user',text:'你好'},{role:'assistant',text:value.text});
  phase='clarify';turn=0;value=await ask('示例公司怎么样',true);assert.match(value.text,/更关注/);assert.equal(value.researched,false);history.push({role:'user',text:'示例公司怎么样'},{role:'assistant',text:value.text});
  phase='outage';turn=0;value=await ask('示例公司经营如何',true);assert.match(value.text,/检索服务未能完成/);assert.match(value.text,/缩小到研发团队/);history.push({role:'user',text:'示例公司经营如何'},{role:'assistant',text:value.text});
  phase='followup';turn=0;value=await ask('那先说怎么继续',false);assert.match(value.text,/接着看研发团队/);history.push({role:'user',text:'那先说怎么继续'},{role:'assistant',text:value.text});
  phase='cancel';turn=0;cancelController=new AbortController();await assert.rejects(ask('示例公司研发方向',true,cancelController));
  phase='retry';turn=0;value=await ask('示例公司研发方向',true);assert.equal(value.report.report_id,'retry-report');assert.match(value.text,/上海设立了研发团队/);assert(modelCalls>=10);assert(executions.some(item=>item.status==='search_service_error'));assert(executions.some(item=>item.status==='complete'));
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
  const result=await runPiResearchAgent({workspaceId:'w1',sessionId:'session-a',requestId:'req_failure',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.match(result.text,/综合分析未完成/);assert.equal(result.report,undefined);
  assert.equal(saved,0);assert.equal(executions.at(-1).status,'read_failed');
  assert.equal(executions.at(-1).evidence.length,1);
  assert.equal(executions.at(-1).context.evidence_status,'originals_retrieved');
  assert.equal(executions.at(-1).context.answer_status,'generated_unsaved');
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
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_fabricated',question:'示例公司研发如何',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.equal(saved,0);assert.equal(result.report,undefined);assert.match(result.text,/已读取 1 份材料/);assert.doesNotMatch(result.text,/示例公司在上海设立了研发团队/);assert.equal(result.evidence?.[0].url,source.url);assert.equal(result.evidence?.[0].excerpt,source.excerpt);}
 finally{server.close();}
});

test('Tencent benefits follow-up recovers from cache-only early final and reads web evidence',async()=>{
 let turn=0;const queries=[];const actions=[];
 const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?{role:'assistant',content:'没有缓存材料，暂时不能回答。'}:{role:'assistant',content:JSON.stringify({claims:[],limitations:['员工个人反馈不能代表全公司']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const tools={findEvidence:async()=>[],searchWeb:async(company,query)=>{queries.push([company,query]);return [{url:'https://example.org/tencent',site:'web',title:'腾讯员工反馈',status:'candidate'}];},readPage:async()=>({...source,url:'https://example.org/tencent',excerpt:'腾讯员工待遇因团队岗位而异',status:'read_original'}),readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async state=>{actions.push(structuredClone(state.actions));},saveReport:async()=>null};
 try{
  await runPiResearchAgent({workspaceId:'w1',requestId:'req_benefits',company:'腾讯',question:'员工待遇',history:[{role:'user',text:'调研下腾讯集团'},{role:'assistant',text:'想了解经营还是员工待遇？'}],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(queries.length,1);assert.equal(queries[0][0],'腾讯');assert.match(queries[0][1],/待遇/);
  assert.ok(actions.at(-1).some(action=>action.tool==='read_page'));
 }finally{server.close();}
});

test('a model ignoring the completion repair is stopped without a report',async()=>{
 let turn=0,saved=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):{role:'assistant',content:'没有材料。'};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  await runPiResearchAgent({workspaceId:'w1',requestId:'req_refuses',company:'腾讯',question:'员工待遇',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>[],searchWeb:async()=>{throw Error('unexpected');},readPage:async()=>null,readBrowserPage:async()=>null,readJob:async()=>null,saveExecution:async()=>{},saveReport:async()=>{saved++;}},()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.equal(saved,0);
 }finally{server.close();}
});

test('explicit research executes bounded acquisition even when the model never calls a tool',async()=>{
 let turn=0;const invoked=[];
 const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  sse(response,{role:'assistant',content:turn===1?'没有材料。':JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'}]})},'stop');
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  const value=await runPiResearchAgent({workspaceId:'w1',requestId:'req_required',company:'示例公司',question:'研究下示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{
   findEvidence:async()=>{invoked.push('cache');return [];},
   searchWeb:async()=>{invoked.push('search');return [{url:source.url,site:'web',title:'原文',status:'candidate'}];},
   readPage:async()=>{invoked.push('read');return source;},
   readJob:async()=>null,readBrowserPage:async()=>{throw Error('unexpected browser');},
   saveExecution:async()=>{},saveReport:async()=>({report_id:'required-report'})
  },()=>{},new AbortController().signal);
  assert.deepEqual(invoked,['cache','search','read']);assert.equal(turn,2);
  assert.equal(value.report.report_id,'required-report');assert.match(value.text,/上海设立了研发团队/);
 }finally{server.close();}
});

test('generic research does not force a fixed acquisition after a model final',async()=>{
 let turn=0,finds=0,searches=0;
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  sse(response,{role:'assistant',content:turn===1?JSON.stringify({message:'你更关注哪个方向？',claims:[]}):JSON.stringify({claims:[],limitations:['当前没有可核对的原文']})},'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_huawei_overview',question:'调研华为',company:'华为',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>{finds++;return [];},searchWeb:async()=>{searches++;return [];},readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async()=>{throw Error('overview must not save a report');}},()=>{},new AbortController().signal);
  assert.equal(finds,0);assert.equal(searches,0);assert.equal(result.text,'你更关注哪个方向？');assert.equal(result.report,undefined);
 }finally{server.close();}
});

test('readable evidence repairs a malformed answer without another search',async()=>{
 let turn=0,searches=0;const server=http.createServer((_request,response)=>{
  response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?tool('search_web',{site:'web',question:'研发'},turn):turn===3?{role:'assistant',content:'公司有研发团队。'}:{role:'assistant',content:JSON.stringify({claims:[{statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business'}]})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  const value=await runPiResearchAgent({workspaceId:'w1',requestId:'req_answer_repair',company:'示例公司',question:'研究示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>[source],searchWeb:async()=>{searches++;return [];},readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async()=>({report_id:'repaired'})},()=>{},new AbortController().signal);
  assert.equal(searches,1);assert.equal(turn,4);assert.equal(value.report.report_id,'repaired');
 }finally{server.close();}
});

test('formal report keeps supported claims and repairs only bad ones',async()=>{
 let turn=0,saved=0;const actions=[];
 const valid={statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'};
 const invalid={statement:'示例公司已在全球上市',quote:'示例公司已在全球上市',evidence_ids:['ev_fake'],category:'listing',scope:'全球'};
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?{role:'assistant',content:JSON.stringify({claims:[valid,invalid]})}:{role:'assistant',content:JSON.stringify({claims:[],limitations:['上市信息没有可核验原文']})};
  sse(response,next,next.tool_calls?'tool_calls':'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_partial_claim',question:'示例公司怎么样',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>[source],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async row=>actions.push(row.actions),saveReport:async()=>{saved++;return null;}},()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.equal(saved,1);assert.equal(result.report,undefined);assert.match(result.text,/示例公司在上海设立了研发团队 \[1\]/);assert.doesNotMatch(result.text,/全球上市/);assert.match(result.text,/尚缺依据/);assert.equal(result.evidence?.[0].evidence_id,source.evidence_id);
  assert(actions.at(-1).some(item=>item.tool==='answer_check'&&item.retained===1&&item.rejected===1));
 }finally{server.close();}
});

test('a repaired claim joins retained claims without a false missing-evidence note',async()=>{
 let turn=0;const first={statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[source.evidence_id],category:'business',scope:'上海'};
 const repaired={statement:'示例公司在上海设立了研发团队，并介绍了产品方向',quote:'示例公司在上海设立了研发团队，并介绍了产品方向',evidence_ids:[source.evidence_id],category:'business',scope:'上海'};
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn===1?tool('find_evidence',{},turn):turn===2?{role:'assistant',content:JSON.stringify({claims:[first,{...repaired,evidence_ids:['ev_fake']}]})}:{role:'assistant',content:JSON.stringify({claims:[repaired]})};sse(response,next,next.tool_calls?'tool_calls':'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_repaired_partial',question:'调研示例公司',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>[source],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async()=>null},()=>{},new AbortController().signal);
  assert.equal(turn,3);assert.match(result.text,/上海设立了研发团队 \[1\]/);assert.match(result.text,/介绍了产品方向 \[1\]/);assert.doesNotMatch(result.text,/尚缺依据/);
 }finally{server.close();}
});

test('a failed correction still returns the previously verified claim',async()=>{
 let turn=0;const sources=Array.from({length:5},(_,index)=>{
  const row={...source,url:`https://www.zhihu.com/p/${index+1}`,excerpt:index===4?source.excerpt:`示例公司资料片段 ${index+1}。`};
  row.evidence_id='ev_'+createHash('sha256').update(`${row.url}\0${row.excerpt}`).digest('hex').slice(0,24);return row;
 });const valid={statement:'示例公司在上海设立了研发团队',quote:'示例公司在上海设立了研发团队',evidence_ids:[sources[4].evidence_id],category:'business',scope:'上海'};
 const server=http.createServer((_request,response)=>{turn++;response.writeHead(turn===3?500:200,{'Content-Type':turn===3?'text/plain':'text/event-stream'});
  if(turn===3){response.end('model unavailable');return;}
  const next=turn===1?tool('find_evidence',{},turn):{role:'assistant',content:JSON.stringify({claims:[valid,{...valid,statement:'示例公司已上市',evidence_ids:['ev_fake']}]})};sse(response,next,next.tool_calls?'tool_calls':'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'req_repair_failure',question:'示例公司怎么样',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>sources,searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveExecution:async()=>{},saveReport:async()=>null},()=>{},new AbortController().signal);
  assert.match(result.text,/示例公司在上海设立了研发团队 \[5\]/);assert.match(result.text,/修复未完成/);assert.equal(result.evidence?.[4].evidence_id,sources[4].evidence_id);
 }finally{server.close();}
});

test('a job-linked research turn analyzes its saved JD with streaming and no public reads or report',async()=>{
 let turn=0,publicReads=0,reports=0,release,firstChunk;const gate=new Promise(resolve=>{release=resolve;});const sawChunk=new Promise(resolve=>{firstChunk=resolve;});const server=http.createServer(async(_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  if(turn<=2){sse(response,turn===1?tool('read_job',{job_id:'job-42'},turn):tool('answer_in_chat',{},turn),'tool_calls');return;}
  response.write(`data: ${JSON.stringify({id:'chatcmpl-jd',object:'chat.completion.chunk',created:1,model:'mock',choices:[{index:0,delta:{role:'assistant',content:'这份 JD 主要写了 Python 开发'},finish_reason:null}]})}\n\n`);
  firstChunk();await gate;sse(response,{role:'assistant',content:'与团队协作；我可以帮你改写简历。'},'stop');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const deltas=[];let finished=false;
 try{const work=runPiResearchAgent({workspaceId:'w1',requestId:'req_jd_local',question:'岗位有坑吗',jobId:'job-42',company:'示例公司',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:async()=>{publicReads++;return [];},searchWeb:async()=>{publicReads++;return [];},readPage:async()=>{publicReads++;return null;},readJob:async()=>({job_id:'job-42',description:'Python 开发，团队协作'}),readBrowserPage:async()=>{publicReads++;return null;},saveExecution:async()=>{},saveReport:async()=>{reports++;return null;}},delta=>deltas.push(delta),new AbortController().signal).then(value=>{finished=true;return value;});
  await sawChunk;await new Promise(resolve=>setTimeout(resolve,15));assert.equal(finished,false);assert.deepEqual(deltas,['这份 JD 主要写了 Python 开发']);
  release();const result=await work;assert.equal(publicReads,0);assert.equal(reports,0);assert.match(result.text,/Python 开发/);assert.equal(deltas.join(''),result.text);assert.equal(result.report,undefined);
 }finally{release();server.close();}
});

for(const skillId of ['resume-tailor','interview-prep'])test(`${skillId} loads its workflow and reads local material without public tools`,async()=>{
 let turn=0;const payloads=[],actions=[],executions=[];
 const server=http.createServer((request,response)=>{
  let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{
   payloads.push(JSON.parse(body));response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
   const next=turn===1?tool('read_skill',{skill_id:skillId},turn):turn===2?tool('read_job',{},turn):turn===3?tool('read_confirmed_resume',{},turn):turn===4?tool('answer_in_chat',{},turn):{role:'assistant',content:skillId==='interview-prep'?'根据你提供的 Python 项目，我们练习一题：你怎样验证 API 返回值？':'根据你的真实 Python 项目，可以准备 API 设计实例。以下是草稿。'};
   sse(response,next,next.tool_calls?'tool_calls':'stop');
  });
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const unexpected=async()=>{throw Error('unexpected public source or report');};
 const tools={readResume:async()=>{actions.push('resume');return {source_version_id:'v1',text:'真实 Python 项目经历',limitations:'脱敏副本'};},readJob:async()=>{actions.push('job');return {title:'Python 工程师',description:'要求 API 开发'};},listSavedJobs:async()=>[],findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readBrowserPage:unexpected,saveReport:unexpected,saveExecution:async state=>executions.push(state)};
 try{
  const result=await runPiResearchAgent({skillId,workspaceId:'w1',requestId:'req_skill_123',jobId:'job_123',question:'请结合目标岗位和我的简历',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.deepEqual(actions,['job','resume']);assert.equal(result.researched,false);assert.match(result.text,skillId==='interview-prep'?/怎样验证 API/:/草稿/);
  const first=payloads[0];assert.match(first.messages.find(item=>item.role==='system').content,skillId==='resume-tailor'?/修改简历/:/模拟面试/);
  assert.ok(first.tools.some(item=>item.function.name==='read_skill'));
  assert.equal(first.tools.some(item=>item.function.name==='search_web'),skillId==='resume-tailor');
  assert.match(JSON.stringify(payloads[1].messages),skillId==='resume-tailor'?/可复制草稿/:/问一道最相关的单一问题/);
  assert.equal(executions[0].context.skill_id,skillId);assert.equal(executions.at(-1).status,'complete');
 }finally{server.close();}
});
test('generic interview questions do not expose public page readers',async()=>{
 let toolsSeen=[];const server=http.createServer((request,response)=>{let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{toolsSeen=JSON.parse(body).tools.map(item=>item.function.name);response.writeHead(200,{'Content-Type':'text/event-stream'});sse(response,{role:'assistant',content:'我们先练项目背景：你负责的项目要解决什么问题？'},'stop');});});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'generic-interview',question:'有哪些问题',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.match(result.text,/项目背景/);for(const name of ['search_web','read_page','read_browser_page','find_evidence'])assert.equal(toolsSeen.includes(name),false);assert.equal(toolsSeen.includes('read_job'),true);}finally{server.close();}
});
test('interview questions with a supplied web link may read public originals',async()=>{
 let toolsSeen=[];const server=http.createServer((request,response)=>{let body='';request.on('data',chunk=>body+=chunk);request.on('end',()=>{toolsSeen=JSON.parse(body).tools.map(item=>item.function.name);response.writeHead(200,{'Content-Type':'text/event-stream'});sse(response,{role:'assistant',content:'围绕提供的岗位要求练习：你会怎样验证实现符合要求？'},'stop');});});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'linked-interview',question:'按这个网页准备面试 https://example.org/job',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.equal(toolsSeen.includes('read_page'),true);}finally{server.close();}
});
test('explicit industry report preserves topic scope and original quotes',async()=>{
 let turn=0;const row={...source,url:'https://example.org/report',company:'招聘',excerpt:'招聘行业报告认为服务模式正在向专业化发展。招聘行业需要改进信息质量。',context:{source_type:'public_web'}};row.evidence_id='ev_'+createHash('sha256').update(`${row.url}\0${row.excerpt}`).digest('hex').slice(0,24);
 const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('read_skill',{skill_id:'deep-research'},turn):turn===2?tool('find_evidence',{},turn):turn===3?tool('search_web',{site:'web',question:'招聘行业报告'},turn):turn===4?tool('read_page',{site:'web',url:row.url},turn):{role:'assistant',content:JSON.stringify({claims:[{quote:'招聘行业报告认为服务模式正在向专业化发展',evidence_ids:[row.evidence_id],category:'business',scope:'招聘行业'}],limitations:['报告期尚未确认']})};sse(res,next,next.tool_calls?'tool_calls':'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));let searchAnchor,readAnchor;const executions=[];
 const unexpected=async()=>{throw Error('unexpected company cache/report');};const tools={findEvidence:unexpected,searchWeb:async anchor=>{searchAnchor=anchor;return [{url:row.url,site:'web',title:'招聘行业报告',status:'candidate'}];},readPage:async anchor=>{readAnchor=anchor;return row;},readJob:unexpected,readBrowserPage:unexpected,saveReport:async state=>{assert.equal(state.subject_kind,'topic');return {report_id:'industry-report'};},saveExecution:async state=>executions.push(state)};
 try{const result=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w1',requestId:'req_industry',question:'研究下招聘行业',company:'招聘行业',history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);assert.equal(searchAnchor,'');assert.equal(readAnchor,'');assert.match(result.text,/## 业务与行业/);assert.match(result.text,/报告期尚未确认/);assert.equal(executions.at(-1).evidence[0].context.level,'topic');assert.equal(executions.at(-1).context.subject_kind,'topic');assert.equal(result.report.report_id,'industry-report');}finally{server.close();}
});
test('image attachments enter the actual multimodal model payload without base64 in text JSON',async()=>{
 let turn=0;const payloads=[];const server=http.createServer((req,res)=>{let body='';req.on('data',chunk=>body+=chunk);req.on('end',()=>{payloads.push(JSON.parse(body));res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('answer_in_chat',{},turn):{role:'assistant',content:'这是虚构图片测试，不是识别质量验收。'};sse(res,next,next.tool_calls?'tool_calls':'stop');});});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const unexpected=async()=>{throw Error('unexpected external request');};const tools={findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveReport:unexpected,saveExecution:async()=>{}};
 try{await runPiResearchAgent({workspaceId:'w1',requestId:'req_image123',question:'阅读图片',history:[],research:false,attachments:[{id:'image-1',name:'图片.jpg',text:'图片材料',truncated:false,image:{mimeType:'image/jpeg',data:'/9j/AA=='}}]},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);const content=payloads[0].messages.at(-1).content;assert.ok(content.some(part=>part.type==='image_url'&&part.image_url.url==='data:image/jpeg;base64,/9j/AA=='));assert.doesNotMatch(content.find(part=>part.type==='text').text,/\/9j\/AA/);}finally{server.close();}
});

test('plain answer uses zero tools and one model turn, regardless of a company hint',async()=>{
 let calls=0;const server=http.createServer((_req,res)=>{calls++;res.writeHead(200,{'Content-Type':'text/event-stream'});sse(res,{role:'assistant',content:'可以从你自己的项目中挑选一个真实例子。'},'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));const unexpected=async()=>{throw Error('unexpected tool');};
 try{const result=await runPiResearchAgent({workspaceId:'w',requestId:'plain-test',question:'如何讲好我的项目？',company:'示例公司',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:unexpected,searchWeb:unexpected,readPage:unexpected,readJob:unexpected,readBrowserPage:unexpected,saveExecution:unexpected,saveReport:unexpected},()=>{},new AbortController().signal);assert.match(result.text,/真实例子/);assert.equal(calls,1);}finally{server.close();}
});

test('direct English official URL reads without subject or search and returns natural citations',async()=>{
 const url='https://docs.example.org/framework';const doc={...source,url,company:'',excerpt:'The framework separates retrieval from generation. This document describes the public API.',context:{source_type:'public_web',research_topic:'web'},status:'read_original'};doc.evidence_id='ev_'+createHash('sha256').update(`${url}\0${doc.excerpt}`).digest('hex').slice(0,24);
 let calls=0,reads=0;const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});calls++;const next=calls===1?tool('read_page',{url,focus:'retrieval API'},calls):{role:'assistant',content:`这份官方资料将检索与生成分开 [${doc.evidence_id}]。这是基于原文的解释。`};sse(res,next,next.tool_calls?'tool_calls':'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));const unexpected=async()=>{throw Error('unnecessary acquisition');};
 try{const result=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w',requestId:'direct-web',question:`比较技术机制 ${url}`,history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{findEvidence:unexpected,searchWeb:unexpected,readPage:async(company,_site,target,_signal,_timeout,focus)=>{assert.equal(company,'');assert.equal(target,url);assert.equal(focus,'retrieval API');reads++;return doc;},readJob:unexpected,readBrowserPage:unexpected,saveExecution:async()=>{},saveReport:unexpected},()=>{},new AbortController().signal);assert.equal(calls,2);assert.equal(reads,1);assert.match(result.text,/\[1\]/);assert.equal(result.report,undefined);assert.equal(result.evidence.length,1);}finally{server.close();}
});

test('deep research cannot present an unsourced model answer as a finding',async()=>{
 let turns=0,searches=0;const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turns++;sse(res,{role:'assistant',content:'未经核验的行业规模是 1000 亿元。'},'stop');});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w',requestId:'unsourced-research',question:'研究某行业规模',history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{searchWeb:async()=>{searches++;return [];},saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.equal(searches,1);assert.equal(turns,2);assert.doesNotMatch(result.text,/1000 亿元/);assert.match(result.text,/没有取得可引用的原文|没有找到可读取的相关原文/);}finally{server.close();}
});

test('deep research reads a supplied original when the model skips tools',async()=>{
 const url='https://docs.example.org/guide',quote='The guide explains how to validate retrieval results.';const doc={...source,url,company:'',excerpt:quote,context:{source_type:'public_web',research_topic:'web'},status:'read_original'};doc.evidence_id='ev_'+createHash('sha256').update(`${url}\0${quote}`).digest('hex').slice(0,24);
 let turns=0,reads=0;const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turns++;sse(res,{role:'assistant',content:turns===1?'The guide explains validation.':`这份原文说明了检索结果的验证方法 [${doc.evidence_id}]。`},'stop');});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const result=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w',requestId:'auto-read',question:`研究检索验证 ${url}`,history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{readPage:async()=>{reads++;return doc;},saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.equal(turns,2);assert.equal(reads,1);assert.match(result.text,/验证方法 \[1\]/);assert.equal(result.evidence.length,1);}finally{server.close();}
});

test('interview state survives stored conversation and is passed into the next turn',async()=>{
 const state={asked:['解释缓存失效'],weaknesses:['没有说明并发'],follow_up_reason:'检验并发条件',current_question:'如何避免同时重建？',mode:'practice'};
 const finished=finishChat(beginChat(undefined,'interview-session','模拟面试','2026-09-29').chat,'下一题',undefined,'2026-09-29',{interviewState:state});assert.deepEqual(fromStoredResearchChat(toStoredResearchChat('w',finished)).turns.at(-1).interviewState,state);
 let turn=0;const server=http.createServer((req,res)=>{let body='';req.on('data',v=>body+=v);req.on('end',()=>{const payload=JSON.parse(body);assert.match(JSON.stringify(payload.messages.find(m=>m.role==='user').content),/检验并发条件/);res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;sse(res,{role:'assistant',content:turn===1?'你已提到缓存失效，如何避免同时重建？':'你说清了用锁限制并发，但还缺少锁失效的处理。锁失效时你会怎样处理？'},'stop');});});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{await runPiResearchAgent({skillId:'interview-prep',interviewState:state,workspaceId:'w',requestId:'interview-followup',question:'我会先加锁',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.equal(turn,2);}finally{server.close();}
});

test('an explicitly requested technical report can save without inventing a company',async()=>{
 const url='https://docs.example.org/architecture',quote='检索层负责获取相关原文，生成层根据原文生成回答。';
 const doc={...source,url,company:'',excerpt:quote,context:{source_type:'public_web',research_topic:'web'}};doc.evidence_id='ev_'+createHash('sha256').update(`${url}\0${quote}`).digest('hex').slice(0,24);
 let turn=0,saved;const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('read_page',{url},turn):{role:'assistant',content:JSON.stringify({claims:[{statement:quote,quote,evidence_ids:[doc.evidence_id],category:'business'}]})};sse(res,next,next.tool_calls?'tool_calls':'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{const result=await runPiResearchAgent({workspaceId:'w',requestId:'technical-report',question:`比较检索与生成，保存报告 ${url}`,history:[],research:true,reportRequested:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{readPage:async()=>doc,saveExecution:async()=>{},saveReport:async value=>{saved=value;return {report_id:'topic-report'};}},()=>{},new AbortController().signal);assert.equal(result.report.report_id,'topic-report');assert.equal(saved.subject_kind,'topic');assert.equal(turn,2);}finally{server.close();}
});

test('interview tool updates the durable state before answering one next question',async()=>{
 const state={asked:['解释缓存失效'],weaknesses:['并发处理不完整'],follow_up_reason:'追问用户未覆盖的并发',current_question:'如何防止缓存击穿？'};
 let turn=0;const executions=[];const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('remember_interview',state,turn):{role:'assistant',content:'接着练习一题：如何防止缓存击穿？'};sse(res,next,next.tool_calls?'tool_calls':'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'interview-record',question:'开始模拟面试',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async value=>executions.push(value)},()=>{},new AbortController().signal);const delivered={...state,asked:['如何防止缓存击穿？'],mode:'practice'};assert.deepEqual(result.interviewState,delivered);assert.deepEqual(executions.at(-1).context.interview_state,delivered);assert.deepEqual(executions[0].context.interview_state,state);assert.equal(executions.at(-1).status,'complete');assert.equal(turn,2);}finally{server.close();}
});

test('resume skill hands off a reviewed proposal without applying or invoking a second model',async()=>{
 let turn=0,proposals=0;const payloads=[];const patch={section:'projects',before:['实现本地工具'],after:['使用 Python 实现本地工具'],rationale:'突出真实技术',evidence_ids:['resume:projects:1','resume:skills:1'],needs_user_input:[]};
 const server=http.createServer((req,res)=>{let body='';req.on('data',v=>body+=v);req.on('end',()=>{payloads.push(JSON.parse(body));res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('read_confirmed_resume',{},turn):turn===2?tool('propose_resume_changes',{base_version_id:'confirmed-v1',patches:[patch]},turn):{role:'assistant',content:'已生成项目修改提案，请逐项审阅后再保存。'};sse(res,next,next.tool_calls?'tool_calls':'stop');});});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{const result=await runPiResearchAgent({skillId:'resume-tailor',workspaceId:'w',requestId:'resume-proposal',question:'只修改项目经历',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{readResume:async()=>({source_version_id:'confirmed-v1',text:'实现本地工具，Python',evidence_ids:['resume:projects:1','resume:skills:1']}),proposeResume:async value=>{assert.equal(value.base_version_id,'confirmed-v1');assert.deepEqual(value.patches,[patch]);proposals++;return {session_id:'proposal-v1'};},saveExecution:async()=>{}},()=>{},new AbortController().signal);assert.equal(result.resumeProposalId,'proposal-v1');assert.equal(proposals,1);assert.equal(turn,3);assert(payloads.every(p=>p.messages.filter(m=>m.role==='system').length===1));}finally{server.close();}
});

test('simulation repairs multiple questions even when the model omitted interview memory',async()=>{
 let turns=0;const executions=[];
 const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turns++;sse(res,{role:'assistant',content:turns===1?'你如何处理缓存？如何验证结果？':'你如何验证缓存失效后的结果？'},'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{const answer=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'one-question',question:'开始模拟面试',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async row=>executions.push(row)},()=>{},new AbortController().signal);
  assert.equal(turns,2);assert.equal((answer.text.match(/？/g)||[]).length,1);assert(executions.at(-1).actions.some(row=>row.reason==='interview_multiple_questions'));
 }finally{server.close();}
});


test('invalid interview reply after bounded repair fails instead of being marked complete or streamed',async()=>{
 let turns=0;const executions=[],deltas=[];
 const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turns++;sse(res,{role:'assistant',content:'先看看准备清单'},'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{await assert.rejects(runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'invalid-interview',question:'开始模拟面试',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async row=>executions.push(row)},text=>deltas.push(text),new AbortController().signal),/assistant_failure:interview_output/);
  assert.equal(turns,2);assert.equal(executions.at(-1).status,'failed');assert.deepEqual(deltas,[]);
 }finally{server.close();}
});

test('live job tool caches identical queries, keeps results and passes source cursors on continuation',async()=>{
 let turn=0,searches=0;const prior=[];const executions=[];
 const server=http.createServer((_request,response)=>{response.writeHead(200,{'Content-Type':'text/event-stream'});turn++;
  const next=turn<=3?tool('search_jobs',{query:'Python工程师',cities:['上海'],continue:turn===3},turn):{role:'assistant',content:'已取得实时岗位，请核对完整JD。'};sse(response,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const row={job_id:'live-job-1',title:'Python工程师',company:'Example',locations:['上海'],apply_url:'https://example.org/jobs/1',source:{source_name:'猎聘'}};
 const tools={findEvidence:async()=>[],searchWeb:async()=>[],readPage:async()=>null,readJob:async()=>null,readBrowserPage:async()=>null,saveReport:async()=>null,saveExecution:async value=>executions.push(value),searchJobs:async(_query,cities,previous)=>{searches++;prior.push(previous);assert.deepEqual(cities,['上海']);return {result_page:{run_id:'live-run',total:1,items:[{job:row}]},source_runs:[{source_id:'liepin',can_continue:true,next_cursor:'city-cursor'}],blocked_sources:[]};}};
 try{const result=await runPiResearchAgent({workspaceId:'w1',requestId:'live-test',question:'找上海Python工程师',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',tools,()=>{},new AbortController().signal);
  assert.equal(searches,2);assert.equal(prior[0],undefined);assert.equal(prior[1].source_runs[0].next_cursor,'city-cursor');assert.equal(result.jobs.length,1);assert.equal(result.jobs[0].job_id,'live-job-1');assert.equal(executions.at(-1).context.job_searches[0].response.result_page.run_id,'live-run');}
 finally{server.close();}
});


test('empty model completion retains retrieved originals without claiming completed research',async()=>{
 const url='https://example.org/guide',quote='The guide describes automatic checks before performing a page action.';
 const doc={...source,url,company:'',excerpt:quote};doc.evidence_id='ev_'+createHash('sha256').update(url+'\0'+quote).digest('hex').slice(0,24);
 let turn=0;const saved=[];
 const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turn++;const next=turn===1?tool('read_page',{url},turn):{role:'assistant',content:''};sse(res,next,next.tool_calls?'tool_calls':'stop');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const value=await runPiResearchAgent({skillId:'deep-research',workspaceId:'w',requestId:'empty-model-original',question:`研究此文档 ${url}`,history:[],research:true},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{readPage:async()=>doc,saveExecution:async row=>saved.push(row)},()=>{},new AbortController().signal);
 assert.equal(value.evidence.length,1);assert.match(value.text,/本轮综合分析未完成/);assert.match(value.text,/\[1\]/);assert.equal(saved.at(-1).status,'read_failed');assert.equal(turn,2);
 }finally{server.close();}
});

test('login and verification gates provide recovery, not a no-data conclusion',()=>{
 for(const [status,expected] of [['login_required',/需要登录/],['verification_required',/人机验证/]]){
 const answer=explainResearchGap(0,[{tool:'browser_open',status}],[],'研究公开资料');assert.match(answer,expected);assert.match(answer,/然后继续研究/);assert.doesNotMatch(answer,/只检查了已保存/);
 }
});


test('role-only preparation, setup and restarting practice use the right delivery contract',async()=>{
 const cases=[
  {question:'帮助我准备agent面试',history:[{role:'assistant',text:'旧题：如何验证？'}],response:'没有JD也能准备。先练工具调用的参数校验，再练失败恢复；自检能否给出测试边界。',mode:'prepare',feedback:false,current:''},
  {question:'再讲讲工具调用',interviewState:{asked:[],weaknesses:[],follow_up_reason:'',current_question:'',mode:'prepare'},history:[],response:'先定义schema，再验证工具参数与返回值。',mode:'prepare',feedback:false,current:''},
  {question:'开始模拟面试',history:[],response:'想练哪个岗位方向？',mode:'practice',feedback:false,current:''},
  {question:'Agent开发工程师',history:[{role:'assistant',text:'想练哪个岗位方向？'}],response:'用假设场景练习：工具调用超时时如何处理？',mode:'practice',feedback:false,current:'用假设场景练习：工具调用超时时如何处理？'},
  {question:'开始模拟Agent面试，没有JD',interviewState:{asked:['旧题？'],weaknesses:[],follow_up_reason:'',current_question:'旧题？'},history:[],response:'请设计工具调用超时的处理流程。',mode:'practice',feedback:false,current:'请设计工具调用超时的处理流程'},
  {question:'给我准备清单',interviewState:{asked:['旧题？'],weaknesses:[],follow_up_reason:'',current_question:'旧题？'},history:[],response:'先练工具调用：如何避免重复执行？再用样例验证失败分支。',mode:'prepare',feedback:false,current:''}
 ];
 for(const [index,c] of cases.entries()){
  let turns=0;const rows=[];
  const server=http.createServer((req,res)=>{let body='';req.on('data',v=>body+=v);req.on('end',()=>{
   const payload=JSON.parse(body);const content=payload.messages.at(-1).content;const input=JSON.parse(typeof content==='string'?content:content[0].text);
   assert.deepEqual(input.interview_delivery,{mode:c.mode,feedback_required:c.feedback,jd_optional:true,previous_question:c.mode==='practice'?c.interviewState?.current_question||null:null});
   assert(!payload.tools.some(t=>['search_web','read_page','read_browser_page'].includes(t.function.name)));
   turns++;res.writeHead(200,{'Content-Type':'text/event-stream'});sse(res,{role:'assistant',content:c.response},'stop');
  });});await new Promise(r=>server.listen(0,'127.0.0.1',r));
  try{
   const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:`mode-${index}`,question:c.question,history:c.history,interviewState:c.interviewState,research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{readJob:async()=>assert.fail('JD is optional'),readResume:async()=>assert.fail('Do not read personal data'),saveExecution:async r=>rows.push(r)},()=>{},new AbortController().signal);
   assert.equal(turns,1);assert.equal(result.text,c.response);assert.equal(result.interviewState.mode,c.mode);assert.equal(result.interviewState.current_question,c.current);assert.equal(rows.at(-1).status,'complete');
  }finally{server.close();}
 }
});

test('JD gating is repaired once into usable role preparation',async()=>{
 let turns=0;const rows=[];
 const server=http.createServer((_req,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});turns++;sse(res,{role:'assistant',content:turns===1?'请先提供JD才能准备面试。':'没有JD也能准备Agent开发：先练工具调用，再练失败恢复。'},'stop');});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  const result=await runPiResearchAgent({skillId:'interview-prep',workspaceId:'w',requestId:'optional-jd',question:'帮助我准备agent面试',history:[],research:false},{protocol:'openai',provider:'openai',endpoint:`http://127.0.0.1:${server.address().port}/v1`,model_id:'mock',status:'verified',auth_mode:'none'},'',{saveExecution:async r=>rows.push(r)},()=>{},new AbortController().signal);
  assert.equal(turns,2);assert.match(result.text,/工具调用/);assert.equal(result.interviewState.current_question,'');assert(rows.at(-1).actions.some(r=>r.reason==='interview_jd_required'));
 }finally{server.close();}
});
