import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveBrowserDestination as resolve,resolveWebsiteHomepage,resolveWebSearch,normalizeSearchEngine} from '../dist-electron/shared/browser-search.js';

test('website action takes only a site and opens its homepage, not login',()=>{
 assert.equal(resolveWebsiteHomepage('').kind,'empty');
 assert.equal(resolveWebsiteHomepage('boss').url,'https://www.zhipin.com/');
 assert.equal(resolveWebsiteHomepage('liepin').url,'https://www.liepin.com/');
 assert.equal(resolveWebsiteHomepage('liepin').sourceId,'liepin');
});
test('top address input preserves direct URL normalization and target partition',()=>{
 assert.equal(resolve('  ','bing').kind,'empty');
 const r=resolve('https://www.liepin.com/job/123.shtml','bing');
 assert.equal(r.kind,'url');assert.equal(r.sourceId,'liepin');
 assert.equal(resolve('example.com/path?q=中文','bing').sourceId,'web');
 assert.equal(resolve('example.com/path?q=中文','bing').url,'https://example.com/path?q=%E4%B8%AD%E6%96%87');
});
test('all engines search full keywords without inheriting a website selection',()=>{
 const home=resolveWebsiteHomepage('liepin');
 for(const engine of ['bing','baidu','google']){
  const text='AI: 工程师 C++ & R&D / 远程 #上海 + 100%';
  const r=resolveWebSearch(text,engine),url=new URL(r.url),key=engine==='baidu'?'wd':'q';
  assert.equal(r.kind,'search');assert.equal(r.sourceId,'web');assert.equal(url.searchParams.get(key),text);
  assert.equal(url.hostname,{bing:'www.bing.com',baidu:'www.baidu.com',google:'www.google.com'}[engine]);
 }
 assert.equal(home.url,resolveWebsiteHomepage('liepin').url);
 assert.equal(resolveWebSearch('','google').kind,'empty');
});
test('dangerous and malformed URLs stay rejected in top address and search inputs',()=>{
 for(const text of ['javascript:alert(1)','data:text/html,test','file:///tmp/a','about:blank','ftp://example.com','https:/example.com','https://','https://bad host.com','http://localhost:123','localhost:3000','127.0.0.1','https://user:pass@example.com','//example.com','http ://example.com','custom:payload','https://example.com\n/secret']){
  assert.equal(resolve(text,'bing').kind,'invalid',text);
  assert.equal(resolveWebSearch(text,'google').kind,'invalid',text);
 }
});
test('engine preference remains compatible; top input Bing remains independent',()=>{
 assert.equal(resolveWebSearch('example.com','google').kind,'search');
 for(const old of ['bing','baidu','google'])assert.equal(normalizeSearchEngine(old),old);
 for(const invalid of [null,'old-value'])assert.equal(normalizeSearchEngine(invalid),'bing');
 assert.equal(new URL(resolve('AI 工程师','bing').url).hostname,'www.bing.com');
});
