import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {decideResearchRequest} from '../dist-electron/shared/research-dialogue.js';
import {acceptsResearchDelta,beginChat,retryChatAttachments,failChat,finishChat,finishJobSearchChat,stopChat,fromStoredResearchChat,loadResearchChats,mergeResearchChats,migrateResearchChats,reportIdsByTurn,saveResearchChats,saveResearchChatWithRetry,toStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';
import {resolveResearchSession} from '../dist-electron/shared/research-session.js';
import {modelHistoryWithinBudget} from '../dist-electron/shared/research-chat-ipc.js';

test('explicit company needs no link, while an ambiguous question reaches the Agent',()=>{
 const direct=decideResearchRequest('腾讯的经营和员工福利怎么样？',{hasJob:false});
 assert.equal(direct.kind,'research');assert.equal(direct.company,'腾讯');
 const unclear=decideResearchRequest('这家公司福利怎么样？',{hasJob:false});
 assert.equal(unclear.kind,'chat');
 assert.equal(decideResearchRequest('你好',{hasJob:false}).kind,'chat');
});
test('a broad explicit company question can begin finite Agent research',()=>{
 const broad=decideResearchRequest('腾讯怎么样',{hasJob:false});
 assert.equal(broad.kind,'research');assert.equal(broad.company,'腾讯');
 assert.equal(decideResearchRequest('什么是公司治理？',{hasJob:false}).kind,'chat');
 const overview=decideResearchRequest('调研华为',{hasJob:false});assert.equal(overview.kind,'research');assert.equal(overview.company,'华为');
});
test('a transient chat database lock retries the same snapshot once',async()=>{
 const calls=[];await saveResearchChatWithRetry({id:'chat-a'},async item=>{calls.push(item.id);if(calls.length===1)throw Error('research_chat_storage:sqlite_busy');});
 assert.deepEqual(calls,['chat-a','chat-a']);
});

test('stopping retains only approved direct text, without promoting research drafts',()=>{
 const started=beginChat(undefined,'chat-stop','总结这份JD','2026-01-01').chat;
 const stopped=stopChat(started,'已生成的普通回复','direct','2026-01-02');
 assert.equal(stopped.turns.at(-1).text,'已生成的普通回复');
 assert.equal(stopped.turns.at(-1).interrupted,true);
 assert.equal(stopped.draft,undefined);
 const restored=fromStoredResearchChat(toStoredResearchChat('w1',stopped));
 assert.deepEqual(restored.turns,stopped.turns);
 assert.match(modelHistoryWithinBudget(restored.turns).at(-1).text,/已停止/);
 for(const status of [undefined,'checked']){
  const hidden=stopChat(started,'未经核验的公司结论',status,'2026-01-02');
  assert.deepEqual(hidden.turns,started.turns);
  assert.equal(hidden.draft,started.draft);
 }
 assert.equal(stopChat(started,'','direct','2026-01-02').turns.length,1);
});

test('agent role exploration keeps its intent when a company is added and uses the existing job search',()=>{
 assert.equal(decideResearchRequest('你是谁',{hasJob:false}).kind,'chat');
 const first=decideResearchRequest('想了解agent相关岗位',{hasJob:false});
 assert.equal(first.kind,'job_search');assert.equal(first.query,'Agent');
 assert.match(first.reply,/选择来源后再发起检索/);
 const chat=finishJobSearchChat(beginChat(undefined,'c1','想了解agent相关岗位','2026-01-01').chat,first.reply,first.query,first.pending,'2026-01-01');
 const restored=fromStoredResearchChat({...toStoredResearchChat('w1',chat),updated_at:'2026-01-01'});
 assert.equal(restored.pendingResearch.kind,'job_search');assert.equal(restored.turns[1].searchQuery,'Agent');
 const next=resolveResearchSession('minimax',restored,undefined,{}).decision;
 assert.equal(next.kind,'job_search');assert.equal(next.query,'minimax Agent');
 assert.match(next.reply,/没有|再发起检索/);
 const resumed=finishJobSearchChat(beginChat(restored,'c1','minimax','2026-01-02').chat,next.reply,next.query,next.pending,'2026-01-02');
 assert.equal(resumed.turns[0].text,'想了解agent相关岗位');
 assert.equal(resumed.turns[2].text,'minimax');
 assert.equal(resumed.turns[3].searchQuery,'minimax Agent');
 assert.equal(resumed.pendingResearch,undefined);
 assert.deepEqual(modelHistoryWithinBudget(resumed.turns)[3],{role:'assistant',text:next.reply});
});

test('job context resolves a follow-up and an explicit new subject replaces that context',()=>{
 const followup=decideResearchRequest('这个岗位的职责和发展怎么样？',{company:'滴滴',title:'算法工程师',hasJob:true});
 assert.equal(followup.kind,'research');assert.equal(followup.company,'滴滴');assert.equal(followup.title,'算法工程师');
 const switched=decideResearchRequest('腾讯的经营怎么样？',{company:'滴滴',title:'算法工程师',hasJob:true});
 assert.equal(switched.kind,'research');assert.equal(switched.company,'腾讯');assert.equal(switched.title,undefined);
});

test('failed or cancelled turns remain retryable without duplicate user messages',()=>{
 const started=beginChat(undefined,'c1','研究腾讯','2026-01-01');
 const failed=failChat(started.chat,'已取消','2026-01-02');
 const retried=beginChat(failed,'c1','研究腾讯','2026-01-03');
 assert.equal(retried.history.length,0);assert.equal(retried.chat.turns.length,1);
 const complete=finishChat(retried.chat,'已核对公开材料','r1','2026-01-04');
 assert.deepEqual(complete.turns.map(turn=>turn.role),['user','assistant']);
 assert.equal(complete.draft,undefined);assert.deepEqual(complete.reportIds,['r1']);
 assert.equal(complete.turns[1].reportId,'r1');
});

test('report turns keep their saved text and attach each report at its answer',()=>{
 const first=finishChat(beginChat(undefined,'c1','A 公司如何？','2026-01-01').chat,'已读取来源', 'r1','2026-01-01');
 const second=finishChat(beginChat(first,'c1','你好','2026-01-02').chat,'你好',undefined,'2026-01-02');
 const third=finishChat(beginChat(second,'c1','A 公司福利如何？','2026-01-03').chat,'已读取来源', 'r2','2026-01-03');
 const reports=[{report_id:'r1',job_context:{interest_question:'A 公司如何？'}},{report_id:'r2',job_context:{interest_question:'A 公司福利如何？'}}];
 assert.deepEqual([...reportIdsByTurn(third,reports)],[[1,'r1'],[5,'r2']]);
 const old={...third,turns:third.turns.map(({reportId,...turn})=>turn)};
 assert.deepEqual([...reportIdsByTurn(old,reports)],[[1,'r1'],[5,'r2']]);
 const repeated={...old,turns:[...old.turns,{role:'user',text:'A 公司如何？'},{role:'assistant',text:'再次回答'}]};
 assert.deepEqual([...reportIdsByTurn(repeated,reports)],[[5,'r2']]);
 assert.equal(third.turns[1].text,'已读取来源');
 assert.equal(fromStoredResearchChat({...toStoredResearchChat('w1',third),updated_at:'2026-01-03'}).turns[1].reportId,'r1');
 assert.deepEqual(modelHistoryWithinBudget(third.turns)[1],{role:'assistant',text:'已读取来源'});
});
test('answer, citation sources and collapsed process survive a long chat round trip',()=>{
 let chat=beginChat(undefined,'session-1','调研华为','2026-01-01').chat;
 chat=finishChat(chat,'华为公开介绍了研发团队。[1]',undefined,'2026-01-01',{evidence:[{evidence_id:'ev_1',url:'https://example.org/1',excerpt:'华为公开介绍了研发团队。',platform:'公开网页'}],process:[{tool:'find_evidence',status:'completed',count:0},{tool:'read_page',status:'read_original',site:'web'}]});
 for(let index=0;index<20;index++)chat=finishChat(beginChat(chat,'session-1',`追问 ${index}`,'2026-01-02').chat,`回答 ${index}`+'长'.repeat(1000),undefined,'2026-01-02');
 const restored=fromStoredResearchChat({...toStoredResearchChat('w1',chat),updated_at:'2026-01-02'});
 assert.equal(restored.turns[1].text,'华为公开介绍了研发团队。[1]');assert.equal(restored.turns[1].evidence[0].evidence_id,'ev_1');assert.equal(restored.turns[1].process[1].status,'read_original');assert.equal(restored.turns.length,42);
});

test('workspace history and streaming events are isolated',()=>{
 const values=new Map();globalThis.localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};
 const chat=finishChat(beginChat(undefined,'c1','你好','2026-01-01').chat,'你好',undefined,'2026-01-01');
 assert.equal(saveResearchChats('w1',[chat]),true);
 assert.equal(loadResearchChats('w1').length,1);assert.equal(loadResearchChats('w2').length,0);
 const active={id:'r1',workspaceId:'w1',sessionId:'c1',kind:'model'};
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',session_id:'c1',workspace_id:'w1',delta:'a'},'w1'),true);
 assert.equal(acceptsResearchDelta(active,{request_id:'r2',session_id:'c1',workspace_id:'w1',delta:'b'},'w1'),false);
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',session_id:'c1',workspace_id:'w2',delta:'c'},'w1'),false);
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',session_id:'c1',workspace_id:'w1',delta:'d'},'w2'),false);
 globalThis.localStorage={getItem:()=>null,setItem:()=>{throw Error('quota');}};
 assert.equal(saveResearchChats('w1',[chat]),false);
});

test('A and B histories restore their own job, company and mode without dropping long turns',()=>{
 const turns=Array.from({length:30},(_,index)=>({role:index%2?'assistant':'user',text:`round ${index} ${'answer '.repeat(120)}`}));
 const a={id:'a',title:'A',updatedAt:'2026-01-01',turns,reportIds:[],subjectCompany:'A公司',subjectTitle:'A岗位',jobId:'job-a',researchMode:true};
 const b={...a,id:'b',subjectCompany:'B公司',subjectTitle:'B岗位',jobId:'job-b',researchMode:false};
 const restored=[a,b].map(chat=>fromStoredResearchChat(toStoredResearchChat('w1',chat)));
 assert.equal(restored[0].turns.length,30);assert.equal(restored[0].jobId,'job-a');assert.equal(restored[0].subjectCompany,'A公司');assert.equal(restored[0].researchMode,true);
 assert.equal(restored[1].jobId,'job-b');assert.equal(restored[1].subjectCompany,'B公司');assert.equal(restored[1].researchMode,false);
 const active={id:'run-a',workspaceId:'w1',sessionId:'a',kind:'model'};
 assert.equal(acceptsResearchDelta(active,{request_id:'run-a',workspace_id:'w1',session_id:'b',delta:'wrong'},'w1'),false);
 assert.equal(acceptsResearchDelta(active,{request_id:'run-a',workspace_id:'w1',session_id:'a',delta:'right'},'w1'),true);
});

test('local only chat survives first SQLite load for migration',()=>{
 const local={id:'legacy',title:'旧对话',updatedAt:'2026-01-02',turns:[{role:'user',text:'旧问题'}],reportIds:[]};
 const remote={id:'server',title:'新对话',updatedAt:'2026-01-03',turns:[{role:'user',text:'新问题'}],reportIds:[]};
 assert.deepEqual(mergeResearchChats([local],[remote]).map(chat=>chat.id),['server','legacy']);
 const staleRemote={...local,updatedAt:'2026-01-01',turns:[]};
 assert.equal(mergeResearchChats([local],[staleRemote])[0].turns.length,1);
});

test('A and B history selection binds the next turn to the selected session',()=>{
 const a={id:'a',title:'A',updatedAt:'2026-01-01',turns:[],reportIds:[],subjectCompany:'A公司',subjectTitle:'A岗位',jobId:'job-a'};
 const b={...a,id:'b',subjectCompany:'B公司',subjectTitle:'B岗位',jobId:'job-b'};
 const chosen=resolveResearchSession('这个岗位职责如何？',b,undefined,{company:'A公司',title:'A岗位'});
 assert.equal(chosen.decision.kind,'research');assert.equal(chosen.decision.company,'B公司');assert.equal(chosen.activeJobId,'job-b');assert.equal(chosen.current?.id,'b');
 const switched=resolveResearchSession('A公司的经营如何？',b,undefined,{});
 assert.equal(switched.newSubject,true);assert.equal(switched.current,undefined);assert.equal(switched.activeJobId,undefined);
});

test('toStored fixture preserves a long answer and migration verifies the backend readback',async()=>{
 const fixture=JSON.parse(readFileSync(new URL('../../../tests/fixtures/research_chat_to_stored.json',import.meta.url),'utf8'));
 const local={id:fixture.id,title:'示例公司研究',updatedAt:'2026-09-25T00:00:00Z',turns:fixture.turns,reportIds:fixture.report_ids,subjectCompany:fixture.subject_company,subjectTitle:fixture.subject_title,jobId:fixture.job_id,researchMode:fixture.research_mode};
 assert.deepEqual(JSON.parse(JSON.stringify(toStoredResearchChat('workspace-fixture',local))),{...fixture,chat_title:local.title,updated_at:local.updatedAt});
 assert(local.turns[1].text.length>8000);
 const values=new Map();globalThis.localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};
 assert.equal(saveResearchChats('workspace-fixture',[local]),true);
 const saved=[];
 const save=async item=>{saved.push(item);};
 const list=async()=>saved.map(item=>({...item,updated_at:'2026-09-26T00:00:00Z'}));
 const migrated=await migrateResearchChats('workspace-fixture',[local],[],save,list);
 assert.equal(migrated[0].turns[1].text,local.turns[1].text);
 await assert.rejects(migrateResearchChats('workspace-fixture',[local],[],save,async()=>[{...saved.at(-1),turns:[saved.at(-1).turns[0]],updated_at:'2026-09-26T00:00:00Z'}]),/读回不一致/);
 assert.equal(local.turns[1].text.length,fixture.turns[1].text.length);
 assert.equal(loadResearchChats('workspace-fixture')[0].turns[1].text,local.turns[1].text);
});

test('renamed chat title survives storage readback and later turns',()=>{
 const chat={id:'renamed',title:'面试准备',updatedAt:'2026-09-30T00:00:00Z',turns:[{role:'user',text:'原始提问'}],reportIds:[]};
 const stored=toStoredResearchChat('workspace-fixture',chat);
 const restored=fromStoredResearchChat(stored);
 assert.equal(restored.title,'面试准备');
 assert.equal(beginChat(restored,'renamed','继续追问','2026-09-30T01:00:00Z').chat.title,'面试准备');
});


test('failed attachment round restores retry materials after conversation reload, completed round does not',()=>{
 const file={id:'attachment1',name:'example.txt',text:'generic sample',truncated:false};
 const started=beginChat(undefined,'retry-files','改写附件','2026-01-01').chat;
 started.turns[0].attachments=[file];
 const failed=fromStoredResearchChat(toStoredResearchChat('w',failChat(started,'model unavailable','2026-01-02')));
 assert.deepEqual(retryChatAttachments(failed),[file]);
 assert.notEqual(retryChatAttachments(failed),failed.turns[0].attachments);
 const done=finishChat(failed,'修改草稿',undefined,'2026-01-03');
 assert.deepEqual(retryChatAttachments(done),[]);
 assert.deepEqual(retryChatAttachments({...failed,draft:'另一条提问'}),[]);
});
