/** Share read-only work while each caller owns its cancellation and wait budget. */
export class SharedFlight<T> {
  private entries = new Map<string,{controller:AbortController;promise:Promise<T>;waiters:number}>();
  run(key:string,work:(signal:AbortSignal)=>Promise<T>,signal?:AbortSignal,ms=21000,timeoutError=()=>Error('source_timeout:读取等待超时')):Promise<T>{
    if(signal?.aborted)return Promise.reject(Error('cancelled'));
    if(ms<=0)return Promise.reject(Error('source_timeout:读取预算已用完'));
    let entry=this.entries.get(key);
    if(!entry){
      const controller=new AbortController();
      entry={controller,promise:Promise.resolve().then(()=>{if(controller.signal.aborted)throw Error('cancelled');return work(controller.signal);}),waiters:0};
      this.entries.set(key,entry);
      const owned=entry;
      void entry.promise.finally(()=>{if(this.entries.get(key)===owned)this.entries.delete(key);}).catch(()=>{});
    }
    const owned=entry;owned.waiters++;
    return new Promise<T>((resolve,reject)=>{
      let settled=false;let timer:ReturnType<typeof setTimeout>;
      const finish=(error:unknown,value?:T)=>{
        if(settled)return;settled=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);owned.controller.signal.removeEventListener('abort',abort);
        owned.waiters--;
        if(!owned.waiters){if(this.entries.get(key)===owned)this.entries.delete(key);owned.controller.abort();}
        if(error)reject(error);else resolve(structuredClone(value!));
      };
      const abort=()=>finish(Error('cancelled'));
      timer=setTimeout(()=>finish(timeoutError()),ms);
      signal?.addEventListener('abort',abort,{once:true});owned.controller.signal.addEventListener('abort',abort,{once:true});
      owned.promise.then(value=>finish(null,value),error=>finish(error));
      if(signal?.aborted)abort();
    });
  }
  cancelAll(){for(const entry of this.entries.values())entry.controller.abort();this.entries.clear();}
}
