import test from 'node:test';
import assert from 'node:assert/strict';
import {browserIsOccluded} from '../dist-electron/shared/browser-overlays.js';
const browser={x:900,y:100,width:700,height:800};
const overlay=(bounds,kind='popover',visible=true)=>({bounds,kind,visible});
test('left menus and touching edges do not hide the right native browser',()=>{
 for(const x of [100,600])assert.equal(browserIsOccluded(browser,[overlay({x,y:200,width:300,height:300})]),false);
 assert.equal(browserIsOccluded(browser,[overlay({x:950,y:10,width:200,height:90})]),false);
});
test('actual overlap or global modal hides; hidden and removed overlays restore',()=>{
 const bounds={x:899,y:200,width:300,height:300};
 assert.equal(browserIsOccluded(browser,[overlay(bounds)]),true);
 assert.equal(browserIsOccluded(browser,[overlay(bounds,'popover',false)]),false);
 assert.equal(browserIsOccluded(browser,[]),false);
 assert.equal(browserIsOccluded(browser,[overlay({x:100,y:200,width:300,height:300},'modal')]),true);
});
test('nested current overlays are recomputed without stale counts',()=>{
 const parent=overlay({x:100,y:200,width:300,height:300}),child=overlay({x:850,y:300,width:200,height:100});
 assert.equal(browserIsOccluded(browser,[parent,child]),true);
 assert.equal(browserIsOccluded(browser,[parent]),false);
 assert.equal(browserIsOccluded(browser,[parent,{...child,visible:false}]),false);
});
