import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import type { SecretStorageMode } from "../../shared/contracts";

// Legacy strings are always OS-encrypted ciphertext. File storage uses an
// explicit tag and is written only after the caller obtains user consent.
type StoredSecret = string | { encoding: "local_file"; value: string };

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

  set(secretRef: string, secret: string, mode: SecretStorageMode = "system"): void {
    if (mode !== "system" && mode !== "local_file") throw new Error("无效的密钥保存方式。");
    if (mode === "local_file") {
      const values = this.read();
      values[secretRef] = { encoding: "local_file", value: secret };
      this.writeAtomically(values);
      this.decrypted.delete(secretRef);
      return;
    }
    if (!this.isAvailable()) {
      throw new Error("系统安全存储不可用，未保存 API Key。");
    }
    const values = this.read();
    let encrypted: string;
    try { encrypted = this.encryption.encryptString(secret).toString("base64"); }
    catch {
      this.availability = false;
      throw new Error("assistant_failure:model_key");
    }
    values[secretRef] = encrypted;
    this.writeAtomically(values);
    this.decrypted.set(secretRef, { encrypted, secret });
  }

  delete(secretRef: string): void {
    const values = this.read();
    if (!(secretRef in values)) { this.decrypted.delete(secretRef); return; }
    delete values[secretRef];
    this.writeAtomically(values);
    this.decrypted.delete(secretRef);
  }

  async withoutSecret<T>(secretRef: string, commit: () => Promise<T>): Promise<T> {
    // Remove the stored entry without decrypting or requesting keychain access.
    // On database failure, restore the exact original entry and its encoding.
    const encrypted = this.read()[secretRef];
    const cached = this.decrypted.get(secretRef);
    this.delete(secretRef);
    try { return await commit(); }
    catch (error) {
      if (encrypted) {
        const values = this.read();
        values[secretRef] = encrypted;
        this.writeAtomically(values);
        if (cached?.encrypted === encrypted) this.decrypted.set(secretRef, cached);
      }
      throw error;
    }
  }

  private writeAtomically(values: Record<string, StoredSecret>): void {
    const directory = path.dirname(this.filePath);
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
    fs.chmodSync(directory, 0o700);
    const temporaryPath = `${this.filePath}.${randomUUID()}.tmp`;
    const descriptor = fs.openSync(temporaryPath, "wx", 0o600);
    try {
      try {
        fs.writeFileSync(descriptor, JSON.stringify(values));
        fs.fsyncSync(descriptor);
      } finally {
        fs.closeSync(descriptor);
      }
      fs.renameSync(temporaryPath, this.filePath);
    } finally {
      if (fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath);
    }
    fs.chmodSync(this.filePath, 0o600);
  }

  get(secretRef: string): string | undefined {
    const encrypted = this.read()[secretRef];
    if (!encrypted) { this.decrypted.delete(secretRef); return undefined; }
    if (typeof encrypted !== "string") {
      this.decrypted.delete(secretRef);
      // Repair permissions before exposing a file-stored key on POSIX. This
      // mode is owner-readable plaintext, not an OS-encryption substitute.
      fs.chmodSync(path.dirname(this.filePath), 0o700);
      fs.chmodSync(this.filePath, 0o600);
      return encrypted.value;
    }
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

  storageMode(secretRef: string): SecretStorageMode | undefined {
    const value = this.read()[secretRef];
    return value ? (typeof value === "string" ? "system" : "local_file") : undefined;
  }

  private read(): Record<string, StoredSecret> {
    if (!fs.existsSync(this.filePath)) return {};
    try {
      const parsed: unknown = JSON.parse(fs.readFileSync(this.filePath, "utf8"));
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid store");
      const entries = Object.entries(parsed);
      if (entries.some(([, value]) => typeof value !== "string" && (
        !value || typeof value !== "object" || Array.isArray(value)
        || value.encoding !== "local_file" || typeof value.value !== "string"
      ))) throw new Error("invalid credential encoding");
      return Object.fromEntries(entries) as Record<string, StoredSecret>;
    } catch {
      throw new Error("无法读取本地密钥存储。");
    }
  }
}
