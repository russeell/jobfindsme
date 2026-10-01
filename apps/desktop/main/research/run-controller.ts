export type ResearchRun={runId:string;sessionId:string;workspaceId:string;signal:AbortSignal};
type OwnedRun=ResearchRun & {controller:AbortController;timer:ReturnType<typeof setTimeout>};
export class ResearchRunController{
  private active=new Map<string,OwnedRun>();
  get current():ResearchRun|undefined{return this.active.values().next().value;}
  has(run:ResearchRun):boolean{return this.active.get(run.runId)===run;}
  forSession(workspaceId:string,sessionId:string):ResearchRun|undefined{return [...this.active.values()].find(run=>run.workspaceId===workspaceId&&run.sessionId===sessionId);}
  begin(input:{runId:string;sessionId:string;workspaceId:string},timeoutMs:number):ResearchRun{
    if(this.active.has(input.runId)||this.forSession(input.workspaceId,input.sessionId))throw Error("该对话正在生成，请先停止或使用另一条聊天。");
    if(this.active.size>=4)throw Error("chat_concurrency_limit");
    const controller=new AbortController();
    const run={...input,controller,signal:controller.signal,timer:setTimeout(()=>this.cancel(input.runId),timeoutMs)};
    this.active.set(input.runId,run);return run;
  }
  cancel(runId:string):boolean{
    const run=this.active.get(runId);if(!run)return false;
    this.active.delete(runId);clearTimeout(run.timer);run.controller.abort();return true;
  }
  cancelCurrent():boolean{
    const runs=[...this.active.keys()];for(const id of runs)this.cancel(id);return runs.length>0;
  }
  finish(run:ResearchRun):void{
    if(!this.has(run))return;const owned=this.active.get(run.runId)!;
    clearTimeout(owned.timer);this.active.delete(run.runId);
  }
}
