import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { safeStorage } from "electron";

export class SecureSecretStore {
  private readonly filePath: string;

  constructor(userDataPath: string) {
    this.filePath = path.join(userDataPath, "secrets", "model-keys.json");
  }

  isAvailable(): boolean {
    return safeStorage.isEncryptionAvailable();
  }

  set(secretRef: string, secret: string): void {
    if (!this.isAvailable()) {
      throw new Error("系统安全存储不可用，未保存 API Key。");
    }
    const values = this.read();
    values[secretRef] = safeStorage.encryptString(secret).toString("base64");
    this.writeAtomically(values);
  }

  delete(secretRef: string): void {
    const values = this.read();
    if (!(secretRef in values)) return;
    delete values[secretRef];
    this.writeAtomically(values);
  }

  private writeAtomically(values: Record<string, string>): void {
    const directory = path.dirname(this.filePath);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    fs.chmodSync(directory, 0o700);
    const temporaryPath = `${this.filePath}.${randomUUID()}.tmp`;
    const descriptor = fs.openSync(temporaryPath, "wx", 0o600);
    try {
      fs.writeFileSync(descriptor, JSON.stringify(values));
      fs.fsyncSync(descriptor);
    } finally {
      fs.closeSync(descriptor);
    }
    try {
      fs.renameSync(temporaryPath, this.filePath);
    } finally {
      if (fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath);
    }
    fs.chmodSync(this.filePath, 0o600);
  }

  get(secretRef: string): string | undefined {
    const encrypted = this.read()[secretRef];
    if (!encrypted || !this.isAvailable()) return undefined;
    return safeStorage.decryptString(Buffer.from(encrypted, "base64"));
  }

  has(secretRef: string): boolean {
    return Boolean(this.read()[secretRef]);
  }

  private read(): Record<string, string> {
    if (!fs.existsSync(this.filePath)) return {};
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(this.filePath, "utf8"));
      return parsed && typeof parsed === "object"
        ? (parsed as Record<string, string>)
        : {};
    } catch {
      throw new Error("无法读取本地密钥存储。");
    }
  }
}
