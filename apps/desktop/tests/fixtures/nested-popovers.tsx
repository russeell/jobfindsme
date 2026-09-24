// Isolated renderer fixture, not imported by the shipped app.
import {createRoot} from 'react-dom/client';
import {PopoverButton} from '../../renderer/src/shared/PopoverButton';
const host=document.createElement('div');
host.id='nested-popover-fixture';
host.style.cssText='position:fixed;left:230px;top:140px;z-index:80';
document.querySelector('.work-content')!.appendChild(host);
const root=createRoot(host);
root.render(<PopoverButton title="外层验收菜单" label="外层验收菜单"><PopoverButton title="内层验收菜单" label="内层验收菜单"><button>内层验收选项</button></PopoverButton></PopoverButton>);
Object.assign(window,{removeNestedPopoverFixture:()=>{root.unmount();host.remove();}});
