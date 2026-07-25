import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "../../../lib/standard.js";
import { yaml } from "../../../lib/serve.js";

export function GET() {
  return yaml(readFileSync(join(ROOT, "api", "quote.openapi.yaml"), "utf8"));
}
