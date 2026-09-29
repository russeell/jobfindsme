import test from 'node:test';
import assert from 'node:assert/strict';
import {assistantSkills,isAssistantSkillId} from '../dist-electron/shared/assistant-skills.js';
import {loadAssistantSkill} from '../dist-electron/main/research/assistant-skills.mjs';
import {validResearchChatInput} from '../dist-electron/shared/research-chat-ipc.js';
import {toStoredResearchChat,fromStoredResearchChat} from '../dist-electron/shared/research-chat-history.js';
test('only reviewed bundled skills load and old chat requests remain valid',()=>{
 const input={request_id:'request-123',session_id:'session-123',workspace_id:'w',connection_id:'m',question:'准备面试',research:false,history:[]};
 assert.equal(validResearchChatInput(input),true);
 for(const skill of assistantSkills){assert.equal(validResearchChatInput({...input,skill_id:skill.id}),true);assert.match(loadAssistantSkill(skill.id),new RegExp(skill.id));}
 assert.equal(isAssistantSkillId('../secret'),false);
 assert.equal(validResearchChatInput({...input,skill_id:'../secret'}),false);
 assert.throws(()=>loadAssistantSkill('../secret'),/unknown assistant skill/);
});
test('selected skill is retained in conversation turns without replacing message text',()=>{
 const chat={id:'chat-12345',title:'准备面试',updatedAt:'2026-09-29T00:00:00Z',turns:[{role:'user',text:'请准备这个岗位',skillId:'interview-prep'}],reportIds:[]};
 assert.deepEqual(fromStoredResearchChat(toStoredResearchChat('w',chat)).turns,chat.turns);
});
