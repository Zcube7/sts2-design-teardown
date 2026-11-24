"""第 03 章辅助：把每个遗物的源码要素（稀有度/池/标志位/覆写的钩子/IsAllowed 条件）+ 简中描述
压成一行，供人工分类时通读。输出 logs/ch03_relic_dump.txt。

python -I -X utf8 scripts/ch03_dump_relics.py
"""
import csv, os, re, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
RELICS = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Relics')
POOLS = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.RelicPools')


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def pools():
    m = collections.defaultdict(list)
    for p in glob.glob(os.path.join(POOLS, '*.cs')):
        pool = os.path.basename(p)[:-3].replace('RelicPool', '')
        for c in re.findall(r'ModelDb\.Relic<(\w+)>\(\)', read(p)):
            if pool not in m[c]:
                m[c].append(pool)
    return m


HOOK_RE = re.compile(r'override\s+(?:async\s+)?[\w<>\[\]?, ]+?\s+(\w+)\(')


def parse(src):
    d = {}
    m = re.search(r'RelicRarity Rarity => RelicRarity\.(\w+)', src)
    d['rarity'] = m.group(1) if m else ''
    flags = []
    for f in ['HasUponPickupEffect', 'ShowCounter', 'IsStackable', 'SpawnsPets', 'AddsPet', 'ShouldFlashOnPlayer']:
        mm = re.search(r'override bool ' + f + r' => (\w+);', src)
        if mm:
            flags.append(f'{f}={mm.group(1)}')
    if re.search(r'override bool IsUsedUp', src):
        flags.append('IsUsedUp*')
    if re.search(r'override bool IsAllowedInShops => false', src):
        flags.append('NoShop')
    mm = re.search(r'override int MerchantCost => (\d+)', src)
    if mm:
        flags.append('Cost=' + mm.group(1))
    d['flags'] = ' '.join(flags)
    hooks = [h for h in HOOK_RE.findall(src) if h not in ('IsAllowed',)]
    d['hooks'] = ','.join(dict.fromkeys(hooks))
    mm = re.search(r'override bool IsAllowed\(IRunState runState\)\s*\{(.*?)\n\t\}', src, re.S)
    d['allowed'] = re.sub(r'\s+', ' ', mm.group(1)).strip()[:160] if mm else ''
    return d


def main():
    base = {r['cls']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'csv', 'relics.csv'), encoding='utf-8-sig'))}
    pm = pools()
    out = []
    for p in sorted(glob.glob(os.path.join(RELICS, '*.cs'))):
        cls = os.path.basename(p)[:-3]
        src = read(p)
        if ': RelicModel' not in src:
            continue
        d = parse(src)
        b = base.get(cls, {})
        desc = re.sub(r'\[/?\w+\]', '', b.get('desc_zh', ''))
        out.append(f"{cls}|{b.get('name_zh','')}|{d['rarity']}|{'+'.join(pm.get(cls, []))}|{d['flags']}|{d['hooks']}|{d['allowed']}|{b.get('vars','')}|{desc}")
    os.makedirs(os.path.join(ROOT, 'logs'), exist_ok=True)
    with open(os.path.join(ROOT, 'logs', 'ch03_relic_dump.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(len(out))


if __name__ == '__main__':
    main()
