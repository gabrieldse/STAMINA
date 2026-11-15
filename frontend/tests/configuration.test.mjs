import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import ts from 'typescript';

// Load the pure TypeScript helpers without adding a test-runner dependency.
function load(file) {
  const source = readFileSync(file, 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 } });
  const module = { exports: {} };
  new Function('require', 'module', 'exports', outputText)(
    name => load(resolve(dirname(file), name + '.ts')), module, module.exports,
  );
  return module.exports;
}
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../src');
const { buildConfiguration, parseConfiguration } = load(resolve(root, 'filters/configuration.ts'));
const { createInitialFilters } = load(resolve(root, 'filters/filterRegistry.ts'));
const { DEFAULT_TEMPERATURE_CONFIG } = load(resolve(root, 'types/temperature.ts'));
const { apiErrorMessage } = load(resolve(root, 'services/apiError.ts'));

test('API errors identify stale visibility servers and invalid request fields', () => {
  assert.match(apiErrorMessage({ detail: [{ loc: ['body', 'filters', 'sunVisibility'], type: 'extra_forbidden', msg: 'Extra inputs are not permitted' }] }, 422), /older version.*Restart/);
  assert.equal(apiErrorMessage({ detail: [{ loc: ['body', 'durationDays'], msg: 'Input should be greater than or equal to 1' }] }, 422), 'durationDays: Input should be greater than or equal to 1');
  assert.equal(apiErrorMessage({ detail: 'Missing terrain data' }, 503), 'Missing terrain data');
  assert.match(apiErrorMessage(null, 404), /Restart/);
});
const filters = {
  ...createInitialFilters(),
  sunVisibility: { enabled: true, value: true },
  earthVisibility: { enabled: false, value: true },
  terrain: { enabled: true, value: false },
  analysisMode: { enabled: true, value: 'instant' },
};
const temperature = {
  ...DEFAULT_TEMPERATURE_CONFIG, enabled: true, season: 'winter', statistic: 'amplitude',
  iceStabilityThresholdK: 95, selectionEnabled: true,
  temperatureK: { min: 22, max: 180 }, amplitudeK: { min: 30, max: 240 },
};
const rules = [
  { id: 'sun-rule', label: ' Solar requirement ', metric: 'sunlightPercent', operator: 'gte', threshold: 72.5, enabled: true },
  { id: 'earth-rule', label: 'Communication', metric: 'maxCommunicationBlackoutHours', operator: 'lte', threshold: 38, enabled: false },
];

test('JSON round trip preserves all built-in values, temperature settings and custom rules', () => {
  const exported = buildConfiguration(temperature, rules, filters);
  const imported = parseConfiguration(JSON.parse(JSON.stringify(exported)));
  assert.deepEqual(imported, { temperature, rules, filters });
});

test('empty rules and disabled temperature settings round trip', () => {
  const exported = buildConfiguration(DEFAULT_TEMPERATURE_CONFIG, [], filters);
  assert.deepEqual(exported.rules, []);
  assert.deepEqual(parseConfiguration(exported), { temperature: DEFAULT_TEMPERATURE_CONFIG, rules: [], filters });
});

test('export is a snapshot independent of subsequent edits', () => {
  const current = structuredClone({ temperature, rules, filters });
  const exported = buildConfiguration(current.temperature, current.rules, current.filters);
  current.rules[0].threshold = 1;
  current.filters.sunVisibility.value = 1;
  current.temperature.temperatureK.min = 1;
  assert.deepEqual(parseConfiguration(exported), { temperature, rules, filters });
});

test('legacy files remain supported without overwriting unrelated built-in filters', () => {
  assert.deepEqual(parseConfiguration({ version: 1, rules }), { rules });
  const oldTemperatureFile = buildConfiguration(temperature, [], filters);
  delete oldTemperatureFile.filters;
  delete oldTemperatureFile.rules;
  assert.deepEqual(parseConfiguration(oldTemperatureFile), { rules: [], temperature });
});

test('invalid settings and duplicate custom IDs reject the whole import', () => {
  for (const mutate of [
    data => { data.filters.sunVisibility.value = 90; },
    data => { data.filters.earthVisibility.enabled = 'false'; },
    data => { delete data.filters.terrain; },
    data => { data.southPoleTemperatures.selection.temperatureK = { min: 200, max: 10 }; },
    data => { data.rules.push(data.rules[0]); },
    data => { data.version = 99; },
  ]) {
    const data = buildConfiguration(temperature, rules, filters);
    mutate(data);
    assert.throws(() => parseConfiguration(data));
  }
});
