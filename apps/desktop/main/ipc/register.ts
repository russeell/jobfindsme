import type {IpcMain,WebContents} from 'electron';

export type DesktopHandlerRegister = IpcMain['handle'];

/** The application window's top frame owns every renderer-facing IPC request. */
export function createDesktopHandlerRegistrar(ipc:Pick<IpcMain,'handle'>,owner:()=>WebContents|undefined):DesktopHandlerRegister{
 return (channel,listener)=>ipc.handle(channel,(event,...args)=>{
  const current=owner();
  if(!current||current.isDestroyed()||event.sender!==current||event.senderFrame!==current.mainFrame)throw Error('unauthorized caller');
  return listener(event,...args);
 });
}
