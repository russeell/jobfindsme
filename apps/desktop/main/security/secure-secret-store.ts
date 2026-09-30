import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

type EncryptionProvider = {
  isEncryptionAvailable(): boolean;
  encryptString(value: string): Buffer;
  decryptString(value: Buffer): string;
};

export class SecureSecretStore {
  private readonly filePath: string;
  private availability: boolean | undefined;
  private readonly decrypted = new Map<string, { encrypted: string; secret: string }>();

  constructor(userDataPath: string, private readonly encryption: EncryptionProvider) {
    this.filePath = path.join(userDataPath, "secrets", "model-keys.json");
  }

  // Availability may initialize the OS keychain. Cache denial as well as success;
  // only a deliberate user retry should invoke the provider again.
  isAvailable(retry = false): boolean {
    if (retry) this.availability = undefined;
    if (this.availability === undefined) {
      try { this.availability = this.encryption.isEncryptionAvailable(); }
      catch { this.availability = false; }
    }
    return this.availability;
  }

  set(secretRef: string, secret: string): void {
    if (!this.isAvailable()) {
      throw new Error("系统安全存储不可用，未保存 API Key。");
    }
    const values = this.read();
    try { values[secretRef] = this.encryption.encryptString(secret).toString("base64"); }
    catch {
      this.availability = false;
      throw new Error("assistant_failure:model_key");
    }
    this.writeAtomically(values);
    this.decrypted.set(secretRef, { encrypted: values[secretRef], secret });
  }

  delete(secretRef: string): void {
    this.decrypted.delete(secretRef);
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
    if (!encrypted) { this.decrypted.delete(secretRef); return undefined; }
    const cached = this.decrypted.get(secretRef);
    if (cached?.encrypted === encrypted) return cached.secret;
    this.decrypted.delete(secretRef);
    if (!this.isAvailable()) throw new Error("assistant_failure:model_key");
    try {
      const secret = this.encryption.decryptString(Buffer.from(encrypted, "base64"));
      this.decrypted.set(secretRef, { encrypted, secret });
      return secret;
    } catch {
      this.availability = false;
      throw new Error("assistant_failure:model_key");
    }
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
