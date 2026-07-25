import { MODULES, manifest, summary, rowsOf, allRules, REPO } from "../lib/standard.js";

export function GET() {
  const s = summary();
  const mods = MODULES.map(manifest);
  const levels = rowsOf("pricing", "conformance_levels");
  const unmet = rowsOf("quote", "unmet_reasons");
  const rules = allRules();

  const text = `# FSP — Fulfillment Services Protocol

Открытый стандарт услуг фулфилмента: прайс оператора, свободные мощности и заявка на
фулфилмент описываются машиночитаемо. Версия протокола 1.0. Канон: ${REPO}.
Текст спецификации под CC BY 4.0, код и схемы под Apache-2.0. Ведёт стандарт МПФИТ
(https://mpfit.ru), первый реализующий; правки принимаются через pull request.

## Устройство

Протокол собран из модулей, каждый версионируется отдельно (MAJOR.MINOR). Сторона объявляет
поддерживаемые модули и версии в манифесте по адресу /.well-known/fsp; стороны сводят манифесты
и работают по пересечению.

${mods
  .map(
    (m) =>
      `- ${m.module} ${m.status === "planned" ? "(planned, реестров нет)" : m.version} — ${m.summary}${
        m.depends.length ? ` Зависит от: ${m.depends.join(", ")}.` : ""
      }`,
  )
  .join("\n")}

## Уровни соответствия FSP Pricing

Глубина описания прайса разная у разных операторов, поэтому модуль цен определяет уровни.
Оператор объявляет достигнутый; согласованным считается наименьший общий уровень.

${levels.map((l) => `- ${l["Уровень"]} ${l["Название"]}: ${l["Типичный источник"]}`).join("\n")}

## Ключевые решения

- Запрос сметы описывается операциями и объёмом, а не площадью под хранение (QUOTE-001).
- Формулы вывода площади и остатка стандартом не нормируются; применённые допущения обязаны
  возвращаться в ответе полем assumptions (QUOTE-002).
- Свободная мощность декларативна: стандарт не требует её верификации, актуальность выражается
  через updated_at (CAP-002).
- Непокрытие возвращается кодами закрытого реестра из ${unmet.length} причин, а не текстом (QUOTE-003).
- Коды стандартных услуг неизменяемы после публикации (CAT-001).
- Своя операция вне стандарта оформляется расширением x-<vendor>:<code> с указанием родительского
  модуля; расширение только добавляет поля и не переопределяет стандартные (PROFILE-007).

## Состав

- Услуг в каталоге: ${s.services} (${s.baseServices} базовых)
- Полей условий цены: ${s.conditions}
- Нормативных правил: ${rules.filter((r) => r.area !== "appendix").length}
- Проверок целостности в валидаторе: ${s.checks}
- Тарифных вариантов из реальных прайсов в приложении: ${s.imports}

## Страницы

- https://openfsp.ru/ — обзор
- https://openfsp.ru/modules/ — модули и правила версионирования
${mods.map((m) => `- https://openfsp.ru/modules/${m.module}/ — ${m.title}`).join("\n")}
- https://openfsp.ru/profile/ — манифест и правила согласования сторон
- https://openfsp.ru/rules/ — все нормативные правила
- https://openfsp.ru/artifacts/ — машиночитаемые артефакты
- https://openfsp.ru/appendix/ — разбор реальных прайсов (вне стандарта)
- https://openfsp.ru/changelog/ — что менялось

## Машиночитаемое

- https://openfsp.ru/1.0/<модуль>/schema.json — JSON Schema сущностей модуля
- https://openfsp.ru/1.0/<модуль>/module.json — манифест модуля
- https://openfsp.ru/1.0/<модуль>/<реестр>.json — реестр как массив объектов
- https://openfsp.ru/1.0/<модуль>/<реестр>.csv — реестр как CSV
- https://openfsp.ru/1.0/profile/fsp-profile.schema.json — схема манифеста стороны
- https://openfsp.ru/1.0/quote/openapi.yaml — OpenAPI модуля Quote
`;

  return new Response(text, {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Access-Control-Allow-Origin": "*" },
  });
}
