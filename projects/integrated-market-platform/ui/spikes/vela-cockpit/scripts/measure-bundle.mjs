import { readFile, readdir } from "node:fs/promises";
import { gzipSync } from "node:zlib";

const dist = new URL("../dist/", import.meta.url);
const assets = new URL("assets/", dist);
const names = await readdir(assets);
const jsFiles = names.filter((n) => n.endsWith(".js"));

let totalRaw = 0;
let totalGzip = 0;
const rows = [];

for (const name of jsFiles) {
  const buf = await readFile(new URL(name, assets));
  const gzip = gzipSync(buf);
  totalRaw += buf.byteLength;
  totalGzip += gzip.byteLength;
  rows.push({ name, rawKb: (buf.byteLength / 1024).toFixed(1), gzipKb: (gzip.byteLength / 1024).toFixed(1) });
}

rows.sort((a, b) => Number(b.rawKb) - Number(a.rawKb));

console.log("Lane G Vela spike bundle (isolated Vite app, not IMP main entry):\n");
for (const row of rows) {
  console.log(`  ${row.name}: ${row.rawKb} KiB raw, ${row.gzipKb} KiB gzip`);
}
console.log(`\nTotal JS: ${(totalRaw / 1024).toFixed(1)} KiB raw, ${(totalGzip / 1024).toFixed(1)} KiB gzip`);
console.log(`Chunks: ${jsFiles.length}`);
