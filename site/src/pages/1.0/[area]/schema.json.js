import { readFileSync } from "node:fs";
import { join } from "node:path";
import { MODULES, ROOT, schemaOf } from "../../../lib/standard.js";
import { schema } from "../../../lib/serve.js";

export function getStaticPaths() {
  return MODULES.filter((m) => schemaOf(m)).map((area) => ({ params: { area } }));
}

export function GET({ params }) {
  return schema(readFileSync(join(ROOT, "modules", params.area, "schema.json"), "utf8"));
}
