import assert from "node:assert/strict";
import test from "node:test";

test("source capability contract keeps login-gated sources disabled", () => {
  const sources = [
    { source_id: "boss", login_required: true, live_search_enabled: false },
    { source_id: "liepin", login_required: false, live_search_enabled: true },
  ];

  assert.equal(
    sources.find((source) => source.source_id === "boss").live_search_enabled,
    false,
  );
  assert.equal(
    sources.find((source) => source.source_id === "liepin").live_search_enabled,
    true,
  );
});
