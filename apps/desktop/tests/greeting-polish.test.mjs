import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {polishGreeting} from '../dist-electron/main/research/greeting-polish.mjs';
const base={protocol:'openai_compatible',provider:'fixture',model_id:'fixture',status:'verified',auth_mode:'none'};
async function fixture(run,finish='stop',output='您好，希望了解{岗位}的工作内容，期待与您沟通。'){
 let received;
 const server=createServer(async(req,res)=>{let body='';for await(const chunk of req)body+=chunk;received=JSON.parse(body);res.writeHead(200,{'Content-Type':'text/event-stream'});for(const chunk of [{choices:[{index:0,delta:{role:'assistant',content:output},finish_reason:null}]},{choices:[{index:0,delta:{},finish_reason:finish}]}])res.write(`data: ${JSON.stringify(chunk)}\n\n`);res.end('data: [DONE]\n\n');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{await run({...base,endpoint:`http://127.0.0.1:${server.address().port}/v1`},()=>received);}finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
test('one tool-free bounded request returns a review draft and preserves placeholders',async()=>fixture(async(connection,received)=>{
 const result=await polishGreeting(connection,'','您好，想了解{岗位}。',new AbortController().signal);
 assert.match(result,/\{岗位\}/);const body=received();assert.equal(body.model,'fixture');assert.ok(!body.tools?.length);assert.equal(body.messages.at(-1).content,'您好，想了解{岗位}。');assert.ok(body.max_tokens<=600||body.max_completion_tokens<=600);
}));
test('truncated output is not accepted as a complete greeting',async()=>fixture(async connection=>{await assert.rejects(polishGreeting(connection,'','你好',new AbortController().signal),/greeting_polish:incomplete/);},'length'));
test('missing credentials and pre-cancelled requests never call provider',async()=>{
 await assert.rejects(polishGreeting({...base,auth_mode:'api_key'},'','你好',new AbortController().signal),/greeting_polish:credentials/);
 await assert.rejects(polishGreeting({...base,status:'failed'},'','你好',new AbortController().signal),/测试连接/);
 const c=new AbortController();c.abort();await assert.rejects(polishGreeting(base,'','你好',c.signal),/greeting_polish:cancelled/);
});

test('IPC-wrapped cancellation and timeout retain precise recovery messages',async()=>{const {userError}=await import('../dist-electron/shared/user-errors.js');assert.match(userError(new Error("Error invoking remote method: greeting_polish:cancelled")).message,/已停止润色/);assert.match(userError(new Error("Error invoking remote method: greeting_polish:timeout")).message,/等待超时/);});
test('resume selection mode sends only selected text with a separate fact-preserving instruction',async()=>fixture(async(connection,received)=>{
 await polishGreeting(connection,'','负责虚构项目的接口实现',new AbortController().signal,'resume_shorten');
 const body=received();assert.equal(body.messages.at(-1).content,'负责虚构项目的接口实现');assert.match(body.messages[0].content,/简历选段编辑/);assert.match(body.messages[0].content,/不新增/);assert.ok(!body.tools?.length);assert.ok(body.max_tokens<=1400||body.max_completion_tokens<=1400);
}));

test('DeepSeek short edits explicitly disable its default thinking mode without changing other providers',async()=>{
 const {editingModel}=await import('../dist-electron/main/research/greeting-polish.mjs');
 const deep=editingModel({...base,endpoint:'https://api.deepseek.com',model_id:'deepseek-v4-flash'});
 assert.equal(deep.reasoning,true);assert.equal(deep.compat.thinkingFormat,'deepseek');
 const other=editingModel({...base,endpoint:'https://example.com'});assert.equal(other.reasoning,false);
 await fixture(async(connection,received)=>{
  const result=await polishGreeting(connection,'','你好',new AbortController().signal);assert.ok(result);assert.equal(received().thinking,undefined);
 });
});
test('DeepSeek adapter actually emits disabled thinking for a short editing request',async()=>{
 const {editingModel}=await import('../dist-electron/main/research/greeting-polish.mjs');
 const {streamSimple}=await import('@earendil-works/pi-ai/api/openai-completions');
 let sent;
 const model=editingModel({...base,endpoint:'https://api.deepseek.com',model_id:'deepseek-v4-flash'});
 const response=await streamSimple(model,{messages:[{role:'user',content:'虚构测试',timestamp:Date.now()}]}, {apiKey:'fixture',maxTokens:600,maxRetries:0,fetch:async(_url,init)=>{
  sent=JSON.parse(init.body);
  return new Response('data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',content:'test'},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n',{headers:{'Content-Type':'text/event-stream'}});
 }}).result();
 assert.equal(response.stopReason,'stop');assert.deepEqual(sent.thinking,{type:'disabled'});assert.ok(!sent.tools?.length);
});

for(const output of ['您好，想了解{岗位}。','您好！想了解 {岗位}'])test(`unchanged greeting is rejected: ${output}`,async()=>fixture(async connection=>{
 await assert.rejects(polishGreeting(connection,'','您好，想了解{岗位}。',new AbortController().signal),/greeting_polish:unchanged/);
},'stop',output));
test('rewrites cannot silently drop reusable placeholders',async()=>fixture(async connection=>{
 await assert.rejects(polishGreeting(connection,'','您好，想了解{公司}的{岗位}。',new AbortController().signal),/greeting_polish:placeholders/);
}));
test('style guides the same bounded request and no-op errors explain recovery',async()=>fixture(async(connection,received)=>{
 await polishGreeting(connection,'','您好，想了解{岗位}。',new AbortController().signal,'greeting','concise');
 assert.match(received().messages[0].content,/40.{0,2}80/);
 assert.equal(received().messages.at(-1).content,'您好，想了解{岗位}。');
 const {userError}=await import('../dist-electron/shared/user-errors.js');
 assert.match(userError(new Error('greeting_polish:unchanged')).message,/原文|实际改动/);
}));
