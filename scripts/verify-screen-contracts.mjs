import { readFileSync } from "node:fs";

const content = readFileSync(new URL("../docs/CONTRATOS-DE-TELA.md", import.meta.url), "utf8");
const matches = content.match(/\| T\d{2} \|/g) ?? [];

if (matches.length !== 56) {
  console.error(`Expected 56 mapped screens, found ${matches.length}.`);
  process.exit(1);
}

console.log("Screen contract coverage OK: 56 screens mapped.");
