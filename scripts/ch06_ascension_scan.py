# -*- coding: utf-8 -*-
"""第 06 章：统计怪物文件里 ToughEnemies / DeadlyEnemies 的进阶值与普通值比例。
用法：python -I -X utf8 scripts/ch06_ascension_scan.py
注意：AscensionHelper.GetValueIfAscension(level, 进阶值, 普通值)，第二个参数是进阶值。
"""
import os, re, glob, statistics
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MON = os.path.join(ROOT, 'csharp', 'sts2_src', 'MegaCrit.Sts2.Core.Models.Monsters')
pat = re.compile(r'GetValueIfAscension\(AscensionLevel\.(ToughEnemies|DeadlyEnemies),\s*([\d.]+)m?f?,\s*([\d.]+)m?f?\)')
ctx = re.compile(r'(\w+)\s*(?:=>|=)\s*[^;]*$')
data = defaultdict(list)
other = Counter()
for p in glob.glob(os.path.join(MON, '*.cs')):
    t = open(p, encoding='utf-8').read()
    for line in t.splitlines():
        for m in pat.finditer(line):
            lvl, a, b = m.group(1), float(m.group(2)), float(m.group(3))
            name = 'HP' if re.search(r'Hp\b|MaxHp|MinInitialHp|MaxInitialHp', line) else 'other'
            data[(lvl, name)].append((a, b, os.path.basename(p)))
    # 非 GetValueIfAscension 的写法
    for m in re.finditer(r'HasAscension\(AscensionLevel\.(ToughEnemies|DeadlyEnemies)\)', t):
        other[m.group(1)] += 1

for k, v in sorted(data.items()):
    ratios = [a / b for a, b, _ in v if b]
    diffs = [a - b for a, b, _ in v]
    print(k, 'n=', len(v), 'ratio median %.3f min %.3f max %.3f' % (statistics.median(ratios), min(ratios), max(ratios)) if ratios else '',
          'diff median', statistics.median(diffs) if diffs else '')
    c = Counter(round(r, 2) for r in ratios)
    print('   common ratios', c.most_common(8))
print('HasAscension 写法次数', dict(other))
