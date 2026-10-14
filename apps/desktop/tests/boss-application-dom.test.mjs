import assert from 'node:assert/strict';
import test from 'node:test';
import {runInNewContext} from 'node:vm';
import {bossApplicationScript} from '../dist-electron/main/applications/boss-dom.js';

// Deterministic DOM shapes, modeled on the inspected BOSS detail/IM controls.
// No cookies, real recruiter identifiers, network requests or employer messages.
function fixture({wrongJob=false,wrongAccount=false,wrongAttachment=false,pending=false,duplicateButton=false,contacted=false,inlineClient=false}={}){
 const target={jobId:'fictional',title:'示例工程师',company:'虚构公司',account:'188****0000',chatUrl:'https://www.zhipin.com/web/geek/chat?id=recruiter',fileName:'简历-1234567890abcdef.pdf',message:'您好，示例工程师岗位。'};
 const clicks=[];
 class Element{
  constructor(text='',attrs={},map={}){this.innerText=this.textContent=text;this.attrs=attrs;this.map=map;this.className=attrs.class||'';}
  getBoundingClientRect(){return {width:100,height:20};}
  querySelectorAll(selector){return this.map[selector]||[];}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  getAttribute(name){return this.attrs[name]||null;}setAttribute(name,value){this.attrs[name]=value;}
  matches(){return false;}click(){clicks.push(this.innerText);}focus(){}
 }
 class Input extends Element{get value(){return this.innerText;}set value(s){this.innerText=s;}dispatchEvent(){}}
 const node=t=>new Element(t),button=new Element(contacted?'继续沟通':'立即沟通',{'redirect-url':target.chatUrl});
 const banner=new Element('客户公司：虚构公司',{}, {'.job-name h1,.name h1,h1':[node(target.title)],'a.op-btn.op-btn-chat,a.btn.btn-startchat':duplicateButton?[button,button]:[button]});
 if(inlineClient){banner.innerText=banner.textContent='客户公司：虚构公司杭州 在校/应届 本科';banner.map['*']=[node('客户公司：虚构公司'),node('杭州 在校/应届 本科')];}
 const input=new Input(''),send=node('发送');
 const outgoing=new Element('',{class:pending?'message-item item-myself pending':'message-item item-myself'}, {'.message-text,.text-content,.text,.message-body':[node(target.message)]});
 const attachment=node(wrongAttachment?'平台旧简历.pdf':target.fileName);
 const resumeMessage=new Element('',{class:'message-item item-myself'}, {'.resume-card,.resume-name,.file-name,.message-resume':[attachment]});
 const link=new Element('',{href:`https://www.zhipin.com/job_detail/${wrongJob?'another':'fictional'}.html`});
 const root=new Element('',{}, {'a[href*="/job_detail/"]':[link],'.message-item,.chat-message':[outgoing,resumeMessage]});
 const panel=new Element(attachment.innerText,{}, {'.resume-item,li':[new Element(attachment.innerText,{class:'selected'})],'.btns span,.btns button,button':[node('确定')]});
 const map={
  '.job-banner':[banner],
  'a[href^="/web/geek/recommend"],a[href^="https://www.zhipin.com/web/geek/recommend"],.user-nav .user-name,.nav-user .user-name':[node(wrongAccount?'177****1111':target.account)],
  '.chat-conversation,.chat-container,.chat-window,.chat-content':[root],'#chat-input':[input],'.chat-op .btn-send':[send],'.panel-resume':[panel],
  '.resume-name,.file-name,.resume-title,.attachment-name':[attachment],
 };
 let location=new URL('https://www.zhipin.com/job_detail/fictional.html');
 const document={querySelectorAll:selector=>map[selector]||[],createRange:()=>({selectNodeContents(){}}),execCommand(_op,_show,text){input.innerText=text;return true;}};
 const context={document,URL,Element,HTMLElement:Element,HTMLInputElement:Input,HTMLTextAreaElement:Input,Event:class{},getSelection:()=>({removeAllRanges(){},addRange(){}}),getComputedStyle:()=>({visibility:'visible'})};
 return {target,clicks,input,
  chat(){location=new URL(target.chatUrl);},
  read(operation='snapshot'){return runInNewContext(bossApplicationScript(operation,target),{...context,location});},
 };
}
test('detail contact is scoped; ambiguous or already contacted controls do not click',()=>{
 const f=fixture();f.read('contact');assert.deepEqual(f.clicks,['立即沟通']);
 for(const args of [{duplicateButton:true},{contacted:true}]){const page=fixture(args);assert.throws(()=>page.read('contact'));assert.deepEqual(page.clicks,[]);}
});
test('application identity uses the same isolated client company field as the JD',()=>{
 const f=fixture({inlineClient:true});assert.equal(f.read().company,'虚构公司');assert.equal(f.read().targetMatched,true);
});
test('different account or selected job stops every chat write',()=>{
 for(const option of [{wrongJob:true},{wrongAccount:true}]){const f=fixture(option);f.chat();assert.equal(f.read().chatReady,false);assert.throws(()=>f.read('send_message'));assert.deepEqual(f.clicks,[]);}
});
test('read back complete greeting and preserve preexisting input',()=>{
 const f=fixture();f.chat();f.read('fill_message');assert.equal(f.input.value,f.target.message);
 assert.throws(()=>f.read('fill_message'),/已有内容/);
 f.input.value='残缺半句';assert.throws(()=>f.read('send_message'),/未完整/);assert.deepEqual(f.clicks,[]);
});
test('pending outgoing bubble is not a receipt and old attachment is never substituted',()=>{
 const f=fixture({pending:true});f.chat();assert.equal(f.read().messageCount,0);
 const old=fixture({wrongAttachment:true});old.chat();assert.equal(old.read().resumeCount,0);assert.throws(()=>old.read('send_resume'),/不一致/);assert.deepEqual(old.clicks,[]);
 const good=fixture();good.chat();assert.equal(good.read().messageCount,1);assert.equal(good.read().resumeCount,1);assert.throws(()=>good.read('send_message'),/招呼语未完整/);
});
