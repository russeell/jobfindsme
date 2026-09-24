import type { ReactNode } from 'react';
const shapes: Record<string, ReactNode> = {
 discover:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
 research:<><path d="M12 21H5V3h10l4 4v5M14 3v5h5"/><circle cx="16" cy="16" r="4"/><path d="m19 19 3 3"/></>,
 records:<><path d="M3 10a9 9 0 1 1 1 8M3 4v6h6M12 7v5l3 2"/></>,
 resume:<><rect x="4" y="3" width="16" height="18" rx="2"/><circle cx="12" cy="9" r="2.5"/><path d="M8 16c0-4 8-4 8 0M8 18h8"/></>,
 scores:<><path d="M4 6h16M4 12h16M4 18h16"/><rect x="8" y="4" width="3" height="4" fill="currentColor"/><rect x="14" y="10" width="3" height="4" fill="currentColor"/><rect x="7" y="16" width="3" height="4" fill="currentColor"/></>,
 sources:<><path d="M3 21h18M5 21V4h14v17M9 21v-5h6v5M8 8h2m4 0h2M8 12h2m4 0h2"/></>,
 models:<><rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3"/></>,
 settings:<><circle cx="12" cy="12" r="3"/><path d="M10 2h4l.6 2.2 1.7.7 2-.9 2.8 2.8-.9 2 .7 1.7 2.1.5v4l-2.1.6-.7 1.7.9 2-2.8 2.8-2-.9-1.7.7L14 22h-4l-.6-2.1-1.7-.7-2 .9-2.8-2.8.9-2-.7-1.7L1 14v-4l2.1-.6.7-1.7-.9-2L5.7 3l2 .9 1.7-.7z"/></>,
 panelLeft:<><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></>,
 expand:<><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/></>,
 split:<><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M12 4v16"/></>,
};
export function Icon({name}:{name:string}) {return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name] ?? shapes.discover}</svg>;}
