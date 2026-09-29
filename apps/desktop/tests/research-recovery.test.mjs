import test from 'node:test';
import assert from 'node:assert/strict';
import {stageResearchChat,acknowledgeResearchChat,pendingResearchChats,researchChatsForRecovery,removeResearchChatRecovery,migrateResearchChats,toStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';
const chat=(id,n,at='2026-09-29')=>({id,title:id,updatedAt:at,turns:Array.from({length:n},(_,i)=>({role:i%2?'assistant':'user',text:String(i)})),reportIds:[]});
function storage(){const data=new Map();global.localStorage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)};}
test('failed pending update survives migrated restart, second save failure and eventual read-back',async()=>{
 storage();const old=chat('one',2),fresh=chat('one',4,'2026-09-30');stageResearchChat('w',fresh);
 const local=researchChatsForRecovery('w',[fresh],[old],new Set(),true);
 await assert.rejects(migrateResearchChats('w',local,[old],async()=>{throw Error('disk failure')},async()=>[]));
 assert.equal(pendingResearchChats('w')[0].turns.length,4);
 let stored;const restored=await migrateResearchChats('w',researchChatsForRecovery('w',[],[old],new Set(),true),[old],async v=>{stored=v},async()=>[stored]);
 assert.equal(restored[0].turns.length,4);assert.equal(restored[0].updatedAt,fresh.updatedAt);
 acknowledgeResearchChat('w',restored[0]);assert.equal(pendingResearchChats('w').length,0);
});
test('new pending chats recover but archived/deleted old cache cannot resurrect; workspaces isolated',()=>{
 storage();stageResearchChat('w',chat('new',2));stageResearchChat('w',chat('archived',4));stageResearchChat('w',chat('deleted',4));removeResearchChatRecovery('w','deleted');
 assert.deepEqual(researchChatsForRecovery('w',[chat('stale-deleted',2)],[],new Set(['archived']),true).map(c=>c.id),['new']);
 assert.deepEqual(pendingResearchChats('other'),[]);
});
test('acknowledging earlier queued version retains the newer update and legacy active updates recover',()=>{
 storage();const old=chat('one',2),fresh=chat('one',4);stageResearchChat('w',fresh);acknowledgeResearchChat('w',old);
 assert.equal(pendingResearchChats('w')[0].turns.length,4);
 assert.equal(researchChatsForRecovery('w',[fresh],[old],new Set(),true)[0].turns.length,4);
 assert.equal(toStoredResearchChat('w',fresh).updated_at,fresh.updatedAt);
});
