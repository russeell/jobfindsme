import {useEffect,useState} from 'react';
import type {UpdateState} from '../../../shared/update-contracts';
import buildInfo from '../../../build-info.json';

export type UpdateDraftEvent=CustomEvent<{pending:Promise<unknown>[]} >;
export async function flushUpdateDrafts(){
 const detail={pending:[] as Promise<unknown>[]};
 window.dispatchEvent(new CustomEvent('jfm:before-update',{detail}));
 await Promise.all(detail.pending);
}
function bytes(value:number){return `${(value/1_048_576).toFixed(1)} MB`;}
export function UpdatesPage(){
 const [state,setState]=useState<UpdateState>({phase:'idle',message:'点击检查新版本。'});
 const [action,setAction]=useState(false);
 const [error,setError]=useState('');
 useEffect(()=>{let active=true;const unsubscribe=window.jobfindsme!.onUpdateState(next=>{if(active)setState(next);});void window.jobfindsme!.updateState().then(next=>{if(active)setState(next);});return()=>{active=false;unsubscribe();};},[]);
 async function run(action:()=>Promise<unknown>){setAction(true);setError('');try{const result=await action();if(result&&typeof result==='object'&&'phase' in result)setState(result as UpdateState);}catch(error){setError(error instanceof Error?error.message:'更新操作未完成，请重试。');}finally{setAction(false);}}
 const running=['checking','downloading','verifying','installing'].includes(state.phase);
 const progress=state.total?Math.min(100,Math.floor((state.received||0)/state.total*100)):0;
 return <section className="section updates-page"><h2>版本更新</h2><p>当前版本：{buildInfo.label.split('+')[0]}</p>
 <div className="update-card"><div className="update-card-heading"><strong>{state.tag?`JobFindsMe ${state.tag}`:'检查新版本'}</strong>{state.phase==='ready'&&<span>已校验</span>}</div>
 <p role={state.phase==='error'||state.phase==='rolled_back'?'alert':'status'} aria-live="polite">{state.message}</p>
 {error&&<p role="alert">{error}</p>}
 {state.phase==='downloading'&&<div className="update-progress"><progress aria-label="更新下载进度" max={100} value={progress}/><span>{progress}% · {bytes(state.received||0)} / {bytes(state.total||0)}</span></div>}
 <div className="button-row">
 {state.phase==='ready'?<button className="primary-button" disabled={action} onClick={()=>void run(async()=>{await flushUpdateDrafts();await window.jobfindsme!.installUpdate();})}>重启并安装</button>
 :state.phase==='downloading'?<button onClick={()=>void window.jobfindsme!.cancelUpdate()}>取消下载</button>
 :!running&&(state.phase==='available'||state.phase==='error'||state.phase==='cancelled'||state.phase==='rolled_back')?<button className="primary-button" disabled={action||state.phase==='available'&&state.canInstall===false} onClick={()=>void run(()=>window.jobfindsme!.downloadUpdate())}>{state.phase==='available'?'下载更新':'重新下载'}</button>:null}
 {!running&&state.phase!=='ready'&&<button disabled={action} className={state.phase==='idle'?'primary-button':undefined} onClick={()=>void run(()=>window.jobfindsme!.checkForUpdates())}>检查更新</button>}
 <button disabled={state.phase==='installing'} onClick={()=>void window.jobfindsme!.openReleases()}>发布说明</button>
 </div></div><p className="update-preservation">更新只替换程序，保留本机简历、草稿和登录会话。安装或启动失败时恢复旧程序；不会上传个人资料。</p>
 <details><summary>构建信息</summary><p>{buildInfo.label}</p></details></section>;
}
