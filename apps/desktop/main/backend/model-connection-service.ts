import type { ModelConnection, ModelConnectionInput } from "../../shared/contracts";

export type ModelConfigurationApi = {
  modelConnection(connectionId: string): Promise<ModelConnection>;
  saveModelConnection(
    input: Omit<ModelConnectionInput, "api_key">,
  ): Promise<ModelConnection>;
};

export type ModelSecretStore = {
  set(secretRef: string, secret: string): void;
  delete(secretRef: string): void;
  has(secretRef: string): boolean;
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
    credential_ref: _ignoredCredentialRef,
    ...configuration
  } = input;
  let stagedCredentialRef: string | undefined;
  if (apiKey && input.auth_mode !== "none") {
    stagedCredentialRef = createSecretRef();
    secrets.set(stagedCredentialRef, apiKey);
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
    has_api_key: Boolean(
      connection.credential_ref && secrets.has(connection.credential_ref),
    ),
  };
}
