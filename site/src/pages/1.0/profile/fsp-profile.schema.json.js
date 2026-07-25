import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "../../../lib/standard.js";
import { schema } from "../../../lib/serve.js";

export function GET() {
  return schema(readFileSync(join(ROOT, "profile", "fsp-profile.schema.json"), "utf8"));
}
