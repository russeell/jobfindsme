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

export function clearCurrentModel(connectionId:string):void {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith("jobfindsme:current-model:") && localStorage.getItem(key) === connectionId) localStorage.removeItem(key);
  }
}
