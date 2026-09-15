import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

try {
  const pkg = require("pinets/package.json");
  process.stdout.write(JSON.stringify({ version: pkg.version, license: pkg.license }));
} catch (error) {
  console.error(String(error));
  process.exit(1);
}
