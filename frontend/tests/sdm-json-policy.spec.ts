import {test, expect} from '@playwright/test';
import {validateSdmJson} from '../src/workbench/sdmJson';
import {jsonDraft} from '../src/workbench/JsonInputContract';

const fixture = () => ({version: 5, source_format: 'JSON', source_ref: 'source.0',
  json_input_contract: jsonDraft({root_shape: 'ARRAY'}),
  json_source: {content_checksum: 'a'.repeat(64), profile_checksum: 'b'.repeat(64), contract_checksum: 'c'.repeat(64)}});

test('JSON SDM display guard accepts both confirmed root shapes without mutation', () => {
  for (const root_shape of ['ARRAY', 'OBJECT']) {
    const document = fixture();document.json_input_contract.root_shape = root_shape;
    const before = JSON.stringify(document);
    expect(() => validateSdmJson(document)).not.toThrow();
    expect(JSON.stringify(document)).toBe(before);
  }
});

test('JSON SDM display guard rejects every missing policy and changed fingerprint', () => {
  for (const key of Object.keys(fixture().json_input_contract)) {
    const document:any = fixture();delete document.json_input_contract[key];
    expect(() => validateSdmJson(document)).toThrow('SDM JSON');
  }
  for (const key of Object.keys(fixture().json_source)) {
    const document:any = fixture();document.json_source[key] = 'invalid';
    expect(() => validateSdmJson(document)).toThrow('SDM JSON');
  }
  for (const changes of [{source_format:'CSV'}, {source_ref:'source.1'}, {json_input_contract:null}, {json_source:null}])
    expect(() => validateSdmJson({...fixture(),...changes})).toThrow('SDM JSON');
  const document:any = fixture();document.json_input_contract.allow_loss = true;
  expect(() => validateSdmJson(document)).toThrow('SDM JSON');
});
