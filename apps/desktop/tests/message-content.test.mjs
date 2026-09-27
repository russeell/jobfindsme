import test from 'node:test';
import assert from 'node:assert/strict';
import {parseMessageBlocks,safeMessageUrl,tokenizeMessageInline} from '../dist-electron/shared/message-content.js';

test('message blocks retain quote, list, table and code without interpreting raw HTML',()=>{
 const blocks=parseMessageBlocks('# 标题\n\n> 引用\n\n- 条目\n\n| 岗位 | 地点 |\n| --- | --- |\n| 开发 | 上海 |\n\n```js\n<script>alert(1)</script>\n```');
 assert.deepEqual(blocks.map(block=>block.kind),['heading','quote','list','table','code']);
 assert.equal(blocks.at(-1).text,'<script>alert(1)</script>');
});
test('inline parser keeps citations distinct from links and rejects unsafe protocols',()=>{
 const parts=tokenizeMessageInline('**重点** [1] [1](https://attacker.example/false) [查看](https://example.com/a) [危险](javascript:alert)');
 assert(parts.some(part=>part.kind==='strong'));
 assert.equal(parts.filter(part=>part.kind==='citation'&&part.number===1).length,2);
 assert(parts.some(part=>part.kind==='link'&&part.url==='https://example.com/a'));
 assert.equal(parts.filter(part=>part.kind==='link').length,1);
 const boldCitation=tokenizeMessageInline('**[1]**')[0];assert.equal(boldCitation.kind,'strong');assert.equal(tokenizeMessageInline(boldCitation.text)[0].kind,'citation');
 assert.equal(safeMessageUrl('data:text/html,<script>'),undefined);
});
