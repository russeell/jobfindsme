import test from 'node:test';
import assert from 'node:assert/strict';
import {addBrowserBookmark,readBrowserBookmarks,removeBrowserBookmark} from '../dist-electron/shared/browser-bookmarks.js';

test('bookmarks survive serialization, deduplicate URLs and preserve titles',()=>{
 const one=addBrowserBookmark([],'https://www.zhaopin.com/jobs','智联岗位');
 assert.equal(addBrowserBookmark(one,'https://www.zhaopin.com/jobs','重复'),one);
 assert.deepEqual(readBrowserBookmarks(JSON.stringify(one)),one);
 assert.deepEqual(removeBrowserBookmark(one,one[0].url),[]);
});

test('invalid and private URLs cannot enter local bookmarks',()=>{
 for(const url of ['file:///tmp/a','http://localhost:3000','https://user:pass@example.com'])assert.throws(()=>addBrowserBookmark([],url,'坏链接'));
 assert.deepEqual(readBrowserBookmarks('[{"url":"file:///tmp/a","title":"bad"}]'),[]);
 assert.deepEqual(readBrowserBookmarks('bad'),[]);
});
