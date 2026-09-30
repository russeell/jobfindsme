import assert from "node:assert/strict";
import test from "node:test";

import { saveModelConnectionWithSecret } from "../dist-electron/main/backend/model-connection-service.js";

const existing = {
  connection_id: "connection-1",
  provider: "Old",
  protocol: "openai_compatible",
  endpoint: "https://old.example/v1",
  model_id: "old-model",
  status: "unverified",
  last_error: null,
  last_tested_at: null,
  input_tokens: null,
  output_tokens: null,
  credential_ref: "old-secret",
};

const update = {
  connection_id: "connection-1",
  provider: "New",
  protocol: "openai_compatible",
  endpoint: "https://new.example/v1",
  model_id: "new-model",
  api_key: "new-key",
};

test('unencrypted persistence requires explicit consent and never sends storage policy or keys to SQLite',async()=>{
 let staged=0;let saved=0;
 const api={modelConnection:async()=>existing,saveModelConnection:async input=>{
  saved++;assert.equal('api_key' in input,false);assert.equal('secret_storage' in input,false);assert.equal('allow_unencrypted_storage' in input,false);
  return {...existing,...input};
 }};
 const secrets={set:(ref,key,mode)=>{staged++;assert.equal(mode,'local_file');},delete:()=>{},has:()=>true,storageMode:()=> 'local_file'};
 const input={...update,secret_storage:'local_file'};
 await assert.rejects(saveModelConnectionWithSecret(api,secrets,input,()=> 'new-secret'),/明文保存/);
 await assert.rejects(saveModelConnectionWithSecret(api,secrets,{...input,allow_unencrypted_storage:'true'},()=> 'new-secret'),/明文保存/);
 await assert.rejects(saveModelConnectionWithSecret(api,secrets,{...input,secret_storage:'invalid',allow_unencrypted_storage:true},()=> 'new-secret'),/无效/);
 assert.equal(staged,0);assert.equal(saved,0);
 const result=await saveModelConnectionWithSecret(api,secrets,{...input,allow_unencrypted_storage:true},()=> 'new-secret');
 assert.equal(staged,1);assert.equal(saved,1);assert.equal(result.secret_storage,'local_file');assert.equal(result.has_api_key,true);
});

test('changing only storage selector without a new key leaves the existing encoding unchanged',async()=>{
 const api={modelConnection:async()=>existing,saveModelConnection:async input=>({...existing,...input,credential_ref:existing.credential_ref})};
 const secrets={set:()=>{throw Error('must not migrate');},delete:()=>{throw Error('must not retire');},has:()=>true,storageMode:()=> 'system'};
 const result=await saveModelConnectionWithSecret(api,secrets,{...update,api_key:'',secret_storage:'local_file'},()=> 'new-secret');
 assert.equal(result.secret_storage,'system');assert.equal(result.credential_ref,'old-secret');
});

test("secret staging failure leaves configuration and old pairing untouched", async () => {
  let saveCalled = false;
  const api = {
    modelConnection: async () => existing,
    saveModelConnection: async () => {
      saveCalled = true;
      return existing;
    },
  };
  const secrets = {
    set: () => { throw new Error("disk unavailable"); },
    delete: () => {},
    has: () => true,
  };

  await assert.rejects(
    saveModelConnectionWithSecret(api, secrets, update, () => "new-secret"),
    /disk unavailable/,
  );
  assert.equal(saveCalled, false);
});

test("configuration failure removes staged credential and keeps old credential", async () => {
  const deleted = [];
  const api = {
    modelConnection: async () => existing,
    saveModelConnection: async () => { throw new Error("database unavailable"); },
  };
  const secrets = {
    set: () => {},
    delete: (secretRef) => deleted.push(secretRef),
    has: () => true,
  };

  await assert.rejects(
    saveModelConnectionWithSecret(api, secrets, update, () => "new-secret"),
    /database unavailable/,
  );
  assert.deepEqual(deleted, ["new-secret"]);
});

test("local no-auth configuration never stages a secret and retires the previous reference", async () => {
  const deleted = [];
  const api = {
    modelConnection: async () => existing,
    saveModelConnection: async (input) => {
      assert.equal(input.auth_mode, "none");
      assert.equal(input.credential_ref, undefined);
      assert.equal(input.api_key, undefined);
      return { ...existing, ...input, credential_ref: null };
    },
  };
  const secrets = {
    set: () => { throw new Error("must not store key in no-auth mode"); },
    delete: (ref) => deleted.push(ref),
    has: () => false,
  };
  const result = await saveModelConnectionWithSecret(api, secrets,
    {...update, endpoint:"http://localhost:11434/v1", auth_mode:"none"}, () => "new-secret");
  assert.equal(result.has_api_key, false);
  assert.deepEqual(deleted, ["old-secret"]);
});

test('delete retires the paired credential without decrypting or touching unrelated entries',async()=>{
 const {deleteModelConnectionWithSecret}=await import('../dist-electron/main/backend/model-connection-service.js');
 const calls=[];
 const api={modelConnection:async()=>existing,deleteModelConnection:async id=>calls.push(['database',id])};
 const secrets={withoutSecret:async(ref,commit)=>{calls.push(['secret',ref]);return commit();}};
 await deleteModelConnectionWithSecret(api,secrets,'connection-1');
 assert.deepEqual(calls,[['secret','old-secret'],['database','connection-1']]);
});
