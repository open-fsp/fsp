import { apiSpec } from "../../../lib/standard.js";
import { yaml } from "../../../lib/serve.js";

export function GET() {
  return yaml(apiSpec("billing"));
}
