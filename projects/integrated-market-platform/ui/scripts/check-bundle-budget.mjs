import { readFile, readdir } from "node:fs/promises";
import { gzipSync } from "node:zlib";

const DIST_DIR = new URL("../dist/", import.meta.url);
const MANIFEST_URL = new URL(".vite/manifest.json", DIST_DIR);
const MAX_INITIAL_GZIP_BYTES = 203 * 1024;
const MAX_CHUNK_RAW_BYTES = 500_000;
/** Lane F: @luxalgo/vela lazy engine (~252 KiB gzip); must never join the entry graph. */
const MAX_VELA_LAZY_CHUNK_RAW_BYTES = 950_000;

const manifest = JSON.parse(await readFile(MANIFEST_URL, "utf8"));
const entryRecords = Object.values(manifest).filter((record) => record.isEntry);

if (entryRecords.length !== 1) {
  throw new Error(`Expected exactly one Vite entry, found ${entryRecords.length}.`);
}

const initialFiles = new Set();

function collectStaticImports(record) {
  if (record.file.endsWith(".js")) initialFiles.add(record.file);
  for (const importKey of record.imports ?? []) {
    const importedRecord = manifest[importKey];
    if (!importedRecord) throw new Error(`Manifest import is missing: ${importKey}`);
    if (!initialFiles.has(importedRecord.file)) collectStaticImports(importedRecord);
  }
}

collectStaticImports(entryRecords[0]);

let initialGzipBytes = 0;
for (const relativePath of initialFiles) {
  const source = await readFile(new URL(relativePath, DIST_DIR));
  initialGzipBytes += gzipSync(source).byteLength;
}

const assetsDir = new URL("assets/", DIST_DIR);
const jsAssetNames = (await readdir(assetsDir)).filter((name) => name.endsWith(".js"));
const chunkSizes = await Promise.all(
  jsAssetNames.map(async (name) => {
    const source = await readFile(new URL(name, assetsDir));
    return { name, rawBytes: source.byteLength };
  }),
);
const oversizedChunks = chunkSizes.filter(({ name, rawBytes }) => {
  if (name.startsWith("vela-")) return rawBytes > MAX_VELA_LAZY_CHUNK_RAW_BYTES;
  return rawBytes > MAX_CHUNK_RAW_BYTES;
});
const failures = [];

if (initialGzipBytes > MAX_INITIAL_GZIP_BYTES) {
  failures.push(
    `Initial JavaScript is ${(initialGzipBytes / 1024).toFixed(2)} KiB gzip; budget is 203.00 KiB.`,
  );
}
for (const { name, rawBytes } of oversizedChunks) {
  failures.push(`${name} is ${rawBytes} raw bytes; budget is ${MAX_CHUNK_RAW_BYTES}.`);
}

const velaChunk = chunkSizes.find(({ name }) => name.startsWith("vela-"));
const velaOnInitialPath = [...initialFiles].some((relativePath) => relativePath.includes("/vela-"));
if (velaOnInitialPath) {
  failures.push("@luxalgo/vela must stay off the Vite entry static import graph.");
}

const largestChunk = [...chunkSizes].sort((a, b) => b.rawBytes - a.rawBytes)[0];
const velaNote = velaChunk
  ? `; vela lazy ${(gzipSync(await readFile(new URL(velaChunk.name, assetsDir))).byteLength / 1024).toFixed(2)} KiB gzip`
  : "";
console.log(
  `Bundle metrics: initial ${(initialGzipBytes / 1024).toFixed(2)} KiB gzip; ` +
    `largest chunk ${largestChunk.name} ${(largestChunk.rawBytes / 1024).toFixed(2)} KiB raw${velaNote}.`,
);

if (failures.length > 0) {
  for (const failure of failures) console.error(`Bundle budget exceeded: ${failure}`);
  process.exitCode = 1;
}
