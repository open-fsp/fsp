# -*- coding: utf-8 -*-
"""
Проверка внутренних ссылок собранной витрины: каждая ссылка на свой домен обязана
указывать на существующий файл в site/dist. Возврат 1 — есть битые ссылки.
Запуск: python3 site/check_links.py   (после npm run build)
"""
import os, re, sys

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')

if not os.path.isdir(DIST):
    sys.exit('FATAL: нет site/dist — сначала npm run build')

pages = set()
for root, _, files in os.walk(DIST):
    for f in files:
        rel = '/' + os.path.relpath(os.path.join(root, f), DIST).replace(os.sep, '/')
        pages.add(rel)
        if rel.endswith('/index.html'):
            pages.add(rel[: -len('index.html')])

broken = {}
for root, _, files in os.walk(DIST):
    for f in files:
        if not f.endswith('.html'):
            continue
        src = '/' + os.path.relpath(os.path.join(root, f), DIST).replace(os.sep, '/')
        html = open(os.path.join(root, f), encoding='utf-8').read()
        for href in sorted(set(re.findall(r'href="(/[^"#]*)', html))):
            target = href.split('?')[0]
            if target in pages:
                continue
            if target.rstrip('/') + '/index.html' in pages or target + 'index.html' in pages:
                continue
            broken.setdefault(src, []).append(href)

total = sum(len(v) for v in broken.values())
print('Проверка ссылок витрины openfsp.ru')
print('=' * 48)
print('  файлов: %d' % len([p for p in pages if not p.endswith('/')]))
print('  битых внутренних ссылок: %d' % total)
for src, hrefs in sorted(broken.items()):
    for h in hrefs:
        print('    %s → %s' % (src, h))
if total:
    sys.exit(1)
print('=' * 48)
print('Ошибок нет.')
