import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import test from 'node:test';

test('map hides obstructed pixels and rejects clicks there; disabling restores the map', () => {
  const html = readFileSync(new URL('../public/lunar-map/index.html', import.meta.url), 'utf8');
  const source = html.slice(html.indexOf('let visibilityMask ='), html.indexOf('let terrainMeta'));
  let rendered;
  const context = {
    atob,
    meta: { radiusM: 10 }, draw() {},
    document: { createElement() { return { getContext() { return {
      createImageData(w, h) { return { data: new Uint8ClampedArray(w*h*4) }; },
      putImageData(data) { rendered = data.data; },
    }; } }; } },
  };
  runInNewContext(source + '\nthis.apply = applyVisibilityMask; this.matches = matchesVisibility;', context);
  context.apply({ size: 2, visible: [1, 0, 0, 1] });
  assert.deepEqual([rendered[3], rendered[7], rendered[11], rendered[15]], [0, 255, 255, 0]);
  assert.equal(context.matches(-5, 5), true);
  assert.equal(context.matches(5, 5), false);
  context.apply({ size: 2, encoding: 'bitset-msb', visiblePacked: 'kA==' });
  assert.deepEqual([rendered[3], rendered[7], rendered[11], rendered[15]], [0, 255, 255, 0]);
  assert.equal(context.matches(-5, 5), true);
  assert.equal(context.matches(5, 5), false);
  context.apply({ pending: true });
  assert.equal(context.matches(-5, 5), false);
  context.apply(null);
  assert.equal(context.matches(5, 5), true);
});

test('visibility mask is drawn in both the full map and each comparison crop', () => {
  const html = readFileSync(new URL('../public/lunar-map/index.html', import.meta.url), 'utf8');
  const source = html.slice(html.indexOf('function drawMap(inCell)'), html.indexOf('function drawPin()'));
  const calls = [];
  const mask = {}, image = {};
  const ctx = new Proxy({}, { get(target, key) { return target[key] ?? ((...args) => calls.push([key, ...args])); } });
  const context = {
    ctx, image, visibilityMask: mask, visibilityConfig: {},
    meta: { radiusM: 10, size: 2 }, view: { k: 1 }, frame: { x: 2, y: 3, w: 8, h: 9 },
    dpr: () => 1, toScreen: () => ({ sx: 0, sy: 0 }), $: () => ({ checked: false }),
    selMask: null, EMBED: true, drawTerrain() {}, drawTerrainContours() {}, drawSites() {}, drawPin() {},
  };
  runInNewContext(source+'\nthis.paint = drawMap;', context);
  for (const inCell of [false, true]) {
    calls.length = 0;
    context.paint(inCell);
    assert.equal(calls.filter(([name, source]) => name === 'drawImage' && source === mask).length, 1);
    if (inCell) assert.ok(calls.some(call => call[0] === 'rect' && call[1] === 2 && call[2] === 3 && call[3] === 8 && call[4] === 9));
  }
});
