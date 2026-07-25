import { readdirSync } from "node:fs";
import { join } from "node:path";
import { MODULES, ROOT, manifest, registry, rowsOf } from "../../../lib/standard.js";
import { json } from "../../../lib/serve.js";

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
  const { area, registry: name } = params;
  const reg = registry(area, name);
  return json(
    JSON.stringify(
      {
        standard: "FSP",
        module: area === "appendix" ? null : area,
        version: area === "appendix" ? null : manifest(area).version,
        registry: name,
        title: reg.title,
        description: reg.description,
        in_standard: area !== "appendix",
        columns: reg.columns,
        rows: rowsOf(area, name),
      },
      null,
      2,
    ),
  );
}
