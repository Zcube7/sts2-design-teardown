"""从 ILSpy 反编译的 sts2 源码 + PCK 本地化 JSON 抽取全部内容模型 -> data/csv/*.csv

python -I -X utf8 scripts/s1_extract_models.py
(在 outputs/sts2_rea_Claude 目录下跑)
"""
import csv, json, os, re, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization')
OUT = os.path.join(ROOT, 'data', 'csv')
os.makedirs(OUT, exist_ok=True)


def ns(name):
    return os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.' + name)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def snake(cls):
    return re.sub(r'(?<=[A-Za-z0-9])([A-Z])', r'_\1', cls).upper()


_loc = {}


def loc(lang, table):
    k = (lang, table)
    if k not in _loc:
        p = os.path.join(LOC, lang, table + '.json')
        _loc[k] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    return _loc[k]


def L(table, mid, field, lang='zhs'):
    return loc(lang, table).get(f'{mid}.{field}', '')


def clean(s):
    return re.sub(r'\s+', ' ', s).strip()


def classes(folder):
    out = {}
    for p in sorted(glob.glob(os.path.join(ns(folder), '*.cs'))):
        cls = os.path.splitext(os.path.basename(p))[0]
        out[cls] = read(p)
    return out


def pool_members(folder, kind):
    """CardPools / RelicPools / PotionPools -> {member_cls: [pool,...]}"""
    m = collections.defaultdict(list)
    for p in glob.glob(os.path.join(ns(folder), '*.cs')):
        pool = os.path.splitext(os.path.basename(p))[0].replace(kind + 'Pool', '')
        for c in re.findall(r'ModelDb\.' + kind + r'<(\w+)>\(\)', read(p)):
            if pool not in m[c]:
                m[c].append(pool)
    return m


def vars_of(src):
    """CanonicalVars 里的 new XxxVar(...) -> 'Damage=6; Vulnerable=2' 形式"""
    seg = re.search(r'CanonicalVars\s*=>(.*?)(?:;\s*\n\s*(?:public|protected|private|internal)|\n\t\}\);|\);\s*\n)', src, re.S)
    if not seg:
        return ''
    body = seg.group(1)
    items = []
    for m in re.finditer(r'new (\w+?)Var(?:<(\w+)>)?\(([^()]*(?:\([^()]*\)[^()]*)*)\)', body):
        kind, gen, args = m.group(1), m.group(2), m.group(3)
        args = [a.strip() for a in re.split(r',(?![^()]*\))', args)] if args.strip() else []
        name = gen.replace('Power', '') if gen else kind
        if kind in ('Dynamic', 'Int', 'String', 'Bool') and args and args[0].startswith('"'):
            name, args = args[0].strip('"'), args[1:]
        val = args[0].rstrip('m') if args else ''
        items.append(f'{name}={val}')
    return '; '.join(items)


def upgrades_of(src):
    m = re.search(r'void OnUpgrade\(\)\s*\{(.*?)\n\t\}', src, re.S)
    if not m:
        # 没有 OnUpgrade、靠 IsUpgraded 分支改行为的牌（如 Armaments）
        return 'behavior(IsUpgraded)' if 'IsUpgraded' in src else ''
    body = m.group(1)
    out = []
    for mm in re.finditer(r'DynamicVars(?:\[\s*"(\w+)"\s*\]|\.(\w+))\.UpgradeValueBy\(([-\d.]+)m?\)', body):
        out.append(f'{mm.group(1) or mm.group(2)}+{mm.group(3)}')
    for mm in re.finditer(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body):
        out.append(f'Cost{mm.group(1)}')
    for mm in re.finditer(r'(AddKeyword|RemoveKeyword)\(CardKeyword\.(\w+)\)', body):
        out.append(('+' if mm.group(1) == 'AddKeyword' else '-') + mm.group(2))
    for mm in re.finditer(r'StarCost\.UpgradeBy\((-?\d+)\)', body):
        out.append(f'Star{mm.group(1)}')
    if not out and body.strip():
        out.append('custom')
    return '; '.join(out)


def summary_doc(src):
    m = re.search(r'/// <summary>\s*\n(.*?)/// </summary>\s*\npublic', src, re.S)
    if not m:
        return ''
    return clean(re.sub(r'\s*///\s?', ' ', m.group(1)))


def w(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8-sig') as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    print(f'{name}: {len(rows)}')


# ---------------- cards ----------------
def cards():
    pools = pool_members('CardPools', 'Card')
    rows = []
    for cls, s in classes('Cards').items():
        m = re.search(r'base\(\s*(-?\d+),\s*CardType\.(\w+),\s*CardRarity\.(\w+),\s*TargetType\.(\w+)(?:,\s*(?:shouldShowInCardLibrary:\s*)?(\w+))?', s)
        if not m:
            continue
        mid = snake(cls)
        kw = re.search(r'CanonicalKeywords\s*=>(.*?);', s, re.S)
        kws = ','.join(re.findall(r'CardKeyword\.(\w+)', kw.group(1))) if kw else ''
        tags = re.search(r'CanonicalTags\s*=>(.*?);', s, re.S)
        star = re.search(r'CanonicalStarCost => (-?\d+)', s)
        mul = re.search(r'MaxUpgradeLevel => (\d+)', s)
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('cards', mid, 'title'), name_en=L('cards', mid, 'title', 'eng'),
            pool='|'.join(pools.get(cls, [])), cost=m.group(1), star_cost=star.group(1) if star else '',
            type=m.group(2), rarity=m.group(3), target=m.group(4),
            in_library='false' if m.group(5) == 'false' else 'true',
            keywords=kws, tags=','.join(re.findall(r'CardTag\.(\w+)', tags.group(1))) if tags else '',
            vars=vars_of(s), upgrade=upgrades_of(s), max_upgrade=mul.group(1) if mul else '1',
            desc_zh=clean(L('cards', mid, 'description')), desc_en=clean(L('cards', mid, 'description', 'eng')),
            dev_note=summary_doc(s)))
    w('cards.csv', rows, list(rows[0].keys()))
    return rows


# ---------------- relics ----------------
def relics():
    pools = pool_members('RelicPools', 'Relic')
    rows = []
    for cls, s in classes('Relics').items():
        mid = snake(cls)
        r = re.search(r'RelicRarity Rarity => RelicRarity\.(\w+)', s)
        cost = re.search(r'MerchantCost => ([^;]+);', s)
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('relics', mid, 'title'), name_en=L('relics', mid, 'title', 'eng'),
            rarity=r.group(1) if r else '', pool='|'.join(pools.get(cls, [])), vars=vars_of(s),
            merchant_cost=clean(cost.group(1)) if cost else '',
            pickup_effect='HasUponPickupEffect => true' in s, shop_allowed='IsAllowedInShops => false' not in s,
            desc_zh=clean(L('relics', mid, 'description')), desc_en=clean(L('relics', mid, 'description', 'eng')),
            flavor_zh=clean(L('relics', mid, 'flavor')), dev_note=summary_doc(s)))
    w('relics.csv', rows, list(rows[0].keys()))


# ---------------- potions ----------------
def potions():
    pools = pool_members('PotionPools', 'Potion')
    rows = []
    for cls, s in classes('Potions').items():
        mid = snake(cls)
        g = lambda rx: (re.search(rx, s).group(1) if re.search(rx, s) else '')
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('potions', mid, 'title'), name_en=L('potions', mid, 'title', 'eng'),
            rarity=g(r'PotionRarity Rarity => PotionRarity\.(\w+)'), usage=g(r'PotionUsage Usage => PotionUsage\.(\w+)'),
            target=g(r'TargetType TargetType => TargetType\.(\w+)'), pool='|'.join(pools.get(cls, [])), vars=vars_of(s),
            desc_zh=clean(L('potions', mid, 'description')), desc_en=clean(L('potions', mid, 'description', 'eng'))))
    w('potions.csv', rows, list(rows[0].keys()))


# ---------------- powers ----------------
def powers():
    rows = []
    for cls, s in classes('Powers').items():
        mid = snake(cls)
        g = lambda rx: (re.search(rx, s).group(1) if re.search(rx, s) else '')
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('powers', mid, 'title') or L('cards', mid[:-6], 'title'),
            name_en=L('powers', mid, 'title', 'eng') or L('cards', mid[:-6], 'title', 'eng'),
            type=g(r'PowerType Type => PowerType\.(\w+)'), stack=g(r'PowerStackType StackType => PowerStackType\.(\w+)'),
            desc_zh=clean(L('powers', mid, 'description')), desc_en=clean(L('powers', mid, 'description', 'eng'))))
    w('powers.csv', rows, list(rows[0].keys()))


# ---------------- monsters ----------------
ASC = r'AscensionHelper\.GetValueIfAscension\(AscensionLevel\.(\w+),\s*([-\d.]+)f?m?,\s*([-\d.]+)f?m?\)'


def prop_val(expr):
    m = re.search(ASC, expr)
    if m:
        return m.group(3), m.group(2), m.group(1)
    m = re.fullmatch(r'\s*(-?\d+)\s*', expr)
    if m:
        return m.group(1), m.group(1), ''
    return clean(expr)[:60], '', 'expr'


def monsters():
    rows, moves = [], []
    for cls, s in classes('Monsters').items():
        mid = snake(cls)
        props = {}
        for m in re.finditer(r'(?:private|public|protected)(?: override)? (?:int|decimal|float) (\w+) => ([^;]+);', s):
            props[m.group(1)] = prop_val(m.group(2))
        for k, v in list(props.items()):
            if v[2] == 'expr' and v[0] in props:
                props[k] = props[v[0]]
        hp = lambda k: props.get(k, ('', '', ''))
        mn, mx = hp('MinInitialHp'), hp('MaxInitialHp')
        nums = {k: v for k, v in props.items() if k not in ('MinInitialHp', 'MaxInitialHp')}
        mv = re.findall(r'new MoveState\("(\w+)",\s*(\w+),\s*((?:new \w+Intent\([^)]*\)(?:,\s*)?)+)', s)
        for name, method, intents in mv:
            moves.append(dict(monster=mid, move=name, method=method,
                              move_zh=L('monsters', mid, f'moves.{name.replace("_MOVE", "")}.title'),
                              intents='; '.join(re.findall(r'new (\w+Intent\([^)]*\))', intents))))
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('monsters', mid, 'name'), name_en=L('monsters', mid, 'name', 'eng'),
            hp_min=mn[0], hp_max=mx[0], hp_min_asc=mn[1], hp_max_asc=mx[1], hp_asc_level=mn[2],
            n_moves=len(mv), move_names=','.join(n for n, _, _ in mv),
            numbers='; '.join(f'{k}={v[0]}' + (f'/{v[1]}@{v[2]}' if v[2] and v[2] != 'expr' else '') for k, v in nums.items() if v[2] != 'expr'),
            file=f'MegaCrit.Sts2.Core.Models.Monsters/{cls}.cs'))
    w('monsters.csv', rows, list(rows[0].keys()))
    w('monster_moves.csv', moves, list(moves[0].keys()))


# ---------------- encounters / acts ----------------
def encounters_acts():
    acts = {}
    for cls, s in classes('Acts').items():
        idx = re.search(r'int Index => (\d+)', s)
        encs = re.findall(r'ModelDb\.Encounter<(\w+)>\(\)', re.search(r'GenerateAllEncounters\(\)(.*?)\n\t\}', s, re.S).group(1)) if 'GenerateAllEncounters' in s else []
        bosses = re.search(r'BossDiscoveryOrder =>(.*?);', s, re.S)
        evs = re.search(r'AllEvents =>(.*?)\}\);', s, re.S)
        anc = re.search(r'AllAncients =>(.*?);', s, re.S)
        g = lambda rx: (re.search(rx, s).group(1) if re.search(rx, s) else '')
        acts[cls] = dict(
            act=cls, name_zh=L('acts', snake(cls), 'title'), index=idx.group(1) if idx else '',
            rooms=g(r'BaseNumberOfRooms => (\d+)'), weak_encounters=g(r'NumberOfWeakEncounters => (\d+)'),
            rest_gauss=g(r'NextGaussianInt\(([^)]*)\)'), is_default=g(r'IsDefault => (\w+)'),
            bosses=','.join(re.findall(r'Encounter<(\w+)>', bosses.group(1))) if bosses else '',
            ancients=','.join(re.findall(r'AncientEvent<(\w+)>', anc.group(1))) if anc else '',
            events=','.join(re.findall(r'Event<(\w+)>', evs.group(1))) if evs else '',
            n_encounters=len(encs), encounters=','.join(encs))
    enc_act = collections.defaultdict(list)
    for a, d in acts.items():
        for e in d['encounters'].split(','):
            if e:
                enc_act[e].append(a)
    w('acts.csv', list(acts.values()), list(next(iter(acts.values())).keys()))
    rows = []
    for cls, s in classes('Encounters').items():
        mid = snake(cls)
        g = lambda rx: (re.search(rx, s).group(1) if re.search(rx, s) else '')
        poss = re.search(r'AllPossibleMonsters =>(.*?);\s*\n', s, re.S)
        rows.append(dict(
            id=mid, cls=cls, name_zh=L('encounters', mid, 'title'), room=g(r'RoomType RoomType => RoomType\.(\w+)'),
            act='|'.join(enc_act.get(cls, [])), weak=g(r'IsWeak => (\w+)') or 'false',
            tags=','.join(re.findall(r'EncounterTag\.(\w+)', g(r'Tags =>(.*?);'))),
            monsters=','.join(dict.fromkeys(re.findall(r'Monster<(\w+)>', poss.group(1) if poss else s))),
            gold=f"{g(r'MinGoldReward => (\\d+)')}-{g(r'MaxGoldReward => (\\d+)')}".strip('-'),
            bgm=g(r'CustomBgm => "([^"]+)"')))
    w('encounters.csv', rows, list(rows[0].keys()))


# ---------------- events ----------------
def events():
    rows = []
    for cls, s in classes('Events').items():
        mid = snake(cls)
        base = re.search(r'class \w+ : (\w+)', s)
        opts = sorted(set(re.findall(r'"' + mid + r'\.pages\.(\w+)\.options\.(\w+)', s)))
        titles = loc('zhs', 'events')
        pages = sorted({k.split('.')[2] for k in titles if k.startswith(mid + '.pages.')})
        rows.append(dict(
            id=mid, cls=cls, base=base.group(1) if base else '', name_zh=L('events', mid, 'title') or L('ancients', mid, 'title'),
            name_en=L('events', mid, 'title', 'eng') or L('ancients', mid, 'title', 'eng'),
            pages='|'.join(pages), vars=vars_of(s), lines=s.count('\n'),
            intro_zh=clean(L('events', mid, 'pages.INITIAL.description'))[:300]))
    w('events.csv', rows, list(rows[0].keys()))


def simple(folder, table, fname, extra=None):
    rows = []
    for cls, s in classes(folder).items():
        mid = snake(cls)
        d = dict(id=mid, cls=cls, name_zh=L(table, mid, 'title'), name_en=L(table, mid, 'title', 'eng'),
                 vars=vars_of(s), desc_zh=clean(L(table, mid, 'description')), dev_note=summary_doc(s))
        if extra:
            d.update(extra(s))
        rows.append(d)
    w(fname, rows, list(rows[0].keys()))


if __name__ == '__main__':
    cards(); relics(); potions(); powers(); monsters(); encounters_acts(); events()
    simple('Enchantments', 'enchantments', 'enchantments.csv')
    simple('Afflictions', 'afflictions', 'afflictions.csv')
    simple('Modifiers', 'modifiers', 'modifiers.csv')
    simple('Orbs', 'orbs', 'orbs.csv')
    simple('Characters', 'characters', 'characters.csv', lambda s: dict(
        hp=(re.search(r'StartingHp => (\d+)', s) or [None, ''])[1],
        gold=(re.search(r'StartingGold => (\d+)', s) or [None, ''])[1],
        energy=(re.search(r'MaxEnergy => (\d+)', s) or [None, '3'])[1],
        deck=','.join(re.findall(r'Card<(\w+)>', (re.search(r'StartingDeck =>(.*?);\s*\n', s, re.S) or [None, ''])[1] if re.search(r'StartingDeck =>(.*?);\s*\n', s, re.S) else '')),
        relics=','.join(re.findall(r'Relic<(\w+)>', (re.search(r'StartingRelics =>(.*?);\s*\n', s, re.S).group(1) if re.search(r'StartingRelics =>(.*?);\s*\n', s, re.S) else '')))))
