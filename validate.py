# -*- coding: utf-8 -*-
"""
Валидатор целостности FSP — Fulfillment Services Protocol.
Проверяет реестры модулей, манифесты, уровни соответствия и примеры профилей.
Возврат: exit 0 — публикация разрешена; exit 1 — есть блокирующие ошибки.
Запуск: python3 validate.py [--root DIR]
"""
import csv, sys, os, json, re, glob, argparse
from collections import Counter

MODULES = ['core', 'pricing', 'capacity', 'quote', 'order', 'tracking']

# Область каждой проверки: модуль FSP или «Приложение» для реестров вне стандарта.
# Реестр appendix/integrity_checks.csv обязан совпадать с этим списком по имени и области.
AREAS = {
    'Дубли кодов услуг': 'core',
    'Неизвестные услуги в связях категорий': 'core',
    'Неизвестные категории в связях': 'core',
    'Дубли связей услуга-категория': 'core',
    'Неизвестные услуги в параметрах услуг': 'core',
    'Неизвестные коды параметров': 'core',
    'Дубли связей услуга-параметр': 'core',
    'Неиспользуемые параметры': 'core',
    'Отраслевые услуги без категории': 'core',
    'Базовые услуги без any': 'core',
    'Дубли кодов материалов': 'core',
    'Неизвестные услуги в метриках услуг': 'core',
    'Неизвестные коды метрик': 'core',
    'Дубли связей услуга-метрика': 'core',
    'Дубли кодов исключений': 'core',
    'Реестр пунктов назначения': 'core',
    'Исключённые коды попали в каталог': 'core',
    'Дубли полей сущностей модели': 'pricing',
    'Дубли полей условий цены': 'pricing',
    'Дубли кодов переменных диапазонов': 'pricing',
    'Дубли кодов областей диапазонов': 'pricing',
    'Переменные диапазонов без источника значения': 'pricing',
    'Неизвестные области в переменных диапазонов': 'pricing',
    'Недопустимые режимы диапазонов': 'pricing',
    'Уровни соответствия и методы расчёта': 'pricing',
    'Сущности модели цены без уровня соответствия': 'pricing',
    'Коды причин непокрытия': 'quote',
    'Манифесты модулей заполнены': 'Протокол',
    'Реестры модулей не расходятся с файлами': 'Протокол',
    'Зависимости модулей': 'Протокол',
    'Префиксы правил не объявлены в манифесте': 'Протокол',
    'Дубли ID нормативных правил': 'Протокол',
    'Перечисления схем расходятся с реестрами': 'Протокол',
    'Ссылки $ref в схемах модулей': 'Протокол',
    'Примеры манифестов в profile/examples': 'Протокол',
    'Ступенчатые строки импорта без обязательных полей': 'Приложение',
    'Методы расчёта импорта вне реестра': 'Приложение',
    'Единицы начисления импорта не разрешены для услуги': 'Приложение',
    'Строки импорта с целью price_adjustment': 'Приложение',
    'Шкалы, области и режимы импорта вне реестров': 'Приложение',
    'Разрывы и пересечения ступеней в импорте': 'Приложение',
    'Реестр проверок расходится с валидатором': 'Приложение',
}
VERSION_RE = re.compile(r'^[0-9]+\.[0-9]+$')
EXT_RE = re.compile(r'^x-[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$')
ROOT = os.path.dirname(os.path.abspath(__file__))


def module_dir(root, module):
    """Каталог модуля или приложения. Приложение не входит в стандарт."""
    return os.path.join(root, 'appendix') if module == 'appendix' else os.path.join(root, 'modules', module)


def load(qualified, signal_col, root):
    """Читает реестр по имени вида <модуль>/<реестр>: находит строку-заголовок, парсит ниже в dict-и."""
    module, name = qualified.split('/')
    path = os.path.join(module_dir(root, module), name + '.csv')
    with open(path, encoding='utf-8') as f:
        rows = list(csv.reader(f))
    hdr_idx = next((i for i, r in enumerate(rows) if signal_col in r), None)
    if hdr_idx is None:
        raise SystemExit("FATAL: в %s.csv не найдена колонка-сигнал '%s'" % (qualified, signal_col))
    hdr = rows[hdr_idx]
    out = []
    for r in rows[hdr_idx + 1:]:
        if not any(c.strip() for c in r):
            continue
        d = {hdr[i]: (r[i] if i < len(r) else '') for i in range(len(hdr))}
        # отбросить строки-призраки экспорта: значимо только если есть непустое текстовое поле
        if any(str(v).strip() and str(v).strip() not in ('True', 'False') for v in d.values()):
            out.append(d)
    return out


def split_list(v):
    return [x.strip() for x in str(v).split(';') if x.strip()]


def load_manifests(root):
    out = {}
    for m in MODULES:
        p = os.path.join(module_dir(root, m), 'module.json')
        if not os.path.exists(p):
            raise SystemExit("FATAL: нет манифеста %s" % os.path.relpath(p, root))
        with open(p, encoding='utf-8') as f:
            out[m] = json.load(f)
    return out


def load_defs(root, module):
    """$defs схемы модуля; пустой словарь, если схемы нет."""
    p = os.path.join(module_dir(root, module), 'schema.json')
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f).get('$defs', {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    R = ap.parse_args().root

    man = load_manifests(R)

    # ---------- реестры ----------
    services   = load('core/catalog_services', 'Код', R)
    categories = load('core/categories', 'Код', R)
    metrics    = load('core/billing_metrics', 'Код', R)
    params     = load('core/parameters', 'Код', R)
    materials  = load('core/materials', 'Код', R)
    exclusions = load('core/exclusions', 'code', R)
    cat_links  = load('core/category_links', 'Код услуги', R)
    svc_params = load('core/service_parameters', 'Код услуги', R)
    svc_metrics= load('core/service_metrics', 'Код услуги', R)
    model      = load('pricing/price_model', 'Поле', R)
    conditions = load('pricing/price_conditions', 'Поле', R)
    cond_ops   = load('pricing/condition_operators', 'Оператор', R)
    calc_methods = load('pricing/calculation_methods', 'Код', R)
    levels     = load('pricing/conformance_levels', 'Уровень', R)
    derived    = load('core/derived_metrics', 'Метрика', R)
    tier_vars  = load('pricing/tier_variables', 'Код', R)
    tier_scopes= load('pricing/tier_scopes', 'Код', R)
    storage_ty = load('capacity/storage_types', 'Код', R)
    destinations = load('core/destinations', 'Код', R)
    unmet      = load('quote/unmet_reasons', 'Код', R)
    # Разбор реальных прайсов операторов — данные их владельцев, в канон не входят.
    # Есть файл — импортные проверки выполняются, нет — помечаются пропущенными.
    has_imports = os.path.exists(os.path.join(module_dir(R, 'appendix'), 'price_imports.csv'))
    imports    = load('appendix/price_imports', 'import_id', R) if has_imports else []
    declared   = load('appendix/integrity_checks', 'Проверка', R)

    svc_codes = [s['Код'] for s in services]
    svc_set   = set(svc_codes)
    cat_set   = set(c['Код'] for c in categories)
    metric_set= set(m['Код'] for m in metrics)
    param_set = set(p['Код'] for p in params)
    svc_type  = {s['Код']: s.get('Тип услуги', '') for s in services}
    level_set = set(l['Уровень'] for l in levels)

    fails = []    # (название проверки, [подробности])
    skipped = set()  # проверки без входных данных: не выполнены, но и не провалены

    def check(name, errors):
        fails.append((name, errors))

    def skip(name, why):
        skipped.add((name, why))
        fails.append((name, []))

    # ---------- каталог и связи (FSP Core) ----------
    check('Дубли кодов услуг',
          [c for c, n in Counter(svc_codes).items() if n > 1])
    check('Неизвестные услуги в связях категорий',
          [l['Код услуги'] for l in cat_links if l['Код услуги'] not in svc_set])
    check('Неизвестные категории в связях',
          [l['Код категории'] for l in cat_links if l['Код категории'] not in cat_set])
    check('Дубли связей услуга-категория',
          [k for k, n in Counter((l['Код услуги'], l['Код категории']) for l in cat_links).items() if n > 1])
    check('Неизвестные услуги в параметрах услуг',
          [p['Код услуги'] for p in svc_params if p['Код услуги'] not in svc_set])
    check('Неизвестные коды параметров',
          [p['Код параметра'] for p in svc_params if p['Код параметра'] not in param_set])
    check('Дубли связей услуга-параметр',
          [k for k, n in Counter((p['Код услуги'], p['Код параметра']) for p in svc_params).items() if n > 1])
    used_params = set(p['Код параметра'] for p in svc_params) | set(c['Поле'] for c in conditions)
    check('Неиспользуемые параметры',
          [c for c in param_set if c not in used_params])
    linked_specific = set(l['Код услуги'] for l in cat_links if l['Код категории'] != 'any')
    check('Отраслевые услуги без категории',
          [c for c, t in svc_type.items() if t == 'industry' and c not in linked_specific])
    linked_any = set(l['Код услуги'] for l in cat_links if l['Код категории'] == 'any')
    check('Базовые услуги без any',
          [c for c, t in svc_type.items() if t == 'base' and c not in linked_any])
    check('Дубли кодов материалов',
          [c for c, n in Counter(m['Код'] for m in materials).items() if n > 1])
    check('Неизвестные услуги в метриках услуг',
          [m['Код услуги'] for m in svc_metrics if m['Код услуги'] not in svc_set])
    check('Неизвестные коды метрик',
          [m['Код метрики'] for m in svc_metrics if m['Код метрики'] not in metric_set])
    check('Дубли связей услуга-метрика',
          [k for k, n in Counter((m['Код услуги'], m['Код метрики']) for m in svc_metrics).items() if n > 1])
    check('Дубли кодов исключений',
          [c for c, n in Counter(e['code'] for e in exclusions).items() if n > 1])
    check('Исключённые коды попали в каталог',
          [e['code'] for e in exclusions if e['code'] in svc_set])

    core_defs = load_defs(R, 'core')
    dest_types = set(core_defs.get('destination_type', {}).get('enum', []))
    dest_markets = set(core_defs.get('marketplace', {}).get('enum', []))
    dest_statuses = set(core_defs.get('destination', {}).get('properties', {})
                        .get('status', {}).get('enum', []))
    errs = ['дубль кода %s' % c for c, n in Counter(d['Код'] for d in destinations).items() if n > 1]
    for d in destinations:
        if d['Тип'] not in dest_types:
            errs.append('%s: тип %r вне схемы' % (d['Код'], d['Тип']))
        if d['Маркетплейс'] and d['Маркетплейс'] not in dest_markets:
            errs.append('%s: маркетплейс %r вне схемы' % (d['Код'], d['Маркетплейс']))
        if not re.match(r'^[A-Z]{2}$', d.get('Страна', '')):
            errs.append('%s: страна %r не в формате ISO 3166-1 alpha-2' % (d['Код'], d.get('Страна')))
        if d['Статус'] not in dest_statuses:
            errs.append('%s: статус %r вне схемы' % (d['Код'], d['Статус']))
        if not d['Название'].strip():
            errs.append('%s: пустое название' % d['Код'])
    check('Реестр пунктов назначения', errs)

    # ---------- модель и условия цены (FSP Pricing) ----------
    check('Дубли полей сущностей модели',
          [k for k, n in Counter((m['Сущность'], m['Поле']) for m in model).items() if n > 1])
    check('Дубли полей условий цены',
          [c for c, n in Counter(x['Поле'] for x in conditions).items() if n > 1])
    check('Дубли кодов переменных диапазонов',
          [c for c, n in Counter(v['Код'] for v in tier_vars).items() if n > 1])
    check('Дубли кодов областей диапазонов',
          [c for c, n in Counter(s['Код'] for s in tier_scopes).items() if n > 1])
    source_sets = {
        'условие': set(c['Поле'] for c in conditions),
        'метрика': metric_set,
        'расчётная метрика': set(d['Метрика'] for d in derived),
    }
    check('Переменные диапазонов без источника значения',
          ['%s (%s)' % (v['Код'], v['Источник значения']) for v in tier_vars
           if v['Код'] not in source_sets.get(v['Источник значения'].strip(), set())])
    scope_set = set(s['Код'] for s in tier_scopes)
    check('Неизвестные области в переменных диапазонов',
          ['%s → %s' % (v['Код'], s) for v in tier_vars
           for s in split_list(v['Допустимые области']) if s not in scope_set])
    check('Недопустимые режимы диапазонов',
          ['%s → %s' % (v['Код'], m) for v in tier_vars
           for m in split_list(v['Допустимые режимы']) if m not in ('slab', 'progressive')])

    # ---------- уровни соответствия (FSP Pricing) ----------
    errs = []
    for l in levels:
        inc = l['Включает'].strip()
        if inc and inc not in level_set:
            errs.append('уровень %s включает неизвестный %s' % (l['Уровень'], inc))
        if inc == l['Уровень']:
            errs.append('уровень %s включает сам себя' % l['Уровень'])
        for col in ('Условия', 'Ступени'):
            if l[col].strip() not in ('да', 'нет'):
                errs.append('уровень %s: колонка «%s» = %r, ожидается да/нет' % (l['Уровень'], col, l[col]))
    tiers_allowed = set(l['Уровень'] for l in levels if l['Ступени'].strip() == 'да')
    for m in calc_methods:
        if m['Уровень'] not in level_set:
            errs.append('метод %s отнесён к неизвестному уровню %s' % (m['Код'], m['Уровень']))
        elif m['Требует ступени'].strip() == 'да' and m['Уровень'] not in tiers_allowed:
            errs.append('метод %s требует ступени, но уровень %s их не допускает' % (m['Код'], m['Уровень']))
    check('Уровни соответствия и методы расчёта', errs)

    model_entities = set(m['Сущность'] for m in model)
    level_entities = Counter(e for l in levels for e in split_list(l['Сущности уровня']))
    errs = ['%s: нет уровня' % e for e in sorted(model_entities - set(level_entities))]
    errs += ['%s: уровень указан %d раза' % (e, n) for e, n in sorted(level_entities.items()) if n > 1]
    errs += ['%s: уровень указан, но сущности нет в модели цены' % e
             for e in sorted(set(level_entities) - model_entities)]
    check('Сущности модели цены без уровня соответствия', errs)

    # ---------- причины непокрытия (FSP Quote) ----------
    errs = [c for c, n in Counter(u['Код'] for u in unmet).items() if n > 1]
    errs += ['%s: влияние %r, ожидается exclude/partial' % (u['Код'], u['Влияние'])
             for u in unmet if u['Влияние'].strip() not in ('exclude', 'partial')]
    errs += ['%s: не заполнено «Что делать оператору»' % u['Код']
             for u in unmet if not u['Что делать оператору'].strip()]
    check('Коды причин непокрытия', errs)

    # ---------- манифесты модулей ----------
    errs = []
    REQUIRED = ('module', 'title', 'version', 'status', 'summary', 'depends', 'registries', 'rule_prefixes')
    for m in MODULES:
        d = man[m]
        for f in REQUIRED:
            if f not in d:
                errs.append('%s: нет поля %s' % (m, f))
        if d.get('module') != m:
            errs.append('%s: поле module = %r' % (m, d.get('module')))
        if not VERSION_RE.match(str(d.get('version', ''))):
            errs.append('%s: версия %r не в формате MAJOR.MINOR' % (m, d.get('version')))
        published = d.get('versions')
        if d.get('status') != 'planned':
            if not published:
                errs.append('%s: не объявлен список опубликованных версий' % m)
            else:
                bad = [v for v in published if not VERSION_RE.match(str(v))]
                if bad:
                    errs.append('%s: версии вне формата MAJOR.MINOR: %s' % (m, bad))
                if published[-1] != d.get('version'):
                    errs.append('%s: текущая версия %s не последняя в списке %s' % (m, d.get('version'), published))
                if len(set(published)) != len(published):
                    errs.append('%s: дубли в списке версий' % m)
        if d.get('status') not in ('stable', 'draft', 'planned'):
            errs.append('%s: статус %r вне stable/draft/planned' % (m, d.get('status')))
        for key in ('schema', 'api', 'profile'):
            if d.get(key) and not os.path.exists(os.path.join(module_dir(R, m), d[key])):
                errs.append('%s: %s указывает на отсутствующий файл %s' % (m, key, d[key]))
    check('Манифесты модулей заполнены', errs)

    errs = []
    for m in MODULES:
        declared_reg = set(man[m].get('registries', []))
        on_disk = set(os.path.splitext(os.path.basename(p))[0]
                      for p in glob.glob(os.path.join(module_dir(R, m), '*.csv')))
        for r in sorted(declared_reg - on_disk):
            errs.append('%s: реестр %s объявлен, но файла нет' % (m, r))
        for r in sorted(on_disk - declared_reg):
            errs.append('%s: файл %s.csv не объявлен в манифесте' % (m, r))
        if man[m]['status'] == 'planned' and declared_reg:
            errs.append('%s: модуль planned, но объявляет реестры' % m)
    check('Реестры модулей не расходятся с файлами', errs)

    errs = []
    for m in MODULES:
        for dep in man[m].get('depends', []):
            if dep not in man:
                errs.append('%s: зависит от неизвестного модуля %s' % (m, dep))
            elif dep == m:
                errs.append('%s: зависит от себя' % m)
            elif man[m]['status'] == 'stable' and man[dep]['status'] == 'planned':
                errs.append('%s (stable) зависит от %s (planned)' % (m, dep))

    def path_exists(a, b, seen=None):
        """Есть ли путь по зависимостям от a к b."""
        seen = seen or set()
        for dep in man.get(a, {}).get('depends', []):
            if dep in seen:
                continue
            seen.add(dep)
            if dep == b or path_exists(dep, b, seen):
                return True
        return False

    for m in MODULES:
        if path_exists(m, m):
            errs.append('%s: цикл в зависимостях' % m)
    check('Зависимости модулей', errs)

    # ---------- нормативные правила ----------
    errs, all_rule_ids = [], []
    for m in MODULES:
        if 'rules' not in man[m].get('registries', []):
            continue
        prefixes = set(man[m]['rule_prefixes'])
        for row in load('%s/rules' % m, 'ID', R):
            rid = row['ID'].strip()
            all_rule_ids.append(rid)
            if rid.split('-')[0] not in prefixes:
                errs.append('%s: правило %s с необъявленным префиксом' % (m, rid))
            if not row['Правило'].strip():
                errs.append('%s: правило %s без текста' % (m, rid))
    check('Префиксы правил не объявлены в манифесте', errs)
    check('Дубли ID нормативных правил',
          [r for r, n in Counter(all_rule_ids).items() if n > 1])

    # ---------- перечисления схем против реестров ----------
    errs = []

    def enum_matches(module, def_name, expected, label):
        defs = load_defs(R, module)
        got = set(defs.get(def_name, {}).get('enum', []))
        if got != set(expected):
            miss = sorted(set(expected) - got)
            extra = sorted(got - set(expected))
            errs.append('%s.%s: нет %s, лишние %s (реестр %s)' % (module, def_name, miss or '—', extra or '—', label))

    enum_matches('capacity', 'storage_type', [s['Код'] for s in storage_ty], 'storage_types')
    enum_matches('capacity', 'temp_mode',
                 set(m for s in storage_ty for m in split_list(s['Допустимые режимы'])), 'storage_types')
    enum_matches('pricing', 'calculation_method', [m['Код'] for m in calc_methods], 'calculation_methods')
    enum_matches('pricing', 'condition_operator', [o['Оператор'] for o in cond_ops], 'condition_operators')
    enum_matches('quote', 'unmet_code', [u['Код'] for u in unmet], 'unmet_reasons')
    enum_matches('quote', 'pricing_level', sorted(level_set), 'conformance_levels')
    check('Перечисления схем расходятся с реестрами', errs)

    # ---------- ссылки между схемами ----------
    def collect_refs(node, out):
        if isinstance(node, dict):
            if isinstance(node.get('$ref'), str):
                out.append(node['$ref'])
            for v in node.values():
                collect_refs(v, out)
        elif isinstance(node, list):
            for v in node:
                collect_refs(v, out)

    errs = []
    for m in MODULES:
        p = os.path.join(module_dir(R, m), 'schema.json')
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as f:
            doc = json.load(f)
        refs = []
        collect_refs(doc, refs)
        for ref in sorted(set(refs)):
            target, _, pointer = ref.partition('#')
            if target:
                tpath = os.path.normpath(os.path.join(module_dir(R, m), target))
                if not os.path.exists(tpath):
                    errs.append('%s: $ref на отсутствующий файл %s' % (m, target)); continue
                with open(tpath, encoding='utf-8') as f:
                    tdoc = json.load(f)
            else:
                tdoc = doc
            node = tdoc
            for part in [x for x in pointer.split('/') if x]:
                if not isinstance(node, dict) or part not in node:
                    errs.append('%s: $ref %s не разрешается' % (m, ref)); node = None; break
                node = node[part]
    check('Ссылки $ref в схемах модулей', errs)

    # ---------- примеры манифестов ----------
    errs = []
    examples = sorted(glob.glob(os.path.join(R, 'profile', 'examples', '*.json')))
    if not examples:
        errs.append('в profile/examples нет ни одного примера манифеста')
    for p in examples:
        rel = os.path.relpath(p, R)
        try:
            with open(p, encoding='utf-8') as f:
                prof = json.load(f)
        except ValueError as e:
            errs.append('%s: не разбирается как JSON (%s)' % (rel, e))
            continue
        if not VERSION_RE.match(str(prof.get('fsp', ''))):
            errs.append('%s: fsp = %r не в формате MAJOR.MINOR' % (rel, prof.get('fsp')))
        if prof.get('party', {}).get('role') not in ('operator', 'requester', 'aggregator'):
            errs.append('%s: роль %r неизвестна' % (rel, prof.get('party', {}).get('role')))
        mods = prof.get('modules', {})
        for name, decl in mods.items():
            if name not in man:
                errs.append('%s: объявлен неизвестный модуль %s' % (rel, name))
                continue
            if man[name]['status'] == 'planned':
                errs.append('%s: объявлен модуль %s со статусом planned' % (rel, name))
            published = man[name].get('versions', [man[name]['version']])
            for v in decl.get('versions', []):
                if v not in published:
                    errs.append('%s: %s версии %s не существует (опубликованы %s)' % (rel, name, v, published))
            if decl.get('level') and decl['level'] not in level_set:
                errs.append('%s: %s уровень %s вне реестра уровней' % (rel, name, decl['level']))
            if decl.get('level') and name != 'pricing':
                errs.append('%s: модуль %s не определяет уровней соответствия' % (rel, name))
            for dep in man[name].get('depends', []):
                if dep not in mods:
                    errs.append('%s: %s объявлен без зависимости %s (PROFILE-002)' % (rel, name, dep))
        for ext, decl in (prof.get('extensions') or {}).items():
            if not EXT_RE.match(ext):
                errs.append('%s: имя расширения %s не по шаблону x-<vendor>:<code>' % (rel, ext))
            if decl.get('module') not in mods:
                errs.append('%s: расширение %s ссылается на необъявленный модуль %r' % (rel, ext, decl.get('module')))
        for name in (prof.get('endpoints') or {}):
            if name not in mods:
                errs.append('%s: точка входа для необъявленного модуля %s' % (rel, name))
    check('Примеры манифестов в profile/examples', errs)

    # ---------- импорт прайсов (приложение) ----------
    if not has_imports:
        skip('Ступенчатые строки импорта без обязательных полей', 'нет данных разбора прайсов')
        skip('Методы расчёта импорта вне реестра', 'нет данных разбора прайсов')
        skip('Единицы начисления импорта не разрешены для услуги', 'нет данных разбора прайсов')
        skip('Строки импорта с целью price_adjustment', 'нет данных разбора прайсов')
        skip('Шкалы, области и режимы импорта вне реестров', 'нет данных разбора прайсов')
        skip('Разрывы и пересечения ступеней в импорте', 'нет данных разбора прайсов')
    else:
        TIER_REQ = ('tier_group', 'tier_variable', 'tier_scope', 'tier_mode')
        errs = []
        for i in imports:
            tiered = i.get('calculation_method', '') == 'tiered'
            filled = [c for c in TIER_REQ if i.get(c, '').strip()]
            if tiered and len(filled) < len(TIER_REQ):
                errs.append('%s: не заполнено %s' % (i['import_id'], [c for c in TIER_REQ if c not in filled]))
            if not tiered and filled:
                errs.append('%s: tier_* заполнены при calculation_method=%s' % (i['import_id'], i.get('calculation_method', '')))
            if tiered and not i.get('tier_from', '').strip():
                errs.append('%s: пустая нижняя граница диапазона' % i['import_id'])
        check('Ступенчатые строки импорта без обязательных полей', errs)

        method_set = set(m['Код'] for m in calc_methods)
        rule_rows = [i for i in imports if i.get('target_entity', '').strip() != 'price_adjustment']
        check('Методы расчёта импорта вне реестра',
              ['%s: %s' % (i['import_id'], i['calculation_method']) for i in rule_rows
               if i.get('calculation_method', '').strip() and i['calculation_method'].strip() not in method_set])

        adj_types = set(load_defs(R, 'pricing').get('price_adjustment', {})
                        .get('properties', {}).get('adjustment_type', {}).get('enum', []))
        errs = []
        for i in imports:
            target = i.get('target_entity', '').strip()
            if target not in ('price_rule', 'price_adjustment'):
                errs.append('%s: target_entity = %r вне price_rule/price_adjustment' % (i['import_id'], target))
            elif target == 'price_adjustment':
                if i.get('calculation_method', '').strip():
                    errs.append('%s: модификатор не имеет метода расчёта' % i['import_id'])
                if i.get('adjustment_type', '').strip() not in adj_types:
                    errs.append('%s: adjustment_type = %r вне схемы модуля цен' % (i['import_id'], i.get('adjustment_type')))
            elif i.get('adjustment_type', '').strip():
                errs.append('%s: adjustment_type заполнен у строки-правила' % i['import_id'])
        check('Строки импорта с целью price_adjustment', errs)

        # Единица начисления обязана быть разрешена для услуги: источник истины —
        # реестр «Метрики услуг» (CAT-010), а не текст строки прайса.
        allowed_metrics = {}
        for r in svc_metrics:
            allowed_metrics.setdefault(r['Код услуги'], set()).add(r['Код метрики'])
        errs = []
        for i in imports:
            metric = i.get('billing_metric', '').strip()
            # ambiguous — разбор строки не завершён и ждёт ответа оператора;
            # спрашивать с него соответствие реестру рано, он отслеживается в residual_gaps
            if not metric or i.get('mapping_status', '').strip() == 'ambiguous':
                continue
            for code in split_list(i.get('service_codes', '')):
                if code in allowed_metrics and metric not in allowed_metrics[code]:
                    errs.append('%s: %s не допускает единицу %s (разрешены %s)'
                                % (i['import_id'], code, metric, ', '.join(sorted(allowed_metrics[code]))))
        check('Единицы начисления импорта не разрешены для услуги', errs)

        var_modes  = {v['Код']: set(split_list(v['Допустимые режимы'])) for v in tier_vars}
        var_scopes = {v['Код']: set(split_list(v['Допустимые области'])) for v in tier_vars}
        errs = []
        for i in imports:
            v, s, m = i.get('tier_variable', ''), i.get('tier_scope', ''), i.get('tier_mode', '')
            if not v:
                continue
            if v not in var_modes:
                errs.append('%s: неизвестная шкала %s' % (i['import_id'], v)); continue
            if s not in scope_set:
                errs.append('%s: неизвестная область %s' % (i['import_id'], s))
            elif s not in var_scopes[v]:
                errs.append('%s: область %s не разрешена для шкалы %s' % (i['import_id'], s, v))
            if m not in var_modes[v]:
                errs.append('%s: режим %s не разрешён для шкалы %s' % (i['import_id'], m, v))
        check('Шкалы, области и режимы импорта вне реестров', errs)

        groups = {}
        for i in imports:
            if i.get('tier_group', '').strip():
                groups.setdefault(i['tier_group'], []).append(i)
        errs = []
        for g, items in sorted(groups.items()):
            try:
                tiers = sorted(((float(i['tier_from']),
                                 float(i['tier_to']) if i.get('tier_to', '').strip() else float('inf'),
                                 i['import_id']) for i in items), key=lambda x: x[0])
            except ValueError:
                errs.append('%s: нечисловая граница диапазона' % g); continue
            if len(set((i.get('tier_variable'), i.get('tier_scope'), i.get('tier_mode')) for i in items)) > 1:
                errs.append('%s: строки группы расходятся по шкале, области или режиму' % g)
            for (f, t, imp), (nf, nt, nimp) in zip(tiers, tiers[1:]):
                if t > nf:
                    errs.append('%s: пересечение %s и %s' % (g, imp, nimp))
                elif t < nf:
                    errs.append('%s: разрыв между %s и %s' % (g, imp, nimp))
            for f, t, imp in tiers:
                if f >= t:
                    errs.append('%s: пустой диапазон в %s' % (g, imp))
            if len([1 for f, t, _ in tiers if t == float('inf')]) != 1:
                errs.append('%s: верхняя ступень должна быть ровно одна и открытая' % g)
        check('Разрывы и пересечения ступеней в импорте', errs)

    # ---------- реестр проверок против кода ----------
    FINAL = 'Реестр проверок расходится с валидатором'
    implemented = [(name, AREAS.get(name, '?')) for name, _ in fails] + [(FINAL, AREAS.get(FINAL, '?'))]
    declared_pairs = [(d['Проверка'], d['Область']) for d in declared]
    errs = ['%s: нет области в AREAS' % n for n, a in implemented if a == '?']
    errs += ['%s (%s): реализована, но не объявлена в реестре' % (n, a)
             for n, a in implemented if (n, a) not in declared_pairs]
    errs += ['%s (%s): объявлена в реестре, но не реализована' % (n, a)
             for n, a in declared_pairs if (n, a) not in implemented]
    check('Реестр проверок расходится с валидатором', errs)

    total = 0
    print("Валидатор целостности FSP — Fulfillment Services Protocol")
    print("=" * 62)
    why = {n: w for n, w in skipped}
    for name, errs in fails:
        status = "SKIP" if name in why else ("OK" if not errs else "FAIL (%d)" % len(errs))
        note = "  — %s" % why[name] if name in why else ""
        print("  [%-9s] %s%s" % (status, name, note))
        if errs:
            for e in errs[:8]:
                print("               → %s" % (e,))
            total += len(errs)
    print("=" * 62)
    print("Проверок: %d, из них пропущено %d. Модулей: %d (%d stable, %d planned)." % (
        len(fails), len(skipped), len(MODULES),
        sum(1 for m in MODULES if man[m]['status'] == 'stable'),
        sum(1 for m in MODULES if man[m]['status'] == 'planned')))
    if total:
        print("БЛОКИРУЮЩИХ ОШИБОК: %d — публикация запрещена." % total)
        sys.exit(1)
    print("Ошибок нет. Публикация разрешена (READY).")
    sys.exit(0)


if __name__ == '__main__':
    main()
