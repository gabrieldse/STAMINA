import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source=readFileSync(new URL('../src/utils/circularProjection.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const module={exports:{}};new Function('module','exports',compiled)(module,module.exports);
const {circularProjection,CIRCULAR_RADIUS_M}=module.exports;
const delta=(a,b)=>(a-b+540)%360-180;

test('the chosen site is the true origin, including both poles and the dateline',()=>{
  for(const latitude of [-90,-80,-20,0,75,90])for(const longitude of [-179.99,-10,0,179.99]){
    const projection=circularProjection({latitude,longitude});
    const plane=projection.forward(latitude,longitude),site=projection.inverse(0,0);
    assert.ok(Math.hypot(plane.x,plane.y)<1e-7);
    assert.ok(Math.abs(site.latitude-latitude)<1e-6);
    assert.ok(Math.abs(delta(site.longitude,longitude))<1e-6);
  }
});
test('the circular edge is ten degrees from its chosen center in every direction',()=>{
  for(const center of [{latitude:12.3,longitude:45.6},{latitude:90,longitude:-10},{latitude:-88,longitude:170}]){
    const projection=circularProjection(center),rad=Math.PI/180;
    for(let angle=0;angle<360;angle+=30){
      const x=CIRCULAR_RADIUS_M*Math.cos(angle*rad),y=CIRCULAR_RADIUS_M*Math.sin(angle*rad);
      const point=projection.inverse(x,y);
      const dot=Math.sin(center.latitude*rad)*Math.sin(point.latitude*rad)+Math.cos(center.latitude*rad)*Math.cos(point.latitude*rad)*Math.cos((point.longitude-center.longitude)*rad);
      assert.ok(Math.abs(Math.acos(Math.max(-1,Math.min(1,dot)))/rad-10)<1e-6);
      const back=projection.forward(point.latitude,point.longitude);
      assert.ok(Math.hypot(back.x-x,back.y-y)<1e-5);
    }
  }
});
