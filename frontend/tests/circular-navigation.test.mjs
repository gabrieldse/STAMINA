import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import ts from 'typescript';

function load(file) {
  const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const module={exports:{}};
  new Function('require','module','exports',code)(name=>load(resolve(dirname(file),name+'.ts')),module,module.exports);
  return module.exports;
}
const {circularWorld,panCircular,zoomCircular}=load(fileURLToPath(new URL('../src/utils/circularNavigation.ts',import.meta.url)));
const frame={width:1000,height:700,radius:326};
const near=(a,b)=>assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<1e-7);

test('dragging carries the same surface point with the pointer',()=>{
  const view={x:10000,y:-9000,zoom:3};
  const point=circularWorld(view,frame,370,280);
  const moved=panCircular(view,frame,120,-50);
  near(point,circularWorld(moved,frame,490,230));
});
test('zoom preserves the off-center cursor anchor after panning and at both zoom limits',()=>{
  for(const zoom of [.2,1,8,64])for(const factor of [.01,.7,1.5,100]){
    const view={x:12345,y:67890,zoom},point=circularWorld(view,frame,720,180);
    const next=zoomCircular(view,frame,720,180,factor);
    near(point,circularWorld(next,frame,720,180));
    assert.ok(next.zoom>=.2&&next.zoom<=64);
  }
});
