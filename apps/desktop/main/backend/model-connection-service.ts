import type { ModelConnection, ModelConnectionInput, SecretStorageMode } from "../../shared/contracts";

export type ModelConfigurationApi = {
  modelConnection(connectionId: string): Promise<ModelConnection>;
  saveModelConnection(
    input: Omit<ModelConnectionInput, "api_key" | "secret_storage" | "allow_unencrypted_storage">,
  ): Promise<ModelConnection>;
};

export type ModelSecretStore = {
  set(secretRef: string, secret: string, mode?: SecretStorageMode): void;
  delete(secretRef: string): void;
  has(secretRef: string): boolean;
  storageMode?(secretRef: string): SecretStorageMode | undefined;
};

export async function saveModelConnectionWithSecret(
  api: ModelConfigurationApi,
  secrets: ModelSecretStore,
  input: ModelConnectionInput,
  createSecretRef: () => string,
): Promise<ModelConnection> {
  const existing = input.connection_id
    ? await api.modelConnection(input.connection_id)
    : undefined;
  const {
    api_key: apiKey,
    secret_storage: storageMode = "system",
    allow_unencrypted_storage: allowUnencrypted,
    credential_ref: _ignoredCredentialRef,
    ...configuration
  } = input;
  if (storageMode !== "system" && storageMode !== "local_file") throw new Error("无效的密钥保存方式。");
  let stagedCredentialRef: string | undefined;
  if (apiKey && input.auth_mode !== "none") {
    if (storageMode === "local_file" && allowUnencrypted !== true) {
      throw new Error("请先确认：本机文件方式会以明文保存密钥，不使用系统钥匙串加密。");
    }
    stagedCredentialRef = createSecretRef();
    secrets.set(stagedCredentialRef, apiKey, storageMode);
  }
  let connection: ModelConnection;
  try {
    connection = await api.saveModelConnection({
      ...configuration,
      credential_ref: stagedCredentialRef,
    });
  } catch (error) {
    if (stagedCredentialRef) secrets.delete(stagedCredentialRef);
    throw error;
  }
  if (
    existing?.credential_ref
    && existing.credential_ref !== connection.credential_ref
  ) {
    try {
      secrets.delete(existing.credential_ref);
    } catch {
      // The obsolete encrypted entry is inert because configuration now points
      // at the new revision. Cleanup can be retried without risking misrouting.
    }
  }
  return {
    ...connection,
    secret_storage: connection.credential_ref ? secrets.storageMode?.(connection.credential_ref) : undefined,
    has_api_key: Boolean(
      connection.credential_ref && secrets.has(connection.credential_ref),
    ),
  };
}

export async function deleteModelConnectionWithSecret(
  api: Pick<ModelConfigurationApi, "modelConnection"> & {deleteModelConnection(connectionId:string):Promise<void>},
  secrets: {withoutSecret<T>(secretRef:string, commit:()=>Promise<T>):Promise<T>},
  connectionId:string,
):Promise<void> {
  const connection = await api.modelConnection(connectionId);
  const commit = () => api.deleteModelConnection(connectionId);
  if (connection.credential_ref) await secrets.withoutSecret(connection.credential_ref, commit);
  else await commit();
}
