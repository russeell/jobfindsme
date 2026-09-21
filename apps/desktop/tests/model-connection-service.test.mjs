import assert from "node:assert/strict";
import test from "node:test";

import { saveModelConnectionWithSecret } from "../dist-electron/main/model-connection-service.js";

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
