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
