"""第 02 章：角色与卡池统计（直接读 ILSpy 反编译源码 + 简中本地化，不依赖 cards.csv 的正则结果）

python -I -X utf8 scripts/ch02_card_stats.py
(在 outputs/sts2_rea_Claude 目录下跑，或任意目录跑都行，路径按脚本位置推)

产出（data/csv/）：
  ch02_card_detail.csv          每张卡一行：池/稀有度/类型/费用/星耗/数值/命中次数/每能量效率/升级分类/机制标签
  ch02_card_stats_by_char.csv   长表：pool × 维度(rarity/type/cost/keyword/upgrade/...) × 取值 → 张数、占比
  ch02_cost_efficiency.csv      按 池 × 指标(伤害/格挡) × 费用 汇总每能量效率（全部 / 白板子集）
  ch02_character_mechanics.csv  每角色专属机制：产出端/消耗端/收益端各有多少张卡（按源码调用计数）+ 样例
  ch02_characters_profile.csv   5+3 个角色的 HP/金币/能量/球槽/起始牌组/起始遗物/解锁前置
"""
import csv, glob, json, os, re, statistics, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization', 'zhs')
OUT = os.path.join(ROOT, 'data', 'csv')

CHARS = ['Ironclad', 'Silent', 'Defect', 'Regent', 'Necrobinder']
CHAR_ZH = {'Ironclad': '铁甲战士', 'Silent': '静默猎手', 'Defect': '故障机器人', 'Regent': '储君', 'Necrobinder': '亡灵契约师'}
POOL_ORDER = CHARS + ['Colorless', 'Event', 'Token', 'Status', 'Curse', 'Quest', 'Deprecated']
RARITY_ORDER = ['Basic', 'Common', 'Uncommon', 'Rare', 'Ancient', 'Event', 'Token', 'Status', 'Curse', 'Quest']


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def snake(cls):
    return re.sub(r'(?<=[A-Za-z0-9])([A-Z])', r'_\1', cls).upper()


def ns(name):
    return os.path.join(SRC, 'MegaCrit.Sts2.Core.' + name)


CARD_LOC = json.load(open(os.path.join(LOC, 'cards.json'), encoding='utf-8'))
RELIC_LOC = json.load(open(os.path.join(LOC, 'relics.json'), encoding='utf-8'))


def zh(cls, table=CARD_LOC, field='title'):
    return table.get(f'{snake(cls)}.{field}', '')


# ---------------------------------------------------------------- pools & epochs
def pool_members():
    m = collections.defaultdict(list)
    for p in glob.glob(os.path.join(ns('Models.CardPools'), '*.cs')):
        pool = os.path.basename(p)[:-3].replace('CardPool', '')
        if pool == 'Mock':
            continue
        for c in re.findall(r'ModelDb\.Card<(\w+)>\(\)', read(p)):
            if pool not in m[c]:
                m[c].append(pool)
    return m


def epoch_locked():
    """卡池 FilterThroughEpochs 里引用的 XxxEpoch.Cards → 该纪元未揭示前不进池子"""
    locked = {}
    for p in glob.glob(os.path.join(ns('Timeline.Epochs'), '*.cs')):
        ep = os.path.basename(p)[:-3]
        s = read(p)
        if 'Cards' not in s:
            continue
        for c in re.findall(r'ModelDb\.Card<(\w+)>\(\)', s):
            locked[c] = ep
    # 只保留真的被某个池子的 FilterThroughEpochs 引用的纪元
    used = set()
    for p in glob.glob(os.path.join(ns('Models.CardPools'), '*.cs')):
        used |= set(re.findall(r'IsEpochRevealed<(\w+)>', read(p)))
    return {c: e for c, e in locked.items() if e in used}


# ---------------------------------------------------------------- card parsing
VAR_RE = re.compile(r'new (\w+?)Var(?:<(\w+)>)?\(([^()]*(?:\([^()]*\)[^()]*)*)\)')


def parse_vars(s):
    seg = re.search(r'CanonicalVars\s*=>(.*?)(?:\n\t(?:public|protected|private|internal)|\n\t\}\);)', s, re.S)
    out = {}
    if not seg:
        return out
    for m in VAR_RE.finditer(seg.group(1)):
        kind, gen, args = m.group(1), m.group(2), m.group(3)
        args = [a.strip() for a in re.split(r',(?![^()]*\))', args)] if args.strip() else []
        name = gen.replace('Power', '') if gen else kind
        if kind in ('Dynamic', 'Int', 'String', 'Bool') and args and args[0].startswith('"'):
            name, args = args[0].strip('"'), args[1:]
        elif args and args[0].startswith('"'):  # BlockVar("BlockNextTurn", 3m, ...)
            name, args = args[0].strip('"'), args[1:]
        val = None
        if args:
            mm = re.match(r'^(-?\d+(?:\.\d+)?)m?$', args[0])
            if mm:
                val = float(mm.group(1))
        if name not in out:
            out[name] = val
    return out


def parse_upgrade(s):
    m = re.search(r'void OnUpgrade\(\)\s*\{(.*?)\n\t\}', s, re.S)
    body = m.group(1) if m else ''
    ups = {}
    for mm in re.finditer(r'DynamicVars(?:\[\s*"(\w+)"\s*\]|\.(\w+))\.UpgradeValueBy\(([-\d.]+)m?\)', body):
        ups[(mm.group(1) or mm.group(2)).replace('Power', '')] = float(mm.group(3))
    cost = sum(int(x) for x in re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body))
    kw_add = re.findall(r'AddKeyword\(CardKeyword\.(\w+)\)', body)
    kw_rm = re.findall(r'RemoveKeyword\(CardKeyword\.(\w+)\)', body)
    rest = re.sub(r'(?:DynamicVars[^;]*UpgradeValueBy|EnergyCost\.UpgradeBy|AddKeyword|RemoveKeyword)[^;]*;', '', body)
    other = bool(rest.strip(' \t\n{}base.'))
    return ups, cost, kw_add, kw_rm, other, bool(m)


def hits_of(s, vars_):
    m = re.search(r'WithHitCount\(([^;]*?)\)\s*[\.\n]', s)
    if not m:
        return 1, ''
    arg = m.group(1)
    if re.fullmatch(r'\d+', arg.strip()):
        return int(arg), ''
    if 'Repeat' in arg and vars_.get('Repeat'):
        return int(vars_['Repeat']), ''
    if 'ResolveEnergyXValue' in arg or 'ResolveStarXValue' in arg:
        return 1, 'X'
    return 1, 'dynamic'


# 机制标签（正则命中源码即记 1）——只做“牌和机制有没有关系”的粗分，不判断强弱
MECH = {
    # 储君
    # 只认真正产星的调用（核查修正：原正则含 StarsVar，会把只读“本回合获得星数”的辐射 Radiate 算进来，又漏掉封印王座）
    'stars_gain': r'PlayerCmd\.GainStars|Apply<(?:StarNextTurn|Genesis|TheSealedThrone)Power>',
    'stars_spend': None,                      # 由 star_cost 字段判
    'forge': r'ForgeCmd\.Forge|ForgeVar',
    'sovereign_blade': r'SovereignBlade',
    'minion': r'Minion(?:Strike|DiveBomb|Sacrifice)|CardTag\.Minion',
    'colorless_gen': r'ColorlessCardPool|GetColorless|IsColorless',
    # 亡灵契约师
    'summon': r'OstyCmd\.Summon|SummonVar|SummonNextTurn',
    'osty_attack': r'CardTag\.OstyAttack|FromOsty\(|OstyDamageVar',
    'osty_any': r'\bOsty\b|IsOstyAlive|IsOstyMissing',
    'doom': r'DoomPower',
    'soul': r'Card<Soul>|\bSoul\b',
    'soul_gen': r'Soul\.Create|TransformTo<Soul>|Apply<SoulboundPower>',   # 真正生成灵魂（不含纠缠/吞噬生命/灵魂风暴等收益牌）
    'ethereal_syn': r'CardKeyword\.Ethereal',
    # 故障机器人
    'orb_channel': r'OrbCmd\.Channel|Channel<',
    'orb_evoke': r'OrbCmd\.Evoke|EvokeNext|EvokeLast',
    'orb_slot': r'OrbCmd\.(?:Add|Remove)Slots|OrbSlots',
    'focus': r'FocusPower',
    'status_gen': r'Card<(?:Dazed|Burn|Slimed|Void|Wound|Infection|Debris|Toxic)>|CardType\.Status',
    # 静默猎手
    'shiv': r'Card<Shiv>|\bShiv\b|CardTag\.Shiv',
    'shiv_gen': r'Shiv\.CreateInHand|CreateCard<Shiv>|Apply<InfiniteBladesPower>',  # 真正生成小刀（不含精准/幻影之刃/刀刃陷阱）
    'poison': r'PoisonPower',
    'discard': r'CardCmd\.Discard|DiscardAndDraw',
    'sly': r'CardKeyword\.Sly|ApplySingleTurnSly',
    # 铁甲战士
    'exhaust': r'CardKeyword\.Exhaust|CardCmd\.Exhaust|PileType\.Exhaust',
    'strength': r'StrengthPower',
    'self_hp_loss': r'HpLossVar|LoseHp\(|DamageCmd\.Self|Damage\(\s*choiceContext,\s*base\.Owner\.Creature',
    'vulnerable': r'VulnerablePower',
    # 通用
    'multiplayer_only': r'CardMultiplayerConstraint\.MultiplayerOnly',
    'generates_card': r'AddGeneratedCardToCombat|AddGeneratedCardsToCombat|CreateCard<|CreateInHand',
}


def parse_cards(pools, locked):
    rows = []
    for p in sorted(glob.glob(os.path.join(ns('Models.Cards'), '*.cs'))):
        cls = os.path.basename(p)[:-3]
        s = read(p)
        m = re.search(r'base\(\s*(-?\d+),\s*CardType\.(\w+),\s*CardRarity\.(\w+),\s*TargetType\.(\w+)', s)
        if not m:
            continue
        cost, ctype, rarity, target = int(m.group(1)), m.group(2), m.group(3), m.group(4)
        x_cost = 'HasEnergyCostX => true' in s
        star = re.search(r'CanonicalStarCost => (-?\d+)', s)
        star_cost = int(star.group(1)) if star else -1
        star_x = 'HasStarCostX => true' in s
        kw = re.search(r'CanonicalKeywords\s*=>(.*?);\s*\n', s, re.S)
        kws = re.findall(r'CardKeyword\.(\w+)', kw.group(1)) if kw else []
        tg = re.search(r'CanonicalTags\s*=>(.*?);\s*\n', s, re.S)
        tags = re.findall(r'CardTag\.(\w+)', tg.group(1)) if tg else []
        mu = re.search(r'MaxUpgradeLevel => (\d+)', s)
        max_up = int(mu.group(1)) if mu else 1
        vars_ = parse_vars(s)
        ups, ucost, kw_add, kw_rm, other, has_on_upgrade = parse_upgrade(s)
        is_upg_branch = 'IsUpgraded' in s
        hits, hit_flag = hits_of(s, vars_)
        aoe = target == 'AllEnemies' or 'TargetingAllOpponents' in s
        pool = '|'.join(pools.get(cls, [])) or 'None'

        dmg = vars_.get('Damage') if 'Damage' in vars_ else vars_.get('OstyDamage')
        if dmg is None and vars_.get('CalculationBase') is not None and 'CalculatedDamage' in vars_:
            dmg_kind = 'scaling'
            dmg = vars_.get('CalculationBase')
        elif 'OstyDamage' in vars_ and 'Damage' not in vars_:
            dmg_kind = 'osty'
        elif dmg is not None:
            dmg_kind = 'direct'
        else:
            dmg_kind = ''
        blk = vars_.get('Block')
        if blk is None and vars_.get('CalculationBase') is not None and 'CalculatedBlock' in vars_:
            blk = vars_.get('CalculationBase')
        # 升级增量
        dmg_up = ups.get('Damage', ups.get('OstyDamage', ups.get('CalculationBase') if dmg_kind == 'scaling' else None))
        blk_up = ups.get('Block')
        # 升级分类
        cats = []
        if ups:
            cats.append('数值')
        if ucost < 0:
            cats.append('降费')
        if ucost > 0:
            cats.append('加费')
        if kw_add:
            cats.append('加关键词:' + '/'.join(kw_add))
        if kw_rm:
            cats.append('去关键词:' + '/'.join(kw_rm))
        if other:
            cats.append('其他代码')
        if is_upg_branch:
            cats.append('行为分支(IsUpgraded)')
        if max_up == 0:
            cats = ['不可升级']
        if not cats:
            cats = ['未识别']
        if max_up == 0:
            up_main = '不可升级'
        elif ups and not (ucost or kw_add or kw_rm):
            up_main = '纯数值'
        elif ucost < 0 and not (ups or kw_add or kw_rm):
            up_main = '纯降费'
        elif (kw_add or kw_rm) and not (ups or ucost):
            up_main = '纯关键词'
        elif not has_on_upgrade and is_upg_branch:
            up_main = '行为改写'
        elif ups or ucost or kw_add or kw_rm:
            up_main = '混合'
        else:
            up_main = '未识别'
        # 核查修正：OnUpgrade 只加数值、但出牌逻辑里另有 IsUpgraded 分支（坚毅/特斯拉线圈/压缩/君权自授/剥夺/挽歌）
        # 不是“纯数值”，归入混合。只看去掉悬停提示行后的源码，避免 HoverTipFactory.FromCard<X>(IsUpgraded) 误判。
        real_upg_branch = 'IsUpgraded' in '\n'.join(l for l in s.split('\n') if 'HoverTip' not in l)
        if up_main == '纯数值' and real_upg_branch:
            up_main = '混合'

        mech ={k: (1 if (rx and re.search(rx, s)) else 0) for k, rx in MECH.items()}
        mech['stars_spend'] = 1 if (star_cost > 0 or star_x) else 0

        def per(v, c):
            if v is None or x_cost or c <= 0:
                return ''
            return round(v / c, 2)

        total = dmg * hits if dmg is not None else None
        total_up = (dmg + (dmg_up or 0)) * hits if dmg is not None else None
        eff_cost_up = cost + (ucost if ucost < 0 else 0)
        # “白板”判定：OnPlay 里除了出伤/加格挡本身，没有任何别的 Cmd 调用，也没有关键词、没有条件分支
        op = re.search(r'Task OnPlay\(.*?\)\s*\{(.*?)\n\t\}', s, re.S)
        op_body = op.group(1) if op else ''
        calls = [c for c in re.findall(r'\b(\w+Cmd\.\w+)', op_body)
                 if c not in ('CreatureCmd.TriggerAnim', 'DamageCmd.Attack', 'CreatureCmd.GainBlock', 'Cmd.Wait', 'SfxCmd.Play', 'VfxCmd.PlayOnCreatureCenter')
                 and not c.startswith('VfxCmd.') and not c.startswith('SfxCmd.')]
        # 除 OnPlay/OnUpgrade 外还重写了别的方法（抽到时减费、回合结束自动打出、条件命中等）→ 不算白板
        extra_methods = [mm for mm in re.findall(r'override (?:async )?[\w<>?\[\], ]+? (\w+)\(', s) if mm not in ('OnPlay', 'OnUpgrade')]
        plain = (not calls and not kws and not is_upg_branch and not extra_methods and not x_cost and not star_x
                 and hit_flag == '' and not re.search(r'\bif \(|\bforeach|\bfor \(|\?', op_body.replace('?.', '')))
        plain = plain and 'EnergyCost' not in op_body and 'IsPlayable =>' not in s
        vanilla_dmg = plain and dmg_kind == 'direct' and set(vars_) <= {'Damage', 'Repeat'} and ctype == 'Attack' and 'GainBlock' not in op_body
        vanilla_blk = plain and blk is not None and set(vars_) <= {'Block'} and ctype == 'Skill' and 'DamageCmd' not in op_body
        rows.append(dict(
            cls=cls, name_zh=zh(cls), pool=pool, rarity=rarity, type=ctype, target=target,
            cost=('X' if x_cost else cost), cost_num=cost, star_cost=('X' if star_x else (star_cost if star_cost >= 0 else '')),
            keywords=','.join(kws), tags=','.join(tags), max_upgrade=max_up,
            epoch_lock=locked.get(cls, ''),
            mp_only=mech['multiplayer_only'],
            dmg_kind=dmg_kind, damage=dmg if dmg is not None else '', hits=hits, hit_flag=hit_flag, aoe=int(aoe),
            total_damage=total if total is not None else '',
            dmg_per_energy=per(total, cost),
            dmg_up=dmg_up if dmg_up is not None else '',
            dmg_per_energy_up=per(total_up, eff_cost_up),
            block=blk if blk is not None else '', block_per_energy=per(blk, cost),
            block_up=blk_up if blk_up is not None else '',
            block_per_energy_up=per((blk or 0) + (blk_up or 0) if blk is not None else None, eff_cost_up),
            upgrade_main=up_main, upgrade_detail=';'.join(cats), upgrade_cost_delta=ucost,
            vanilla_attack=int(vanilla_dmg), vanilla_block=int(vanilla_blk),
            vars=';'.join(f'{k}={"" if v is None else (int(v) if v == int(v) else v)}' for k, v in vars_.items()),
            mech='|'.join(k for k, v in mech.items() if v),
        ))
    return rows


# ---------------------------------------------------------------- aggregations
def stats_by_char(cards):
    out = []

    def add(pool, dim, key, n, tot):
        out.append(dict(pool=pool, dimension=dim, key=key, count=n, share=round(n / tot, 3) if tot else ''))

    for pool in POOL_ORDER + ['ALL_CHAR']:
        sub = [c for c in cards if (c['pool'] in CHARS if pool == 'ALL_CHAR' else c['pool'] == pool)]
        if not sub:
            continue
        tot = len(sub)
        add(pool, 'total', 'cards', tot, tot)
        for dim, keyf in [
            ('rarity', lambda c: c['rarity']),
            ('type', lambda c: c['type']),
            ('rarity_type', lambda c: f"{c['rarity']}/{c['type']}"),
            ('cost', lambda c: 'unplayable(-1)' if c['cost'] == -1 else ('4+' if isinstance(c['cost'], int) and c['cost'] >= 4 else str(c['cost']))),
            ('star_cost', lambda c: 'none' if c['star_cost'] == '' else str(c['star_cost'])),
            ('upgrade_main', lambda c: c['upgrade_main']),
            ('mp_only', lambda c: 'MultiplayerOnly' if c['mp_only'] else 'any'),
            ('epoch_locked', lambda c: 'locked' if c['epoch_lock'] else 'base'),
        ]:
            cnt = collections.Counter(keyf(c) for c in sub)
            for k, v in sorted(cnt.items(), key=lambda kv: str(kv[0])):
                add(pool, dim, k, v, tot)
        kwc = collections.Counter(k for c in sub for k in c['keywords'].split(',') if k)
        for k, v in sorted(kwc.items()):
            add(pool, 'keyword', k, v, tot)
        tgc = collections.Counter(k for c in sub for k in c['tags'].split(',') if k)
        for k, v in sorted(tgc.items()):
            add(pool, 'tag', k, v, tot)
        # 费用均值（排除不可打出/X）
        cs = [c['cost'] for c in sub if isinstance(c['cost'], int) and c['cost'] >= 0]
        if cs:
            out.append(dict(pool=pool, dimension='cost_mean', key='playable_non_x', count=len(cs), share=round(statistics.mean(cs), 3)))
        for rar in ['Common', 'Uncommon', 'Rare']:
            cs = [c['cost'] for c in sub if c['rarity'] == rar and isinstance(c['cost'], int) and c['cost'] >= 0]
            if cs:
                out.append(dict(pool=pool, dimension='cost_mean_by_rarity', key=rar, count=len(cs), share=round(statistics.mean(cs), 3)))
    return out


def cost_efficiency(cards):
    out = []

    def summarize(pool, metric, cost_key, vals, vals_up, vanilla_vals):
        if not vals:
            return
        out.append(dict(pool=pool, metric=metric, cost=cost_key, n=len(vals),
                        mean=round(statistics.mean(vals), 2), median=round(statistics.median(vals), 2),
                        min=min(vals), max=max(vals),
                        mean_upgraded=round(statistics.mean(vals_up), 2) if vals_up else '',
                        upgrade_gain_pct=round((statistics.mean(vals_up) / statistics.mean(vals) - 1) * 100, 1) if vals_up else '',
                        vanilla_n=len(vanilla_vals),
                        vanilla_mean=round(statistics.mean(vanilla_vals), 2) if vanilla_vals else ''))

    groups = [(p, lambda c, p=p: c['pool'] == p) for p in CHARS + ['Colorless', 'Event']]
    groups.append(('ALL_CHAR', lambda c: c['pool'] in CHARS))
    for pool, flt in groups:
        sub = [c for c in cards if flt(c) and c['rarity'] in ('Basic', 'Common', 'Uncommon', 'Rare', 'Ancient', 'Event')]
        for metric, fld, fld_up, van in [('damage_per_energy', 'dmg_per_energy', 'dmg_per_energy_up', 'vanilla_attack'),
                                         ('block_per_energy', 'block_per_energy', 'block_per_energy_up', 'vanilla_block')]:
            # 伤害只看攻击牌的直接/奥斯提伤害；格挡只看技能/攻击牌上 >0 的格挡；能力牌（每次触发的数值）与星耗牌另算
            if metric == 'damage_per_energy':
                base = [c for c in sub if c[fld] != '' and c['star_cost'] == '' and c['type'] == 'Attack' and c['dmg_kind'] in ('direct', 'osty')]
            else:
                base = [c for c in sub if c[fld] != '' and c['star_cost'] == '' and c['type'] in ('Skill', 'Attack') and float(c['block'] or 0) > 0]
            for ck in ['1', '2', '3', '4+', 'ALL']:
                if ck == 'ALL':
                    g = base
                elif ck == '4+':
                    g = [c for c in base if c['cost_num'] >= 4]
                else:
                    g = [c for c in base if str(c['cost_num']) == ck]
                summarize(pool, metric, ck, [c[fld] for c in g], [c[fld_up] for c in g if c[fld_up] != ''],
                          [c[fld] for c in g if c[van]])
            # 按稀有度
            for rar in ['Basic', 'Common', 'Uncommon', 'Rare']:
                g = [c for c in base if c['rarity'] == rar]
                summarize(pool, metric, 'rarity:' + rar, [c[fld] for c in g], [c[fld_up] for c in g if c[fld_up] != ''],
                          [c[fld] for c in g if c[van]])
            # AOE 与单体分开（只对伤害）
            if metric == 'damage_per_energy':
                for aoe in (0, 1):
                    g = [c for c in base if c['aoe'] == aoe]
                    summarize(pool, metric, 'aoe' if aoe else 'single', [c[fld] for c in g],
                              [c[fld_up] for c in g if c[fld_up] != ''], [c[fld] for c in g if c[van]])
        # 0 费伤害牌：给出绝对伤害
        z = [c for c in sub if c['cost'] == 0 and c['type'] == 'Attack' and c['dmg_kind'] in ('direct', 'osty') and c['star_cost'] == '']
        if z:
            vals = [c['total_damage'] for c in z]
            out.append(dict(pool=pool, metric='zero_cost_total_damage', cost='0', n=len(vals), mean=round(statistics.mean(vals), 2),
                            median=statistics.median(vals), min=min(vals), max=max(vals), mean_upgraded='', upgrade_gain_pct='',
                            vanilla_n='', vanilla_mean=''))
    # 储君：星耗牌单列（伤害 / 每“能量+星”）
    st = [c for c in cards if c['pool'] == 'Regent' and c['star_cost'] not in ('', 'X') and c['dmg_kind'] == 'direct']
    for c in st:
        out.append(dict(pool='Regent', metric='star_card_damage:' + c['cls'], cost=f"{c['cost']}E+{c['star_cost']}S", n=1,
                        mean=c['total_damage'], median='', min='', max='', mean_upgraded='', upgrade_gain_pct='', vanilla_n='', vanilla_mean=''))
    return out


MECH_ROLES = {
    'Ironclad': [('exhaust', '消耗(产出/收益)'), ('strength', '力量'), ('self_hp_loss', '自损生命'), ('vulnerable', '易伤')],
    'Silent': [('shiv', '小刀'), ('shiv_gen', '小刀-生成'), ('poison', '中毒'), ('discard', '弃牌'), ('sly', '奇巧 Sly')],
    'Defect': [('orb_channel', '生成充能球'), ('orb_evoke', '激发'), ('focus', '集中'), ('orb_slot', '球槽增减'), ('status_gen', '状态牌')],
    'Regent': [('stars_gain', '辉星-产出'), ('stars_spend', '辉星-消耗(星耗牌)'), ('forge', '铸造'), ('sovereign_blade', '君王之剑相关'),
               ('minion', '仆从'), ('colorless_gen', '无色牌生成/联动')],
    'Necrobinder': [('summon', '召唤(奥斯提HP产出)'), ('osty_attack', '奥斯提攻击'), ('osty_any', '引用奥斯提(含上两项)'), ('doom', '灾厄'),
                    ('soul', '灵魂'), ('soul_gen', '灵魂-生成'), ('ethereal_syn', '虚无联动(自带或检查)')],
}


def character_mechanics(cards):
    out = []
    for ch in CHARS:
        sub = [c for c in cards if c['pool'] == ch]
        for key, label in MECH_ROLES[ch] + [('generates_card', '生成卡牌'), ('multiplayer_only', '仅多人')]:
            hit = [c for c in sub if key in c['mech'].split('|')]
            by_r = collections.Counter(c['rarity'] for c in hit)
            out.append(dict(character=ch, character_zh=CHAR_ZH[ch], mechanic=key, label=label, n_cards=len(hit),
                            share_of_pool=round(len(hit) / len(sub), 3),
                            by_rarity=' '.join(f'{r}:{by_r[r]}' for r in RARITY_ORDER if by_r[r]),
                            examples='、'.join(c['name_zh'] for c in hit[:12])))
        # 交叉：其它角色池里出现本角色机制的情况（检查机制是否“专属”）
    for key in ['stars_gain', 'forge', 'summon', 'doom', 'orb_channel', 'shiv', 'poison', 'focus']:
        hit = [c for c in cards if key in c['mech'].split('|')]
        by_p = collections.Counter(c['pool'] for c in hit)
        out.append(dict(character='CROSS', character_zh='跨池分布', mechanic=key, label='该机制在各池的分布', n_cards=len(hit),
                        share_of_pool='', by_rarity=' '.join(f'{p}:{n}' for p, n in by_p.most_common()), examples=''))
    return out


def characters_profile():
    out = []
    unlock = {}
    for p in glob.glob(os.path.join(ns('Models.Characters'), '*.cs')):
        cls = os.path.basename(p)[:-3]
        s = read(p)
        g = lambda rx, d='': (re.search(rx, s, re.S).group(1) if re.search(rx, s, re.S) else d)
        deck = re.findall(r'Card<(\w+)>', g(r'StartingDeck =>(.*?);\s*\n', ''))
        relics = re.findall(r'Relic<(\w+)>', g(r'StartingRelics =>(.*?);\s*\n', ''))
        cnt = collections.Counter(deck)
        out.append(dict(
            character=cls, name_zh=json.load(open(os.path.join(LOC, 'characters.json'), encoding='utf-8')).get(snake(cls) + '.title', ''),
            playable=('false' if 'IsPlayable => false' in s else 'true'),
            hp=g(r'StartingHp => (\d+)'), gold=g(r'StartingGold => (\d+)'), max_energy=g(r'MaxEnergy => (\d+)', '3'),
            orb_slots=g(r'BaseOrbSlotCount => (\d+)', '0'),
            unlocks_after_run_as=g(r'UnlocksAfterRunAs => ModelDb\.Character<(\w+)>', ''),
            deck_size=len(deck), deck=' '.join(f'{k}x{v}' for k, v in cnt.items()),
            deck_zh=' '.join(f'{zh(k)}x{v}' for k, v in cnt.items()),
            starter_relic=','.join(relics), starter_relic_zh=','.join(RELIC_LOC.get(snake(r) + '.title', '') for r in relics),
            starter_relic_desc=','.join(re.sub(r'\s+', ' ', RELIC_LOC.get(snake(r) + '.description', '')) for r in relics),
            card_pool=g(r'CardPool => ModelDb\.CardPool<(\w+)>', ''),
        ))
    order = {c: i for i, c in enumerate(CHARS + ['Deprived', 'RandomCharacter', 'DeprecatedCharacter'])}
    return sorted(out, key=lambda r: order.get(r['character'], 99))


def w(name, rows):
    p = os.path.join(OUT, name)
    with open(p, 'w', newline='', encoding='utf-8-sig') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f'{name}: {len(rows)} rows')


def main():
    pools = pool_members()
    locked = epoch_locked()
    cards = parse_cards(pools, locked)
    order = {p: i for i, p in enumerate(POOL_ORDER)}
    rorder = {r: i for i, r in enumerate(RARITY_ORDER)}
    cards.sort(key=lambda c: (order.get(c['pool'], 99), rorder.get(c['rarity'], 99), c['type'], str(c['cost']), c['cls']))
    w('ch02_card_detail.csv', cards)
    w('ch02_card_stats_by_char.csv', stats_by_char(cards))
    w('ch02_cost_efficiency.csv', cost_efficiency(cards))
    w('ch02_character_mechanics.csv', character_mechanics(cards))
    w('ch02_characters_profile.csv', characters_profile())
    print('cards parsed:', len(cards), collections.Counter(c['pool'] for c in cards))


if __name__ == '__main__':
    main()
