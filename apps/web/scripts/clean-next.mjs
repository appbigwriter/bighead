import { rmSync } from "node:fs";

const target = process.env.NEXT_DIST_DIR ?? ".next";
if (!/^\.next(?:-[a-z0-9-]+)?$/i.test(target)) throw new Error(`Unsafe Next distDir: ${target}`);
rmSync(target, { recursive: true, force: true });
