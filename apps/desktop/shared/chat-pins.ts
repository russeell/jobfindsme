// Pins are workspace-scoped display preferences, independent of chat saves.
// Streaming replies must not overwrite their order or update conversation dates.
type PinStorage = Pick<Storage, "getItem" | "setItem">;
const key = (workspaceId: string) => `jobfindsme:chat-pins:${workspaceId}`;

export function loadChatPins(storage: PinStorage, workspaceId: string): string[] {
  const raw = storage.getItem(key(workspaceId));
  if (!raw) return [];
  const value: unknown = JSON.parse(raw);
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((id): id is string => typeof id === "string" && id.length > 0 && id.length <= 100))];
}

export function toggleChatPin(storage: PinStorage, workspaceId: string, id: string): string[] {
  const pins = loadChatPins(storage, workspaceId);
  const next = pins.includes(id) ? pins.filter(value => value !== id) : [id, ...pins];
  storage.setItem(key(workspaceId), JSON.stringify(next));
  return next;
}

export function sortPinnedChats<T extends {id: string; title: string; updatedAt: string}>(chats: T[], pins: string[], sort: "recent" | "oldest" | "title"): T[] {
  const positions = new Map(pins.map((id, index) => [id, index]));
  return [...chats].sort((a, b) => {
    const left = positions.get(a.id), right = positions.get(b.id);
    if (left !== undefined || right !== undefined) return (left ?? pins.length) - (right ?? pins.length);
    return sort === "title" ? a.title.localeCompare(b.title, "zh-CN") : sort === "oldest" ? a.updatedAt.localeCompare(b.updatedAt) : b.updatedAt.localeCompare(a.updatedAt);
  });
}
