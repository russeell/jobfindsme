export type BossTarget={jobId:string;title:string;company:string;account?:string;chatUrl?:string;fileName?:string|null;message?:string};
export type BossSnapshot={url:string;gate:string|null;jobId:string;title:string;company:string;account:string;recruiter:string;chatUrl:string;contactable:boolean;alreadyContacted:boolean;contactEstablished:boolean;chatReady:boolean;targetMatched:boolean;messageCount:number;resumeCount:number;uploaded:boolean;resumeReady:boolean;uploadSelector:string|null;inputText:string;action?:string};
export type BossOperation='snapshot'|'open_upload'|'close_upload'|'contact'|'fill_message'|'send_message'|'open_resume'|'select_resume'|'send_resume';
export function bossApplicationScript(operation:BossOperation,target:BossTarget):string{return `(${bossApplicationDom.toString()})(${JSON.stringify(operation)},${JSON.stringify(target)})`;}

// All writes are fixed operations scoped to a verified job/dialog/conversation.
// Never search the whole page for generic "确定" or let an Agent choose selectors.
export function bossApplicationDom(operation:BossOperation,target:BossTarget):BossSnapshot{
  const text=(e:Element|null)=>((e as HTMLElement|null)?.innerText||e?.textContent||'').trim();
  const normalize=(s:string)=>s.replace(/\s+/g,'').normalize('NFKC');
  const visible=(e:Element|null):e is HTMLElement=>!!e&&(e as HTMLElement).getBoundingClientRect().width>0&&(e as HTMLElement).getBoundingClientRect().height>0&&getComputedStyle(e).visibility!=='hidden';
  const all=(root:ParentNode,selector:string)=>Array.from(root.querySelectorAll(selector)).filter(visible);
  const one=(root:ParentNode,selector:string)=>{const nodes=all(root,selector);return nodes.length===1?nodes[0]:null;};
  const pick=(root:ParentNode,selector:string)=>text(all(root,selector)[0]||null);
  const jobId=(value:string)=>{try{return new URL(value,location.origin).pathname.match(/^\/job_detail\/([\w-]+)\.html$/)?.[1]||'';}catch{return '';}};
  const banner=all(document,'.job-banner')[0];
  const title=banner?pick(banner,'.job-name h1,.name h1,h1'):'';
  const client=text(banner||null).split(/\n/).find(line=>/^客户公司\s*[:：]/.test(line.trim()))?.replace(/^\s*客户公司\s*[:：]\s*/,'').trim();
  const company=client||pick(document,'.sider-company .company-info a[href*="/gongsi/"],.sider-company .company-name,.job-company-name');
  const account=pick(document,'a[href^="/web/geek/recommend"],a[href^="https://www.zhipin.com/web/geek/recommend"],.user-nav .user-name,.nav-user .user-name');
  const overlays=all(document,'.dialog-container,.dialog-wrap,.boss-popup,.verify-dialog,.geetest_panel,.toast,.message-toast');
  const warning=overlays.map(text).join('\n');
  let gate:string|null=/验证|滑块|验证码|安全校验/.test(warning)?'请在 BOSS 原页完成安全验证':/频繁|上限|稍后再试|操作异常/.test(warning)?'BOSS 已限流，本次停止；请稍后在原页核对':null;
  if(/\/web\/user|\/login|\/geek\/guide/.test(location.pathname)||/资料不完善|完善.*资料/.test(warning))gate='请在 BOSS 原页完成登录或必要资料';
  const contact=banner?one(banner,'a.op-btn.op-btn-chat,a.btn.btn-startchat'):null;
  let chatUrl='';
  if(contact){try{const u=new URL(contact.getAttribute('redirect-url')||'',location.origin);if(u.origin==='https://www.zhipin.com'&&u.pathname==='/web/geek/chat'&&u.searchParams.get('id'))chatUrl=u.href;}catch{/* unsupported entry */}}
  const current=new URL(location.href),expected=target.chatUrl?new URL(target.chatUrl):null;
  const chatRoot=all(document,'.chat-conversation,.chat-container,.chat-window,.chat-content')[0];
  const jobLinks=chatRoot?all(chatRoot,'a[href*="/job_detail/"]'):[];
  const matchingLinks=jobLinks.filter(e=>jobId(e.getAttribute('href')||'')===target.jobId);
  const uniqueJob=matchingLinks.length>0&&jobLinks.every(e=>jobId(e.getAttribute('href')||'')===target.jobId);
  const chatIdentity=!!expected&&current.pathname==='/web/geek/chat'&&!!current.searchParams.get('id')&&current.searchParams.get('id')===expected.searchParams.get('id');
  const detailMatched=jobId(location.href)===target.jobId&&normalize(title)===normalize(target.title)&&normalize(company)===normalize(target.company);
  const targetMatched=(detailMatched||chatIdentity&&uniqueJob)&&(!target.account||account===target.account);
  const input=one(document,'#chat-input');
  const chatReady=!!input&&!!chatRoot&&targetMatched&&current.pathname==='/web/geek/chat';
  const selfMessages=chatRoot?all(chatRoot,'.message-item,.chat-message').filter(e=>/(?:^|\s)(?:is-self|myself|item-myself|item-my|right|sent)(?:\s|$)/.test(e.className)||e.getAttribute('data-from')==='self'):[];
  const delivered=selfMessages.filter(e=>!/(?:sending|pending|failed|error)/.test(e.className)&&!e.querySelector('.send-error,.send-failed,.sending'));
  const messageCount=target.message?delivered.filter(e=>normalize(pick(e,'.message-text,.text-content,.text,.message-body'))===normalize(target.message!)).length:0;
  const fileStem=target.fileName?.replace(/\.(pdf|docx)$/i,'');
  const resumeCount=fileStem?delivered.filter(e=>all(e,'.resume-card,.resume-name,.file-name,.message-resume').some(el=>text(el).includes(fileStem))).length:0;
  const panel=all(document,'.panel-resume')[0];
  const uploaded=!!fileStem&&all(document,'.resume-name,.file-name,.resume-title,.attachment-name').some(e=>text(e).includes(fileStem));
  const inputs=Array.from(document.querySelectorAll<HTMLInputElement>('input[type=file]')).filter(e=>/pdf|docx/i.test(e.accept)&&overlays.some(dialog=>dialog.contains(e)&&/附件简历/.test(text(dialog))));
  let uploadSelector:string|null=null;
  if(inputs.length===1&&detailMatched&&!gate){inputs[0].setAttribute('data-jfm-resume-input',target.jobId);uploadSelector=`input[data-jfm-resume-input="${target.jobId}"]`;}
  const contactEstablished=overlays.some(e=>/已向BOSS发送消息|已成功发起沟通/.test(text(e)));
  const inputText=input instanceof HTMLInputElement||input instanceof HTMLTextAreaElement?input.value:text(input);
  const result:BossSnapshot={url:location.href,gate,jobId:jobId(location.href),title,company,account,recruiter:pick(document,'.job-boss-info h2,.boss-info .name'),chatUrl,contactable:!!contact&&!/disabled/.test(contact.className),alreadyContacted:!!contact&&/继续沟通|已沟通/.test(text(contact)),contactEstablished,chatReady,targetMatched,messageCount,resumeCount,uploaded,resumeReady:!!panel&&!!fileStem&&text(panel).includes(fileStem),uploadSelector,inputText};
  if(operation==='snapshot')return result;
  if(gate||!targetMatched)throw Error(gate||'岗位或聊天对象已变化，已停止');
  const click=(e:HTMLElement|null)=>{if(!e||e.matches(':disabled,[aria-disabled=true]')||/disabled/.test(e.className))throw Error('BOSS 操作入口不可用，已停止');e.click();result.action='clicked';return result;};
  if(operation==='open_upload'){
    if(!detailMatched||!banner)throw Error('附件上传必须从准确岗位原页开始');
    const entries=all(banner,'a,button').filter(e=>text(e)==='上传附件简历');
    return click(entries.length===1?entries[0]:null);
  }
  if(operation==='close_upload'){
    const uploadPanels=overlays.filter(e=>/附件简历/.test(text(e))&&!!fileStem&&text(e).includes(fileStem));
    if(!uploadPanels.length){result.action='closed';return result;}
    if(uploadPanels.length!==1)throw Error('附件面板需在原页核对，已停止');
    const close=one(uploadPanels[0],'.dialog-close,.close,[aria-label="关闭"]');return click(close);
  }
  if(operation==='contact'){
    if(!detailMatched||result.alreadyContacted||!chatUrl)throw Error('该岗位已有沟通或无法核对聊天入口，已停止');
    return click(contact);
  }
  if(!chatReady)throw Error('未能核对当前岗位的聊天对象，已停止');
  if(operation==='fill_message'){
    if(!target.message?.trim()||result.inputText)throw Error('聊天输入已有内容，已保留；请在原页核对');
    input!.focus();
    if(input instanceof HTMLTextAreaElement||input instanceof HTMLInputElement){
      const proto=input instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value')!.set!.call(input,target.message);
    }else{
      const range=document.createRange();range.selectNodeContents(input!);const selection=getSelection();selection?.removeAllRanges();selection?.addRange(range);
      if(!document.execCommand('insertText',false,target.message))throw Error('BOSS 未接受完整招呼语，已停止');
    }
    input!.dispatchEvent(new Event('input',{bubbles:true}));result.action='filled';return result;
  }
  if(operation==='send_message'){
    const value=input instanceof HTMLInputElement||input instanceof HTMLTextAreaElement?input.value:text(input);
    if(normalize(value)!==normalize(target.message||''))throw Error('招呼语未完整填入，已停止');
    if(messageCount)throw Error('相同招呼语已有发送记录，不会重复发送');
    return click(one(document,'.chat-op .btn-send'));
  }
  if(operation==='open_resume'){
    if(!target.fileName)throw Error('本次明确不附简历');
    const buttons=all(document,'.chat-op .toolbar-btn,.chat-container .toolbar-btn').filter(e=>text(e)==='发简历');
    return click(buttons.length===1?buttons[0]:null);
  }
  if(!panel||!fileStem||!text(panel).includes(fileStem))throw Error('平台附件与本次所选简历不一致，未发送简历');
  if(operation==='select_resume'){
    const options=all(panel,'.resume-item,li').filter(e=>text(e).includes(fileStem));
    if(options.length===1)return click(options[0]);
    if(options.length===0&&all(panel,'.resume-name,.file-name').length===1){result.action='selected';return result;}
    throw Error('无法唯一选中本次附件，未发送简历');
  }
  if(operation==='send_resume'){
    const choices=all(panel,'.resume-item,li');
    if(choices.length>1){const selected=choices.filter(e=>/selected|checked|active/.test(e.className)||e.querySelector('input:checked,[aria-checked=true],.checked,.selected'));if(selected.length!==1||!text(selected[0]).includes(fileStem))throw Error('简历选择未生效，未发送');}
    const buttons=all(panel,'.btns span,.btns button,button').filter(e=>/^(确定|发送)$/.test(text(e)));
    return click(buttons.length===1?buttons[0]:null);
  }
  throw Error('unsupported application operation');
}
