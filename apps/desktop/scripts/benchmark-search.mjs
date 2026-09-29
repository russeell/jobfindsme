import {collectBrowserSourcePages} from '../dist-electron/main/sources/source-search-coordinator.js';
import {performance,monitorEventLoopDelay} from 'node:perf_hooks';
const ids=['boss','liepin','zhilian','wuyou'],durations={boss:120,liepin:220,zhilian:80,wuyou:160};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const results=[];
// Alternate runs to reduce warmup bias; this does not access recruitment websites.
for(const concurrency of [2,4,4,2,2,4,4,2,2,4]){
 let first=null,pages=0;const cpu=process.cpuUsage(),memory=process.memoryUsage().rss,loop=monitorEventLoopDelay({resolution:10});loop.enable();const start=performance.now();
 const read=async id=>{pages++;await wait(durations[id]);return {records:[{external_id:id,source_name:id,source_url:'https://example.org/',payload:{title:'Agent工程师'}}],next_cursor:null};};
 const result=await collectBrowserSourcePages({workspace_id:'offline',source_ids:ids,intent:'Agent工程师'}, {allowed_source_ids:ids,keywords:['Agent工程师'],max_pages:1,time_budget_seconds:5},{concurrency,isCancelled:()=>false,client:{publicSourcePages:async id=>[await read(id)]},manager:{boss:{collect:()=>read('boss')},searchPage:id=>read(id)},onSourceCompleted:async()=>{await wait(5);if(first===null)first=performance.now()-start;}});
 loop.disable();const used=process.cpuUsage(cpu);results.push({concurrency,first_usable_ms:Math.round(first),total_elapsed_ms:Math.round(performance.now()-start),source_ms:Object.fromEntries(Object.entries(result.diagnostics.sources).map(([k,v])=>[k,v.elapsed_ms])),pages,cpu_ms:(used.user+used.system)/1000,rss_delta_mb:(process.memoryUsage().rss-memory)/1048576,node_loop_p99_ms:loop.percentile(99)/1e6,failures:Object.keys(result.errors).length});
}
console.log(JSON.stringify({kind:'offline fixed-delay fixture, not actual platform/UI benchmark',results},null,2));
