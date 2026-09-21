/// <reference types="vite/client" />

import type { DesktopBridge } from "../../shared/contracts";

declare global {
  interface Window {
    jobfindsme?: DesktopBridge;
  }
}

export {};
