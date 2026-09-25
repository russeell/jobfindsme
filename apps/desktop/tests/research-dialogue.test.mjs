import test from 'node:test';
import assert from 'node:assert/strict';
import {decideResearchRequest} from '../dist-electron/shared/research-dialogue.js';
import {acceptsResearchDelta,beginChat,failChat,finishChat,loadResearchChats,saveResearchChats} from '../dist-electron/shared/research-chat-history.js';

test('explicit company needs no link, while ambiguous research asks in the conversation',()=>{
 const direct=decideResearchRequest('腾讯的经营和员工福利怎么样？',{hasJob:false});
 assert.equal(direct.kind,'research');assert.equal(direct.company,'腾讯');
 const unclear=decideResearchRequest('这家公司福利怎么样？',{hasJob:false});
 assert.equal(unclear.kind,'clarify');assert.equal(unclear.pending.missing,'company');
 const answered=decideResearchRequest('腾讯',{hasJob:false,pending:unclear.pending});
 assert.equal(answered.kind,'research');assert.equal(answered.company,'腾讯');assert.equal(answered.question,'这家公司福利怎么样？');
 assert.equal(decideResearchRequest('你好',{hasJob:false}).kind,'chat');
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
});

test('workspace history and streaming events are isolated',()=>{
 const values=new Map();globalThis.localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)};
 const chat=finishChat(beginChat(undefined,'c1','你好','2026-01-01').chat,'你好',undefined,'2026-01-01');
 assert.equal(saveResearchChats('w1',[chat]),true);
 assert.equal(loadResearchChats('w1').length,1);assert.equal(loadResearchChats('w2').length,0);
 const active={id:'r1',workspaceId:'w1',kind:'model'};
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',workspace_id:'w1',delta:'a'},'w1'),true);
 assert.equal(acceptsResearchDelta(active,{request_id:'r2',workspace_id:'w1',delta:'b'},'w1'),false);
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',workspace_id:'w2',delta:'c'},'w1'),false);
 assert.equal(acceptsResearchDelta(active,{request_id:'r1',workspace_id:'w1',delta:'d'},'w2'),false);
 globalThis.localStorage={getItem:()=>null,setItem:()=>{throw Error('quota');}};
 assert.equal(saveResearchChats('w1',[chat]),false);
});
