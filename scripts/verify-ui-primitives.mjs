import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.cwd();
const sourceRoot = join(root, "apps", "web", "src");
const legacyButtonAllowance = new Map([
  ["apps/web/src/components/screens/screen-experience.tsx", 13]
]);

function files(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? files(path) : path.endsWith(".tsx") ? [path] : [];
  });
}

const violations = [];
for (const path of files(sourceRoot)) {
  const name = relative(root, path).replaceAll("\\", "/");
  const source = readFileSync(path, "utf8");
  const buttons = source.match(/<button\b/g)?.length ?? 0;
  const allowed = legacyButtonAllowance.get(name) ?? 0;
  if (buttons !== allowed) violations.push(`${name}: ${buttons} raw <button> (exact legacy baseline ${allowed})`);
  if (/<dialog\b/.test(source)) violations.push(`${name}: raw <dialog>`);
  if (/role=["']alert["']/.test(source)) violations.push(`${name}: ad-hoc alert role`);
}

if (violations.length) {
  throw new Error(`Use Button, Dialog, StatePanel or FieldError from @bighead/ui:\n${violations.join("\n")}`);
}
console.log("UI primitive guard passed: future screens cannot add raw buttons, dialogs or error alerts.");
