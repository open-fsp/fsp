import { readFileSync } from "node:fs";
import { join } from "node:path";
import { MODULES, ROOT } from "../../../lib/standard.js";
import { json } from "../../../lib/serve.js";

export function getStaticPaths() {
  return MODULES.map((area) => ({ params: { area } }));
}

export function GET({ params }) {
  return json(readFileSync(join(ROOT, "modules", params.area, "module.json"), "utf8"));
}
