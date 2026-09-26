import assert from "node:assert/strict";
import path from "node:path";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { PythonService, resolvePythonLaunch } = require("../dist-electron/main/backend/python-service.js");

test("packaged runtime resolves inside app resources without source checkout", () => {
  assert.deepEqual(
    resolvePythonLaunch({
      packaged: true,
      resourcesPath: "/Applications/JobFindsMe.app/Contents/Resources",
      projectRoot: "/unavailable/source",
    }),
    {
      executable: path.join("/Applications/JobFindsMe.app/Contents/Resources", "python", "jobfindsme-api", process.platform === "win32" ? "jobfindsme-api.exe" : "jobfindsme-api"),
      cwd: path.join("/Applications/JobFindsMe.app/Contents/Resources", "python"),
      moduleArgs: [],
    },
  );
});

test("development runtime invokes the desktop API as a Python module", () => {
  assert.deepEqual(
    resolvePythonLaunch({
      packaged: false,
      projectRoot: "/checkout/jobfindsme",
      pythonPath: "/checkout/jobfindsme/.venv/bin/python",
    }),
    {
      executable: "/checkout/jobfindsme/.venv/bin/python",
      cwd: "/checkout/jobfindsme",
      moduleArgs: ["-m", "jobfindsme.desktop_api"],
    },
  );
});

class FakeChild extends EventEmitter {
  constructor({ exitOn = "SIGTERM", exitDelayMs = 0 } = {}) {
    super();
    this.exitCode = null;
    this.signalCode = null;
    this.pid = 1234;
    this.stdout = new PassThrough();
    this.stderr = new PassThrough();
    this.exitOn = exitOn;
    this.exitDelayMs = exitDelayMs;
    this.kills = [];
  }

  kill(signal) {
    this.kills.push(signal);
    if (signal === this.exitOn) {
      setTimeout(() => this.forceExit(null, signal), this.exitDelayMs);
    }
    return true;
  }

  forceExit(code, signal = null) {
    if (this.exitCode !== null || this.signalCode !== null) return;
    this.exitCode = code;
    this.signalCode = signal;
    this.emit("exit", code, signal);
  }
}

function spawnFake(child) {
  return () => {
    queueMicrotask(() => child.emit("spawn"));
    return child;
  };
}

function serviceOptions(overrides = {}) {
  return {
    projectRoot: "/tmp/jobfindsme-test",
    userDataPath: "/tmp/jobfindsme-test-data",
    reservePort: async () => 43123,
    createClient: () => ({ health: async () => true }),
    terminateGraceMs: 5,
    killWaitMs: 100,
    pollIntervalMs: 1,
    readyTimeoutMs: 100,
    ...overrides,
  };
}

test("stop during port reservation prevents a later spawn", async () => {
  let resolvePort;
  let spawnCount = 0;
  const service = new PythonService(
    serviceOptions({
      reservePort: () => new Promise((resolve) => (resolvePort = resolve)),
      spawnProcess: () => {
        spawnCount += 1;
        return new FakeChild();
      },
    }),
  );

  const starting = service.start();
  const stopping = service.stop();
  resolvePort(43123);

  await assert.rejects(starting, /startup cancelled/);
  await stopping;
  assert.equal(spawnCount, 0);
});

test("stop is idempotent while health is not ready", async () => {
  const child = new FakeChild();
  const service = new PythonService(
    serviceOptions({
      spawnProcess: spawnFake(child),
      createClient: () => ({ health: () => new Promise(() => {}) }),
    }),
  );

  const starting = service.start();
  await new Promise((resolve) => setImmediate(resolve));
  const firstStop = service.stop();
  const secondStop = service.stop();

  assert.equal(firstStop, secondStop);
  await Promise.all([firstStop, secondStop]);
  await assert.rejects(starting, /Python service exited/);
  assert.deepEqual(child.kills, ["SIGTERM"]);
});

test("spawn errors reject start without an unhandled process error", async () => {
  const service = new PythonService(
    serviceOptions({
      pythonPath: "/definitely/missing-jobfindsme-python",
    }),
  );

  await assert.rejects(service.start(), /spawn .*ENOENT/);
  await service.stop();
});

test("stop waits for the child exit after escalating to SIGKILL", async () => {
  const child = new FakeChild({ exitOn: "SIGKILL", exitDelayMs: 20 });
  const service = new PythonService(
    serviceOptions({ spawnProcess: spawnFake(child) }),
  );
  await service.start();

  const startedAt = Date.now();
  await service.stop();

  assert.deepEqual(child.kills, ["SIGTERM", "SIGKILL"]);
  assert.ok(Date.now() - startedAt >= 20);
});

test("unexpected exit after readiness reports a disconnected status", async () => {
  const child = new FakeChild();
  const statuses = [];
  const service = new PythonService(
    serviceOptions({
      spawnProcess: spawnFake(child),
      onStatus: (status) => statuses.push(status),
    }),
  );
  await service.start();

  child.forceExit(1);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(statuses[0].connected, true);
  assert.equal(statuses.at(-1).connected, false);
  assert.match(statuses.at(-1).message, /code 1/);
});
