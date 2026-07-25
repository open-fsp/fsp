/**
 * Единственный источник данных для витрины: реестры, манифесты и схемы модулей FSP.
 * Сайт ничего не дублирует руками — если реестр изменился, страница меняется сама.
 */
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { marked } from "marked";

/**
 * Корень репозитория. Считается от рабочего каталога, а не от import.meta.url:
 * при сборке модуль попадает в бандл внутри dist и путь до канона теряется.
 */
function findRoot() {
  let dir = process.cwd();
  for (let i = 0; i < 5; i++) {
    if (existsSync(join(dir, "modules", "core", "module.json"))) return dir;
    dir = resolve(dir, "..");
  }
  throw new Error("Не найден корень стандарта: нет modules/core/module.json выше " + process.cwd());
}

export const ROOT = findRoot();
/** Адрес канона. Меняется в одном месте: сайт, llms.txt и главная берут его отсюда. */
export const REPO = "https://github.com/open-fsp/fsp";
export const GITHUB = REPO + "/blob/main";
export const MODULES = ["core", "pricing", "capacity", "quote", "order", "tracking"];

function dirOf(area) {
  return area === "appendix" ? join(ROOT, "appendix") : join(ROOT, "modules", area);
}

/** Разбор CSV с кавычками и переводами строк внутри полей. */
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false;
      } else field += c;
      continue;
    }
    if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}

const cache = new Map();

/**
 * Реестр как {title, description, columns, rows}.
 * Заголовок — первая строка с более чем одной заполненной ячейкой (выше него преамбула).
 */
export function hasRegistry(area, name) {
  return existsSync(join(dirOf(area), `${name}.csv`));
}

export function registry(area, name) {
  const key = `${area}/${name}`;
  if (cache.has(key)) return cache.get(key);
  const raw = readFileSync(join(dirOf(area), `${name}.csv`), "utf8");
  const rows = parseCsv(raw);
  const hdr = rows.findIndex((r) => r.filter((c) => c.trim()).length > 1);
  const preamble = rows.slice(0, hdr).map((r) => r[0]).filter(Boolean);
  const columns = rows[hdr].map((c) => c.trim());
  const body = rows
    .slice(hdr + 1)
    .filter((r) => r.some((c) => c.trim()))
    .map((r) => columns.map((_, i) => (r[i] ?? "").trim()));
  const out = {
    area,
    name,
    title: preamble[0] || name,
    description: preamble.slice(1).join(" "),
    columns,
    rows: body,
    href: `/registry/${area}/${name}/`,
  };
  cache.set(key, out);
  return out;
}

/** Реестр как массив объектов. */
export function rowsOf(area, name) {
  const r = registry(area, name);
  return r.rows.map((row) => Object.fromEntries(r.columns.map((c, i) => [c, row[i]])));
}

export function manifest(module) {
  return JSON.parse(readFileSync(join(dirOf(module), "module.json"), "utf8"));
}

export function allManifests() {
  return MODULES.map(manifest);
}

export function schemaOf(module) {
  const p = join(dirOf(module), "schema.json");
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf8")) : null;
}

export function profileSchema() {
  return JSON.parse(readFileSync(join(ROOT, "profile", "fsp-profile.schema.json"), "utf8"));
}

export function profileExamples() {
  const dir = join(ROOT, "profile", "examples");
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .map((f) => ({ file: f, json: readFileSync(join(dir, f), "utf8").trimEnd() }));
}

/** Нормативные правила всех модулей и приложения одним списком. */
export function allRules() {
  const out = [];
  for (const area of [...MODULES, "appendix"]) {
    if (!existsSync(join(dirOf(area), "rules.csv"))) continue;
    for (const r of rowsOf(area, "rules")) {
      if (!r.ID) continue;
      out.push({ id: r.ID, text: r["Правило"], area, prefix: r.ID.split("-")[0] });
    }
  }
  return out;
}

export function readDoc(...parts) {
  return readFileSync(join(ROOT, ...parts), "utf8");
}

/**
 * Markdown канона в HTML. Относительные ссылки репозитория переписываются на
 * страницы витрины: реестр рядом с README — в свою таблицу, `../<модуль>` — в
 * страницу модуля. Что не удалось разложить, уходит на GitHub, а не в 404.
 *
 * strip убирает из канона то, что страница витрины уже нарисовала сама:
 * "h1" — заголовок файла, "lead" — первый абзац, "table" — первую таблицу.
 * В репозитории README остаётся целым, на странице ничего не задваивается.
 */
export function renderMarkdown(md, area = null, strip = []) {
  let src = md;
  if (strip.includes("h1")) src = src.replace(/^#\s[^\n]*\n+/, "");
  if (strip.includes("lead")) src = src.replace(/^(?![#|])[^\n]+(\n(?![\n#|])[^\n]+)*\n+/, "");
  if (strip.includes("table")) src = src.replace(/^\|[^\n]*\n(\|[^\n]*\n)*\n*/m, "");
  const html = marked.parse(src, { mangle: false, headerIds: true });
  return html.replace(/href="([^"#][^"]*)"/g, (m, href) => {
    if (/^(https?:|mailto:|\/)/.test(href)) return m;
    // выкидываем ./ и ../: адрес страницы витрины не зависит от глубины файла в репозитории
    const rel = href.replace(/^\.\//, "");
    const bare = rel.replace(/^(\.\.\/)+/, "");
    const mod = `(${MODULES.join("|")})`;  // только реальные модули, иначе appendix и profile съедаются
    const reg = "([a-z_0-9]+)";
    const rules = [
      [new RegExp(`^modules/${mod}/${reg}\\.csv$`), (x) => `/registry/${x[1]}/${x[2]}/`],
      [new RegExp(`^modules/${mod}/README\\.md$`), (x) => `/modules/${x[1]}/`],
      [new RegExp(`^modules/${mod}/schema\\.json$`), (x) => `/1.0/${x[1]}/schema.json`],
      [new RegExp(`^modules/${mod}/?$`), (x) => `/modules/${x[1]}/`],
      [new RegExp(`^modules/README\\.md$`), () => "/modules/"],
      [new RegExp(`^${mod}/${reg}\\.csv$`), (x) => `/registry/${x[1]}/${x[2]}/`],
      [new RegExp(`^${mod}/?$`), (x) => `/modules/${x[1]}/`],
      [new RegExp(`^appendix/${reg}\\.csv$`), (x) => `/registry/appendix/${x[1]}/`],
      [/^appendix\/?(README\.md)?$/, () => "/appendix/"],
      [/^profile\/?(README\.md)?$/, () => "/profile/"],
      [/^fsp-profile\.schema\.json$/, () => "/1.0/profile/fsp-profile.schema.json"],
      [/^profile\/fsp-profile\.schema\.json$/, () => "/1.0/profile/fsp-profile.schema.json"],
      [/^examples\/?$/, () => "/profile/#examples"],
      [/^api\/quote\.openapi\.yaml$/, () => "/artifacts/#api"],
      [/^schema\.json$/, () => (area && MODULES.includes(area) ? `/1.0/${area}/schema.json` : null)],
      [new RegExp(`^${reg}\\.csv$`), (x) => (area ? `/registry/${area}/${x[1]}/` : null)],
      [/^CONTRIBUTING\.md$/, () => null],
      [/^CHANGELOG\.md$/, () => "/changelog/"],
      [/^ABOUT\.md$/, () => "/about/"],
    ];
    for (const [re, to] of rules) {
      const hit = bare.match(re);
      if (!hit) continue;
      const target = to(hit);
      if (target) return `href="${target}"`;
      break;
    }
    // не разложилось — ведём в репозиторий, а не в 404
    const base = area && area !== "appendix" ? `modules/${area}` : area || "";
    const path = href.startsWith("..") ? bare : [base, rel].filter(Boolean).join("/");
    return `href="${GITHUB}/${path}"`;
  });
}

/** Русское согласование числительного: plural(21, "код", "кода", "кодов"). */
export function plural(n, one, few, many) {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}

/** Сводка по составу стандарта для главной. */
export function summary() {
  const services = rowsOf("core", "catalog_services").filter((s) => s["Тип услуги"]);
  const stable = allManifests().filter((m) => m.status === "stable");
  return {
    modules: stable.length,
    planned: allManifests().filter((m) => m.status === "planned").length,
    services: services.length,
    baseServices: services.filter((s) => s["Тип услуги"] === "base").length,
    conditions: rowsOf("pricing", "price_conditions").length,
    levels: rowsOf("pricing", "conformance_levels").length,
    unmet: rowsOf("quote", "unmet_reasons").length,
    rules: allRules().filter((r) => r.area !== "appendix").length,
    checks: rowsOf("appendix", "integrity_checks").length,
    // разбор реальных прайсов не публикуется: числа берём только если данные рядом
    imports: hasRegistry("appendix", "price_imports")
      ? rowsOf("appendix", "price_imports").length
      : 166,
    gaps: rowsOf("appendix", "residual_gaps").filter((g) => g.status === "open").length,
    registries: stable.reduce((n, m) => n + m.registries.length, 0),
  };
}
