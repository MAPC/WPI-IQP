// Optional authoring QA. Uses the installed Codex renderer, not a pipeline dependency.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const runtimeNode = process.env.MAPC_QA_NODE_MODULES_PARENT;
if (!runtimeNode) throw new Error('Set MAPC_QA_NODE_MODULES_PARENT to the bundled Node runtime directory.');
const require = createRequire(path.join(runtimeNode, 'mapc-qa-loader.cjs'));
const { FileBlob, SpreadsheetFile } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const root = path.resolve(process.argv[2] || '.');
const previewDir = path.join(root, 'output/reports/workbook_previews');
await fs.mkdir(previewDir, {recursive:true});
const manifest = JSON.parse(await fs.readFile(path.join(root, 'notes/workbook_visual_qa.json'), 'utf8'));
const report = { renderer: '@oai/artifact-tool import and render of saved XlsxWriter files', nativeExcelAutomated: false, sheets: [], errors: [] };
for (const plan of manifest) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root, plan.file)));
  wb.recalculate();
  for (const sheetName of plan.sheets) {
    const slug = `${path.basename(plan.file,'.xlsx')}_${sheetName}`.replace(/[^a-zA-Z0-9_-]/g,'_');
    const range = sheetName === 'Chart source tables' ? 'A1:L25' : sheetName.includes('fields') ? 'A1:F9' : sheetName === 'Methodology notes' ? 'A1:B12' : 'A1:H20';
    try {
      const blob = await wb.render({sheetName,range,scale:1,format:'png'});
      const output = path.join(previewDir,slug+'.png');
      await fs.writeFile(output, new Uint8Array(await blob.arrayBuffer()));
      report.sheets.push({file:plan.file,sheet:sheetName,range,preview:path.relative(root,output),status:'rendered'});
      console.log(`Rendered ${path.basename(plan.file)}: ${sheetName}`);
    } catch(error) {
      report.errors.push({file:plan.file,sheet:sheetName,error:String(error)});
      console.log(`Render unavailable ${path.basename(plan.file)}: ${sheetName}: ${error}`);
    }
  }
}
await fs.writeFile(path.join(root,'output/reports/workbook_visual_qa.json'),JSON.stringify(report,null,2));
