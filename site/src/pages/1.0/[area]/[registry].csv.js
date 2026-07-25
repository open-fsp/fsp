import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { MODULES, ROOT, manifest } from "../../../lib/standard.js";
import { csv } from "../../../lib/serve.js";

export function getStaticPaths() {
  const paths = [];
  for (const area of MODULES) {
    for (const name of manifest(area).registries) paths.push({ params: { area, registry: name } });
  }
  for (const f of readdirSync(join(ROOT, "appendix")).filter((x) => x.endsWith(".csv"))) {
    paths.push({ params: { area: "appendix", registry: f.replace(/\.csv$/, "") } });
  }
  return paths;
}

export function GET({ params }) {
  const dir = params.area === "appendix" ? "appendix" : join("modules", params.area);
  return csv(readFileSync(join(ROOT, dir, `${params.registry}.csv`), "utf8"));
}
