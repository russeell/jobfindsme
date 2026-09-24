export function currentModelKey(workspaceId: string): string {
  return `jobfindsme:current-model:${workspaceId}`;
}

export function getCurrentModel(workspaceId: string | undefined): string | null {
  if (!workspaceId) return null;
  return localStorage.getItem(currentModelKey(workspaceId));
}

export function setCurrentModel(workspaceId: string | undefined, connectionId: string): void {
  if (workspaceId) localStorage.setItem(currentModelKey(workspaceId), connectionId);
}
