import {type FormEvent, useEffect, useRef, useState} from "react";
import {createPortal} from "react-dom";
import type {ModelConnection, ModelConnectionInput, ModelProtocol} from "../../../shared/contracts";
import {userError} from "../../../shared/user-errors";
import {Icon} from "../shared/Icon";
import {getCurrentModel, setCurrentModel} from "./current-model";
import {modelPresets, protocolNames} from "./model-presets";

const emptyForm = (): ModelConnectionInput => ({provider:"DeepSeek", protocol:"openai_compatible", endpoint:"https://api.deepseek.com", model_id:"", api_key:"", auth_mode:"api_key"});
const statusLabels = {unverified:"尚未测试", testing:"测试中", verified:"上次测试通过", failed:"上次测试失败", cancelled:"测试已取消"};

export function ModelsPage({workspaceId, onError}: {workspaceId?:string; onError(message?:string):void}) {
  const [connections, setConnections] = useState<ModelConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [testing, setTesting] = useState<string>();
  const [saving, setSaving] = useState(false);
  const [authorizing, setAuthorizing] = useState(false);
  const [keyBlocked, setKeyBlocked] = useState(false);
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");
  const [selected, setSelected] = useState<string|null>(()=>getCurrentModel(workspaceId));
  const [form, setForm] = useState<ModelConnectionInput>(emptyForm);
  const dialog = useRef<HTMLDialogElement>(null);
  const busy = saving || Boolean(testing) || authorizing;
  const operation = useRef(false);
  const preset = modelPresets.find(item=>item.name===form.provider);

  useEffect(()=>{setSelected(getCurrentModel(workspaceId));},[workspaceId]);
  useEffect(()=>{
    let cancelled = false;
    // Read metadata only. Opening settings must never request OS keychain access.
    void window.jobfindsme!.listModelConnections().then(items=>{if(!cancelled){setConnections(items);setLoading(false);}})
      .catch(error=>{if(!cancelled){setLoading(false);setProblem(userError(error).message);}});
    return ()=>{cancelled=true;};
  },[]);
  useEffect(()=>{if(editing && !dialog.current?.open){dialog.current?.showModal();dialog.current?.querySelector("select")?.focus();}},[editing]);
  function closeEditor(){dialog.current?.close();setEditing(false);}

  function clearFeedback(){setNotice("");setProblem("");onError(undefined);}
  function fail(error:unknown){
    const raw = error instanceof Error ? error.message : String(error);
    if(/assistant_failure:model_key|安全存储|safeStorage|ciphertext/i.test(raw)){
      setKeyBlocked(true);
      setProblem("未获得钥匙串访问权限。已暂停重复尝试，请重新授权后再测试连接。");
    } else setProblem(userError(error).message);
  }
  async function runTest(connectionId:string):Promise<ModelConnection|undefined>{
    setTesting(connectionId);setNotice("正在测试连接…");
    try {
      const tested = await window.jobfindsme!.testModelConnection(connectionId);
      setConnections(items=>items.map(item=>item.connection_id===connectionId?{...tested,has_api_key:item.has_api_key}:item));
      if(tested.status==="verified") {setKeyBlocked(false);setNotice("连接测试通过。");}
      else {setNotice("");setProblem(tested.last_error?userError(tested.last_error).message:"连接未通过测试，请检查模型 ID、地址与密钥。");}
      return tested;
    } catch(error) {
      try {setConnections(await window.jobfindsme!.listModelConnections());} catch { /* Preserve the visible saved configuration. */ }
      setNotice("");fail(error);return undefined;
    } finally {setTesting(undefined);}
  }
  async function test(connectionId:string){
    if(operation.current)return;
    operation.current=true;clearFeedback();
    try {await runTest(connectionId);} finally {operation.current=false;}
  }
  async function retryAuthorization(){
    if(operation.current)return;
    operation.current=true;clearFeedback();setAuthorizing(true);
    try {
      const available = await window.jobfindsme!.secureStorageAvailable(true);
      setKeyBlocked(!available);
      if(available)setNotice("已允许重新尝试。请测试连接；如出现系统授权窗口，请由你确认。");
      else setProblem("系统钥匙串仍不可用。请确认登录钥匙串已解锁，再重新授权。");
    } catch(error){fail(error);} finally {setAuthorizing(false);operation.current=false;}
  }
  async function save(event:FormEvent){
    event.preventDefault();if(operation.current)return;
    operation.current=true;setSaving(true);clearFeedback();
    try {
      const saved=await window.jobfindsme!.saveModelConnection(form);
      setConnections(items=>[saved,...items.filter(item=>item.connection_id!==saved.connection_id)]);
      setForm(value=>({...value,connection_id:saved.connection_id,api_key:""}));
      const tested=await runTest(saved.connection_id);
      if(tested?.status==="verified")closeEditor();
    } catch(error){fail(error);} finally {setSaving(false);operation.current=false;}
  }
  function edit(connection?:ModelConnection){
    clearFeedback();setForm(connection?{connection_id:connection.connection_id,provider:connection.provider,protocol:connection.protocol,endpoint:connection.endpoint,model_id:connection.model_id,auth_mode:connection.auth_mode??"api_key",api_key:""}:emptyForm());setEditing(true);
  }
  function choose(connection:ModelConnection){
    if(connection.status!=="verified")return;
    setCurrentModel(workspaceId,connection.connection_id);setSelected(connection.connection_id);clearFeedback();setNotice(`已使用 ${connection.model_id}。`);
  }
  function feedback(){return <>
    {problem&&<div className="model-feedback model-feedback-error" role="alert"><span>{problem}</span>{keyBlocked&&<button type="button" disabled={busy} onClick={()=>void retryAuthorization()}>{authorizing?"授权中…":"重新授权"}</button>}</div>}
    {notice&&<p className="model-feedback" role="status">{notice}</p>}
  </>;}
  return <div className="models-page">
    <header className="model-page-heading"><div><h1>模型设置</h1><p>为求职助手连接模型。找岗位无需配置。</p></div><button className="model-add-button" type="button" disabled={busy} onClick={()=>edit()}><Icon name="add"/>添加模型</button></header>
    {loading?<p className="muted">正在读取连接…</p>:connections.length?<div className="model-cards">{connections.map(connection=><article className="model-card" key={connection.connection_id}>
      <div className="model-card-heading"><span className="model-provider-mark" aria-hidden="true"><Icon name="models"/></span><div className="model-card-title"><h2>{connection.model_id}</h2><span>{connection.provider}</span></div>{selected===connection.connection_id&&<span className="model-current">使用中</span>}</div>
      <p className="model-endpoint">{connection.endpoint}</p>
      <div className="model-card-meta"><span>{connection.auth_mode==="none"?"本机免密":connection.has_api_key?"密钥已加密保存":"尚未保存密钥"}</span><span className={connection.status==="failed"?"model-test-failed":""}>{statusLabels[connection.status]}{connection.last_tested_at&&` · ${new Date(connection.last_tested_at).toLocaleDateString()}`}</span></div>
      <div className="model-card-actions"><button type="button" disabled={busy} onClick={()=>edit(connection)}>编辑</button>{selected!==connection.connection_id&&<button type="button" disabled={busy||connection.status!=="verified"} onClick={()=>choose(connection)}>使用此模型</button>}<button type="button" disabled={busy||(!connection.has_api_key&&connection.auth_mode!=="none")} onClick={()=>void test(connection.connection_id)}>{testing===connection.connection_id?"测试中…":"测试连接"}</button>{testing===connection.connection_id&&<button type="button" onClick={()=>void window.jobfindsme!.cancelModelTest()}>取消测试</button>}</div>
    </article>)}</div>:<div className="model-empty"><Icon name="models"/><h2>连接你的第一个模型</h2><p>支持 DeepSeek、其他 API 服务和本地模型。</p><button type="button" className="primary-button" onClick={()=>edit()}>添加模型</button></div>}
    {!editing&&feedback()}
    <footer className="model-page-footer"><span>密钥加密保存在本机。连接测试可能产生少量费用。</span><button type="button" disabled={busy} onClick={()=>void retryAuthorization()}>{authorizing?"授权中…":"钥匙串授权"}</button></footer>
    {editing&&createPortal(<dialog ref={dialog} className="model-dialog" aria-labelledby="model-dialog-title" onCancel={event=>{event.preventDefault();if(!busy)closeEditor();}}>
      <form className="model-form" onSubmit={event=>void save(event)}>
        <header className="model-dialog-heading"><div><h2 id="model-dialog-title">{form.connection_id?"编辑模型":"添加模型"}</h2><p>填写服务商提供的连接信息。</p></div><button type="button" aria-label="关闭编辑" disabled={busy} onClick={closeEditor}>×</button></header>
        <fieldset disabled={busy} className="model-form-fields">
          <div className="model-form-pair"><label>模型服务<select autoFocus value={preset?form.provider:"自定义"} onChange={event=>{const next=modelPresets.find(item=>item.name===event.target.value)!;setForm({connection_id:form.connection_id,provider:next.name,protocol:next.protocol,endpoint:next.endpoint,model_id:"",api_key:"",auth_mode:next.local?"none":"api_key"});clearFeedback();}}>{modelPresets.map(item=><option key={item.name}>{item.name}</option>)}</select></label>
          <label>模型 ID<input value={form.model_id} onChange={event=>setForm({...form,model_id:event.target.value})} placeholder="例如 deepseek-flash" required/></label></div>
          {preset?.note&&<p className="model-field-note">{preset.note}</p>}
          {preset?.local?<label>本地服务地址<input type="url" value={form.endpoint} onChange={event=>setForm({...form,endpoint:event.target.value})} required/></label>:form.auth_mode!=="none"&&<label>API Key<input type="password" autoComplete="off" value={form.api_key} onChange={event=>setForm({...form,api_key:event.target.value})} placeholder={form.connection_id?"留空保留原有密钥":"粘贴你的 API Key"}/></label>}
          <details className="model-advanced"><summary>高级选项</summary><label>协议<select value={form.protocol} onChange={event=>setForm({...form,protocol:event.target.value as ModelProtocol})}>{Object.entries(protocolNames).map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label><label>API 基础地址<input type="url" value={form.endpoint} onChange={event=>setForm({...form,endpoint:event.target.value})} required/></label><label>认证方式<select value={form.auth_mode??"api_key"} onChange={event=>setForm({...form,auth_mode:event.target.value as "api_key"|"none",api_key:""})}><option value="api_key">API Key</option><option value="none">本机免密</option></select></label></details>
        </fieldset>
        {feedback()}
        <footer className="model-dialog-footer"><p>测试会发送一次最小请求，服务商可能计费。</p><div>{testing&&<button type="button" onClick={()=>void window.jobfindsme!.cancelModelTest().catch(fail)}>取消测试</button>}<button type="button" disabled={busy} onClick={closeEditor}>取消</button><button className="primary-button" disabled={busy}>{saving?"保存并测试中…":"保存并测试"}</button></div></footer>
      </form>
    </dialog>,document.body)}
  </div>;
}
