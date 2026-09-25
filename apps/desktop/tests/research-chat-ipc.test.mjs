import test from 'node:test';
import assert from 'node:assert/strict';
import {beginChat,finishChat,toStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';
import {modelHistoryWithinBudget,validResearchChatInput} from '../dist-electron/shared/research-chat-ipc.js';

test('15 rounds with a long answer pass the same validator as the IPC handler',()=>{
 let chat;
 for(let round=0;round<15;round++){
  const started=beginChat(chat,'session-1234',`问题${round}`,'2026-01-01');
  chat=finishChat(started.chat,`回答${round}`+'答'.repeat(round===14?12000:1000),undefined,'2026-01-01');
 }
 const stored=toStoredResearchChat('workspace-1',chat);
 assert.equal(stored.turns.length,30);
 assert.equal(stored.turns.at(-1).text.length,12004);
 const next=beginChat(chat,'session-1234','继续追问','2026-01-02');
 const request={request_id:'request-1234',session_id:'session-1234',workspace_id:'workspace-1',connection_id:'model-1',question:'继续追问',research:false,history:modelHistoryWithinBudget(next.history)};
 assert.equal(validResearchChatInput({...request,history:next.history}),false);
 assert.equal(validResearchChatInput(request),true);
 assert(request.history.every(turn=>turn.text.length<=8000));
 assert(request.history.reduce((count,turn)=>count+turn.text.length,0)<=20000);
 assert.equal(chat.turns.at(-1).text.length,12004);
});

test('IPC question contract accepts 300, 301 and 700 characters but rejects 701',()=>{
 const base={request_id:'request-1234',session_id:'session-1234',workspace_id:'workspace-1',connection_id:'model-1',research:true,history:[]};
 for(const size of [300,301,700])assert.equal(validResearchChatInput({...base,question:'问'.repeat(size)}),true);
 assert.equal(validResearchChatInput({...base,question:'问'.repeat(701)}),false);
});

test('more than 200 short saved turns remain complete while IPC receives the latest 200',()=>{
 const full=Array.from({length:220},(_,index)=>({role:index%2?'assistant':'user',text:`turn ${index}`}));
 const model=modelHistoryWithinBudget(full);
 assert.equal(full.length,220);
 assert.equal(model.length,200);
 assert.deepEqual(model[0],full[20]);
 const input={request_id:'request-1234',session_id:'session-1234',workspace_id:'workspace-1',connection_id:'model-1',question:'继续追问',research:false,history:model};
 assert.equal(validResearchChatInput(input),true);
});
