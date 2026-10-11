import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadChatPins,toggleChatPin,sortPinnedChats} from '../dist-electron/shared/chat-pins.js';
const storage=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};};
const chats=[{id:'old',title:'A',updatedAt:'2026-10-01'},{id:'new',title:'B',updatedAt:'2026-10-11'},{id:'middle',title:'C',updatedAt:'2026-10-05'}];
test('pins survive reload, remain workspace scoped, and unpin restores chronological order',()=>{
 const disk=storage();
 toggleChatPin(disk,'one','old');
 const pins=loadChatPins(disk,'one');
 assert.deepEqual(loadChatPins(disk,'two'),[]);
 assert.deepEqual(sortPinnedChats(chats,pins,'recent').map(x=>x.id),['old','new','middle']);
 assert.deepEqual(sortPinnedChats(chats,toggleChatPin(disk,'one','old'),'recent').map(x=>x.id),['new','middle','old']);
 assert.equal(chats[0].updatedAt,'2026-10-01');
});
test('pin order is independent of replies and sorting; filtered or archived chats are not reintroduced',()=>{
 const disk=storage();toggleChatPin(disk,'one','old');const pins=toggleChatPin(disk,'one','middle');
 const updated=chats.map(x=>x.id==='old'?{...x,updatedAt:'2026-10-12'}:x);
 for(const sort of ['recent','oldest','title'])assert.deepEqual(sortPinnedChats(updated,pins,sort).map(x=>x.id),['middle','old','new']);
 assert.deepEqual(sortPinnedChats(chats.filter(x=>x.id!=='middle'),pins,'recent').map(x=>x.id),['old','new']);
 assert.deepEqual(sortPinnedChats(chats.filter(x=>x.title==='B'),pins,'recent').map(x=>x.id),['new']);
});
test('failed storage writes do not falsely return success or erase previous pins',()=>{
 const disk=storage();toggleChatPin(disk,'one','old');
 assert.throws(()=>toggleChatPin({...disk,setItem(){throw Error('quota');}},'one','middle'),/quota/);
 assert.deepEqual(loadChatPins(disk,'one'),['old']);
});
