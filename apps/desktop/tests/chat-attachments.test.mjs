import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,mkdir,symlink,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {collectChatAttachments} from '../dist-electron/main/research/chat-attachments.js';
import {validChatAttachments} from '../dist-electron/shared/chat-attachments.js';
import {validResearchChatInput,modelHistoryWithinBudget} from '../dist-electron/shared/research-chat-ipc.js';
import {fromStoredResearchChat,toStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';
test('folder keeps good files, skips failures hidden files and symlinks, bounds text',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'jfm-attachments-'));
 try{await mkdir(path.join(dir,'sub'));await writeFile(path.join(dir,'good.md'),'真实项目材料');await writeFile(path.join(dir,'bad.pdf'),'bad');await writeFile(path.join(dir,'.private.txt'),'secret');await writeFile(path.join(dir,'sub','notes.txt'),'说明');await symlink(path.join(dir,'good.md'),path.join(dir,'link.md'));
 const result=await collectChatAttachments([dir],async(name,base64)=>{if(name==='bad.pdf')throw Error('bad');return {text:Buffer.from(base64,'base64').toString(),truncated:false};});
 assert.equal(result.attachments.length,2);assert.equal(validChatAttachments(result.attachments),true);assert.equal(result.attachments.some(item=>item.text==='secret'),false);assert.ok(result.warnings.some(item=>item.includes('读取失败')));assert.ok(result.warnings.some(item=>item.includes('链接')));
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('attachments persist and enter subsequent model history; oversized IPC rejected',()=>{
 const attachments=[{id:'file1',name:'经历.md',text:'团队项目真实贡献',truncated:false}];
 const input={request_id:'request-123',session_id:'session-123',workspace_id:'w',connection_id:'m',question:'请修改',research:false,history:[],attachments};
 assert.equal(validResearchChatInput(input),true);assert.equal(validResearchChatInput({...input,attachments:[{...attachments[0],text:'a'.repeat(8001)}]}),false);
 const chat={id:'chat-12345',title:'修改',updatedAt:'2026-09-29',reportIds:[],turns:[{role:'user',text:'请修改',attachments}]};
 assert.deepEqual(fromStoredResearchChat(toStoredResearchChat('w',chat)).turns,chat.turns);
 assert.match(modelHistoryWithinBudget(chat.turns)[0].text,/团队项目真实贡献/);
});
