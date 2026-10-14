import test from 'node:test';
import assert from 'node:assert/strict';
import {exportSelectedResume} from '../dist-electron/shared/resume-export.js';

function fixture(version,{cancel=false,lookupError=false}={}){
 const calls=[];
 const bridge={
  async getResumeVersion(workspace,id){calls.push(['get',workspace,id]);if(lookupError)throw Error('workspace mismatch');return version;},
  async exportResumeSource(input){calls.push(['source',input]);return !cancel;},
  async exportResume(input){calls.push(['edited',input]);return cancel?undefined:{template:'campus'};},
 };
 return {bridge,calls};
}
test('archived original is looked up by its exact version and exported from its source',async()=>{
 const {bridge,calls}=fixture({version_id:'archived-original',original_file:true,source_document_id:'original-pdf',hidden:true});
 assert.equal(await exportSelectedResume(bridge,'workspace','archived-original'),true);
 assert.deepEqual(calls,[['get','workspace','archived-original'],['source',{workspace_id:'workspace',document_id:'original-pdf'}]]);
});
test('edited export uses the selected old version and its saved layout',async()=>{
 const {bridge,calls}=fixture({version_id:'old-campus',original_file:false,document:{attrs:{template:'campus'}}});
 assert.equal(await exportSelectedResume(bridge,'workspace','old-campus'),true);
 assert.deepEqual(calls,[['get','workspace','old-campus'],['edited',{workspace_id:'workspace',version_id:'old-campus',format:'pdf'}]]);
});
test('cancelled native saves are not reported as successful',async()=>{
 for(const version of [{original_file:true,source_document_id:'original-pdf'},{original_file:false}]){
  const {bridge}=fixture(version,{cancel:true});
  assert.equal(await exportSelectedResume(bridge,'workspace','selected'),false);
 }
});
test('failed lookup or missing original source never falls back to a converted or current resume',async()=>{
 for(const [version,options] of [[{}, {lookupError:true}],[{original_file:true},{}]]){
  const {bridge,calls}=fixture(version,options);
  await assert.rejects(exportSelectedResume(bridge,'workspace','selected'));
  assert.deepEqual(calls,[['get','workspace','selected']]);
 }
});
