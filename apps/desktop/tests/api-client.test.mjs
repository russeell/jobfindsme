import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { DesktopApiClient } = require("../dist-electron/main/backend/api-client.js");

test("resume export keeps the path version out of the strict request body", async () => {
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, init };
    return new Response(JSON.stringify({
      path: "/tmp/resume.md",
      workspace_id: "workspace-1",
      version_id: "version-1",
      format: "md",
      template: "classic",
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    const client = new DesktopApiClient("http://127.0.0.1:43123", "secret");
    await client.exportResume({
      workspace_id: "workspace-1",
      version_id: "version-1",
      format: "md",
      template: "classic",
    }, "/tmp/resume.md");
    assert.equal(request.url, "http://127.0.0.1:43123/v1/resume-versions/version-1/export");
    assert.deepEqual(JSON.parse(request.init.body), {
      workspace_id: "workspace-1",
      destination: "/tmp/resume.md",
      format: "md",
      template: "classic",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("validation errors are rendered as readable messages", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    detail: [{ loc: ["body", "version_id"], msg: "Extra inputs are not permitted" }],
  }), { status: 422, headers: { "Content-Type": "application/json" } });
  try {
    const client = new DesktopApiClient("http://127.0.0.1:43123", "secret");
    await assert.rejects(
      client.exportResume({
        workspace_id: "workspace-1",
        version_id: "version-1",
        format: "md",
        template: "classic",
      }, "/tmp/resume.md"),
      /body\.version_id: Extra inputs are not permitted/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
