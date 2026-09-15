/**
 * Minimal research runner — requires operator-installed pinets (AGPL) via isolated npm install.
 * IMP does not ship PineTS in the production UI graph; this script is opt-in research only.
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const raw = await readStdin();
  const request = JSON.parse(raw || "{}");
  const scriptId = String(request.script_id || "");
  const bars = Array.isArray(request.bars) ? request.bars : [];
  const parameters = request.parameters && typeof request.parameters === "object" ? request.parameters : {};

  // PineTS full fixture execution is not wired in Lane E gate 1 — fail closed honestly.
  process.stdout.write(
    JSON.stringify({
      status: "UNSUPPORTED",
      reason: "UNSUPPORTED_PINE_FEATURE",
      script_id: scriptId,
      bar_count: bars.length,
      parameters,
      message:
        "Lane E gate 1 uses Python reference parity; enable PineTS series extraction in a later gate.",
    }),
  );
}

main().catch((error) => {
  console.error(String(error));
  process.exit(1);
});
