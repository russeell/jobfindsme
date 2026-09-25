export type ResearchRun={runId:string;sessionId:string;workspaceId:string;signal:AbortSignal};

export class ResearchRunController{
  private active?:ResearchRun & {controller:AbortController;timer:ReturnType<typeof setTimeout>};
  get current():ResearchRun|undefined{return this.active;}
  begin(input:{runId:string;sessionId:string;workspaceId:string},timeoutMs:number):ResearchRun{
    if(this.active)throw Error("已有对话正在生成，请先取消。");
    const controller=new AbortController();
    const run={...input,controller,signal:controller.signal,timer:setTimeout(()=>this.cancel(input.runId),timeoutMs)};
    this.active=run;
    return run;
  }
  cancel(runId:string):boolean{
    const run=this.active;
    if(!run||run.runId!==runId)return false;
    this.active=undefined;
    clearTimeout(run.timer);
    run.controller.abort();
    return true;
  }
  cancelCurrent():boolean{
    return this.active?this.cancel(this.active.runId):false;
  }
  finish(run:ResearchRun):void{
    if(this.active!==run)return;
    clearTimeout(this.active.timer);
    this.active=undefined;
  }
}
