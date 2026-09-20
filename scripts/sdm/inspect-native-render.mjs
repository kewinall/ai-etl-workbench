// Development-only visual check of server-produced XLSX. Not a runtime dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const runtime = process.env.WORKBENCH_ARTIFACT_NODE_MODULES;
if (!runtime) throw Error('Bundled artifact runtime is required for visual verification');
const require = createRequire(import.meta.url);
const {FileBlob, SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool', {paths:[runtime]})));
const input = path.resolve(process.argv[2]);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
workbook.recalculate();
console.log((await workbook.inspect({kind:'sheet',include:'id,name'})).ndjson);
console.log((await workbook.inspect({kind:'formula',maxChars:1500,options:{maxResults:10}})).ndjson);
for (const [sheetName, range, name] of [['欄位對照','A1:F9','mapping'],['規則及版本','A1:B20','rules']]) {
  const preview = await workbook.render({sheetName,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(path.dirname(input),name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
