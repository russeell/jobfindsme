import { type ChildProcess, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createServer } from "node:net";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import { DesktopApiClient } from "./api-client";

const LOOPBACK = "127.0.0.1";

export type ServiceStatus = {
  connected: boolean;
  message?: string;
};

type PythonServiceOptions = {
  projectRoot: string;
  userDataPath: string;
  packaged?: boolean;
  resourcesPath?: string;
  pythonPath?: string;
  spawnProcess?: typeof spawn;
  reservePort?: () => Promise<number>;
  createClient?: (baseUrl: string, token: string) => DesktopApiClient;
  onStatus?: (status: ServiceStatus) => void;
  readyTimeoutMs?: number;
  pollIntervalMs?: number;
  terminateGraceMs?: number;
  killWaitMs?: number;
};

export function resolvePythonLaunch(options: Pick<
  PythonServiceOptions,
  "packaged" | "resourcesPath" | "projectRoot" | "pythonPath"
>): { executable: string; cwd: string; moduleArgs: string[] } {
  if (options.pythonPath) {
    return {
      executable: options.pythonPath,
      cwd: options.projectRoot,
      moduleArgs: ["-m", "jobfindsme.desktop_api"],
    };
  }
  if (options.packaged) {
    if (!options.resourcesPath) {
      throw new Error("packaged Python runtime requires resourcesPath");
    }
    return {
      executable: path.join(options.resourcesPath, "python", "jobfindsme-api", process.platform === "win32" ? "jobfindsme-api.exe" : "jobfindsme-api"),
      cwd: path.join(options.resourcesPath, "python"),
      // PyInstaller's executable already embeds the desktop_api entry point.
      moduleArgs: [],
    };
  }
  return {
    executable: process.env.JFM_PYTHON ?? path.join(options.projectRoot, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python"),
    cwd: options.projectRoot,
    moduleArgs: ["-m", "jobfindsme.desktop_api"],
  };
}

async function reserveLoopbackPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, LOOPBACK, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("could not reserve desktop API port"));
        return;
      }
      server.close((error) => (error ? reject(error) : resolve(address.port)));
    });
  });
}

function exitMessage(code: number | null, signal: NodeJS.Signals | null): string {
  return signal ? `signal ${signal}` : `code ${code ?? "unknown"}`;
}

export class PythonService {
  private child: ChildProcess | undefined;
  private client: DesktopApiClient | undefined;
  private startPromise: Promise<DesktopApiClient> | undefined;
  private stopPromise: Promise<void> | undefined;
  private stopRequested = false;
  private ready = false;
  private stderrTail = "";

  constructor(private readonly options: PythonServiceOptions) {}

  start(): Promise<DesktopApiClient> {
    if (this.startPromise || this.child || this.client) {
      return Promise.reject(new Error("Python service already started"));
    }
    this.stopRequested = false;
    const pending = this.startInternal();
    this.startPromise = pending;
    void pending
      .finally(() => {
        if (this.startPromise === pending) this.startPromise = undefined;
      })
      .catch(() => undefined);
    return pending;
  }

  stop(): Promise<void> {
    this.stopRequested = true;
    if (this.stopPromise) return this.stopPromise;
    const pending = this.stopInternal();
    this.stopPromise = pending;
    void pending
      .finally(() => {
        if (this.stopPromise === pending) this.stopPromise = undefined;
      })
      .catch(() => undefined);
    return pending;
  }

  private async startInternal(): Promise<DesktopApiClient> {
    const port = await (this.options.reservePort ?? reserveLoopbackPort)();
    if (this.stopRequested) throw new Error("Python service startup cancelled");

    const token = randomBytes(32).toString("base64url");
    const launch = resolvePythonLaunch(this.options);
    const database = path.join(this.options.userDataPath, "jobfindsme.db");
    const spawnProcess = this.options.spawnProcess ?? spawn;
    const child = spawnProcess(
      launch.executable,
      [
        ...launch.moduleArgs,
        "--host",
        LOOPBACK,
        "--port",
        String(port),
        "--database",
        database,
      ],
      {
        cwd: launch.cwd,
        windowsHide: true,
        env: { ...process.env, JFM_DESKTOP_TOKEN: token },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    this.child = child;
    this.stderrTail = "";
    child.stdout?.resume();
    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (chunk: string) => {
      this.stderrTail = `${this.stderrTail}${chunk}`.slice(-8_192);
    });

    const spawned = new Promise<void>((resolve) => child.once("spawn", resolve));
    const failed = new Promise<never>((_, reject) => {
      child.once("error", (error) => reject(error));
      child.once("exit", (code, signal) => {
        const wasReady = this.ready;
        const expected = this.stopRequested;
        if (this.child === child) {
          this.child = undefined;
          this.client = undefined;
          this.ready = false;
        }
        if (wasReady && !expected) {
          this.options.onStatus?.({
            connected: false,
            message: `本地服务已退出（${exitMessage(code, signal)}）`,
          });
        }
        reject(
          new Error(
            `Python service exited with ${exitMessage(code, signal)}` +
              (this.stderrTail ? `: ${this.stderrTail.trim()}` : ""),
          ),
        );
      });
    });

    const createClient =
      this.options.createClient ??
      ((baseUrl: string, secret: string) =>
        new DesktopApiClient(baseUrl, secret));
    const client = createClient(`http://${LOOPBACK}:${port}`, token);
    try {
      await Promise.race([spawned, failed]);
      await Promise.race([this.waitUntilReady(client), failed]);
      if (this.stopRequested) throw new Error("Python service startup cancelled");
      this.client = client;
      this.ready = true;
      this.options.onStatus?.({ connected: true });
      return client;
    } catch (error) {
      await this.terminate(child);
      if (this.child === child) this.child = undefined;
      this.client = undefined;
      this.ready = false;
      throw error;
    }
  }

  private async stopInternal(): Promise<void> {
    const child = this.child;
    if (child) await this.terminate(child);

    const starting = this.startPromise;
    if (starting) await starting.catch(() => undefined);

    const spawnedDuringStop = this.child;
    if (spawnedDuringStop && spawnedDuringStop !== child) {
      await this.terminate(spawnedDuringStop);
    }
    this.child = undefined;
    this.client = undefined;
    this.ready = false;
  }

  private async terminate(child: ChildProcess): Promise<void> {
    if (
      child.pid === undefined ||
      child.exitCode !== null ||
      child.signalCode !== null
    ) {
      return;
    }
    const exited = new Promise<void>((resolve) => child.once("exit", () => resolve()));
    child.kill("SIGTERM");
    const graceful = await Promise.race([
      exited.then(() => true),
      delay(this.options.terminateGraceMs ?? 2_000).then(() => false),
    ]);
    if (graceful) return;

    child.kill("SIGKILL");
    const killed = await Promise.race([
      exited.then(() => true),
      delay(this.options.killWaitMs ?? 2_000).then(() => false),
    ]);
    if (!killed) throw new Error("Python service did not exit after SIGKILL");
  }

  private async waitUntilReady(client: DesktopApiClient): Promise<void> {
    // First launch may still require OS checks of bundled native libraries.
    const timeoutMs = this.options.readyTimeoutMs ?? (this.options.packaged ? 60_000 : 10_000);
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (this.stopRequested) throw new Error("Python service startup cancelled");
      try {
        if (await client.health()) return;
      } catch {
        // The loopback listener may not be ready yet.
      }
      await delay(this.options.pollIntervalMs ?? 100);
    }
    throw new Error(`Python service did not become ready within ${timeoutMs} ms`);
  }
}
