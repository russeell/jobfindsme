import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {polishGreeting} from '../dist-electron/main/research/greeting-polish.mjs';
const base={protocol:'openai_compatible',provider:'fixture',model_id:'fixture',status:'verified',auth_mode:'none'};
async function fixture(run,finish='stop'){
 let received;
 const server=createServer(async(req,res)=>{let body='';for await(const chunk of req)body+=chunk;received=JSON.parse(body);res.writeHead(200,{'Content-Type':'text/event-stream'});for(const chunk of [{choices:[{index:0,delta:{role:'assistant',content:'您好，希望了解{岗位}的工作内容，期待与您沟通。'},finish_reason:null}]},{choices:[{index:0,delta:{},finish_reason:finish}]}])res.write(`data: ${JSON.stringify(chunk)}\n\n`);res.end('data: [DONE]\n\n');});
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
