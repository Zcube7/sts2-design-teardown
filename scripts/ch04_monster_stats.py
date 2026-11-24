"""第 04 章：怪物 / 遭遇 / 幕 数值表

python -I -X utf8 scripts/ch04_monster_stats.py
(在 outputs/sts2_rea_Claude 目录下跑，或任意目录，路径按脚本位置推)

产出 data/csv/:
  ch04_monster_stats.csv     每怪一行：幕、房间类型、HP 普通/A10、开局能力、招式循环、单招最大伤害、模拟期望伤害
  ch04_monster_moves.csv     每招一行：意图、单段伤害 x 段数（普通/A10）、自身加力量、后继
  ch04_encounter_pools.csv   每个幕内遭遇：池子(弱/普通/精英/Boss)、标签、组成、HP 区间与期望、期望每回合伤害
  ch04_hp_budget_by_act.csv  按 幕 x 池子 汇总 HP 预算与期望伤害

方法说明
- 数值来自 MonsterModel 子类里的 `X => AscensionHelper.GetValueIfAscension(Level, 进阶值, 普通值)`；
  A0 = 全部进阶关；A10 = 全部进阶开（ToughEnemies 管 HP/格挡，DeadlyEnemies 管伤害/力量）。
- 招式状态机按 GenerateMoveStateMachine() 里的 MoveState / RandomBranchState / ConditionalBranchState
  静态重建，然后蒙特卡洛跑前 6 回合（RandomBranch 的 CannotRepeat / CanRepeatXTimes / UseOnlyOnce / cooldown
  规则按 RandomBranchState.GetStateWeight 复刻）。
- 近似：ConditionalBranch 的条件无法静态求值，模拟时在各分支间均匀随机（标 cond）；权重是方法调用的 lambda
  也按 1 处理（标 wlambda）；只计自身 StrengthPower / RitualPower 带来的力量增长，不计玩家减益/格挡/易伤。
- 遭遇组成是对照 Encounters/*.cs 的 GenerateMonsters() 手工录入（下方 COMPOSITION），召唤物不进开局 HP。
"""
import csv, json, os, re, glob, random, collections, statistics, itertools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
MON = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Monsters')
ACTS = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Acts')
ENC = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Encounters')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization')
OUT = os.path.join(ROOT, 'data', 'csv')
TURNS = 6
RUNS = 600
random.seed(20261123)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def snake(cls):
    return re.sub(r'(?<=[A-Za-z0-9])([A-Z])', r'_\1', cls).upper()


_loc = {}


def L(table, key, lang='zhs'):
    k = (lang, table)
    if k not in _loc:
        p = os.path.join(LOC, lang, table + '.json')
        _loc[k] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    return _loc[k].get(key, '')


def match_paren(s, i):
    """s[i] == '(' -> index of matching ')'"""
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return j
    return -1


def split_args(s):
    out, depth, cur = [], 0, ''
    for c in s:
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        if c == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += c
    if cur.strip():
        out.append(cur.strip())
    return out


def method_body(src, header_regex):
    m = re.search(header_regex, src)
    if not m:
        return ''
    i = src.find('{', m.end() - 1)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


# ---------------------------------------------------------------- 数值属性
class Props:
    def __init__(self, src, parent=None):
        self.expr = dict(parent.expr) if parent else {}
        self.const = dict(parent.const) if parent else {}
        for m in re.finditer(r'const (?:int|decimal|float|double) (\w+) = (-?[\d.]+)[mfd]?;', src):
            self.const[m.group(1)] = float(m.group(2))
        for m in re.finditer(r'(?:public|private|protected|internal)(?: static)?(?: override| virtual)* (?:int|decimal|float|double) (\w+) => ([^;]+);', src):
            self.expr[m.group(1)] = m.group(2).strip()

    def ev(self, e, mode, depth=0):
        """mode: 'a0' 全关 / 'a10' 全开; 返回 float 或 None"""
        if e is None or depth > 12:
            return None
        e = e.strip()
        e = re.sub(r'^\(\)\s*=>\s*', '', e)
        e = e.replace('base.', '')
        m = re.fullmatch(r'AscensionHelper\.GetValueIfAscension\(AscensionLevel\.(\w+),\s*(.+)\)', e)
        if m:
            args = split_args(m.group(2))
            if len(args) == 2:
                return self.ev(args[0] if mode == 'a10' else args[1], mode, depth + 1)
        if re.fullmatch(r'-?[\d.]+[mfd]?', e):
            return float(e.rstrip('mfd'))
        if re.fullmatch(r'\w+', e):
            if e in self.const:
                return self.const[e]
            if e in self.expr:
                return self.ev(self.expr[e], mode, depth + 1)
            return 0.0 if getattr(self, 'zero_unknown', False) else None
        # 简单算术：把 AscensionHelper 调用和标识符替换成数值
        def rep_asc(mm):
            v = self.ev(mm.group(0), mode, depth + 1)
            return 'None' if v is None else repr(v)
        e2 = re.sub(r'AscensionHelper\.GetValueIfAscension\([^()]*\)', rep_asc, e)
        def rep_id(mm):
            name = mm.group(0)
            v = self.ev(name, mode, depth + 1)
            return 'None' if v is None else repr(v)
        e2 = re.sub(r'(?<![\d.])[A-Za-z_]\w*', rep_id, e2)
        e2 = re.sub(r'(\d)[mfd]\b', r'\1', e2)
        if 'None' in e2 or not re.fullmatch(r'[\d.\s+\-*/()]+', e2):
            return None
        try:
            return float(eval(e2, {'__builtins__': {}}))
        except Exception:
            return None


# ---------------------------------------------------------------- 状态机
class State:
    def __init__(self, kind, sid):
        self.kind, self.id = kind, sid
        self.method, self.intents, self.follow = None, [], None
        self.branches = []      # random: (var, cooldown, repeat, maxtimes, weight_expr)
        self.conds = []         # cond: (var, cond_expr)
        self.must_once = False


INTENT_RE = re.compile(r'new (\w+Intent)\(')


def parse_intents(argstr):
    out = []
    for a in split_args(argstr):
        m = re.match(r'new (\w+Intent)\((.*)\)$', a, re.S)
        if m:
            out.append((m.group(1), split_args(m.group(2))))
    return out


def parse_state_machine(src):
    body = method_body(src, r'MonsterMoveStateMachine GenerateMoveStateMachine\(\)')
    states, flags = {}, set()
    if not body:
        return None, states, {'no_sm'}
    # 按语句切分（ILSpy 输出一句一行；对象初始化器 { MustPerform... } 会跨行，单独处理）
    stmts = [x.strip() for x in re.split(r';\s*\n', body)]
    follows = []
    anon = 0
    for stmt in stmts:
        mnew = re.search(r'new (MoveState|RandomBranchState|ConditionalBranchState)\(', stmt)
        target = None
        if mnew:
            kind = mnew.group(1)
            p0 = mnew.end() - 1
            p1 = match_paren(stmt, p0)
            args = split_args(stmt[p0 + 1:p1])
            sid = args[0].strip('"') if args else ''
            md = re.match(r'(?:(?:MoveState|RandomBranchState|ConditionalBranchState|MonsterState)\s+)?(\w+)\s*=', stmt)
            if md and not stmt.startswith(md.group(1) + '.') and '.FollowUpState' not in md.group(0):
                var = md.group(1)
            else:
                anon += 1
                var = f'#{sid or anon}'
            st = State({'MoveState': 'move', 'RandomBranchState': 'rand', 'ConditionalBranchState': 'cond'}[kind], sid)
            if kind == 'MoveState':
                st.method = args[1] if len(args) > 1 else None
                st.intents = parse_intents(','.join(args[2:])) if len(args) > 2 else []
                if re.search(r'MustPerformOnceBeforeTransitioning = true', stmt[p1:]):
                    st.must_once = True
            states[var] = st
            target = var
        elif '.FollowUpState' in stmt:
            mt = re.search(r'=\s*\(*\s*(\w+)\s*\)*\s*$', stmt)
            target = mt.group(1) if mt else None
        if target:
            for prev in re.findall(r'(\w+)\.FollowUpState\s*=', stmt):
                follows.append((prev, target))
    for prev, nxt in follows:
        if prev in states and nxt in states:
            states[prev].follow = nxt
    for m in re.finditer(r'(\w+)\.AddBranch\(', body):
        var = m.group(1)
        if var not in states:
            continue
        p0 = m.end() - 1
        args = split_args(body[p0 + 1:match_paren(body, p0)])
        tgt, rest = args[0], args[1:]
        cooldown, repeat, maxt, w = 0, 'CanRepeatForever', 0, '1'
        ints = []
        for a in rest:
            if a.startswith('MoveRepeatType.'):
                repeat = a.split('.')[1]
            elif re.fullmatch(r'\d+', a):
                ints.append(int(a))
            else:
                w = a
        # 重载：(S, maxRepeats[, w]) / (S, cooldown, RepeatType[, w]) / (S, cooldown, maxRepeats, w)
        if repeat == 'CanRepeatForever' and not any(a.startswith('MoveRepeatType.') for a in rest):
            if len(ints) == 1:
                repeat, maxt = 'CanRepeatXTimes', ints[0]
            elif len(ints) == 2:
                cooldown, repeat, maxt = ints[0], 'CanRepeatXTimes', ints[1]
        else:
            if ints:
                cooldown = ints[0]
        states[var].branches.append((tgt, cooldown, repeat, maxt, w))
    for m in re.finditer(r'(\w+)\.AddState\(', body):
        var = m.group(1)
        if var not in states:
            continue
        p0 = m.end() - 1
        args = split_args(body[p0 + 1:match_paren(body, p0)])
        states[var].conds.append((args[0], args[1] if len(args) > 1 else ''))
    # 初始态：可能是变量、三元/switch 表达式、或先赋给 initialState 再传入；多个 return 取最后一个
    inits = []
    mis = list(re.finditer(r'new MonsterMoveStateMachine\(', body))
    if len(mis) > 1:
        flags.add('multi_init')
    for mi in mis:  # switch 里每个分支各 return 一个状态机（ScrollOfBiting）-> 取并集
        p0 = mi.end() - 1
        args = split_args(body[p0 + 1:match_paren(body, p0)])
        ie = args[-1] if args else ''
        if ie in states:
            inits.append(ie)
        else:
            ma = re.search(r'\b' + re.escape(ie) + r'\s*=\s*([^;]+);', body) if re.fullmatch(r'\w+', ie) else None
            expr = ma.group(1) if ma else ie
            inits += [n for n in re.findall(r'\w+', expr) if n in states]
    inits = list(dict.fromkeys(inits))
    if len(inits) > 1:
        flags.add('init_random')
    return inits, states, flags


# ---------------------------------------------------------------- 招式效果
def move_effects(src, method, props, mode):
    """返回 (自身力量增量, 自身仪式增量)"""
    if not method:
        return 0.0, 0.0
    body = method_body(src, r'(?:private|public|protected)[^\n]*\bTask ' + re.escape(method) + r'\(')
    s, r = 0.0, 0.0
    for m in re.finditer(r'PowerCmd\.Apply<(StrengthPower|RitualPower)>\(', body):
        p0 = m.end() - 1
        args = split_args(body[p0 + 1:match_paren(body, p0)])
        if len(args) >= 3 and args[1].strip() == 'base.Creature':
            v = props.ev(args[2], mode)
            if v is None:  # 含运行时计数器（如 Aeonglass.AdditionalStrength 初值 0）-> 未知标识符按 0
                props.zero_unknown = True
                v = props.ev(args[2], mode) or 0.0
                props.zero_unknown = False
            if m.group(1) == 'StrengthPower':
                s += v
            else:
                r += v
    return s, r


def start_powers(src, props, mode):
    body = method_body(src, r'override async Task AfterAddedToRoom\(\)')
    out = []
    for m in re.finditer(r'PowerCmd\.Apply<(\w+)Power>\(', body):
        p0 = m.end() - 1
        args = split_args(body[p0 + 1:match_paren(body, p0)])
        if len(args) >= 3 and args[1].strip() == 'base.Creature':
            v = props.ev(args[2], mode)
            out.append((m.group(1), v))
    return out


def intent_damage(intents, props, mode):
    """-> (单段伤害, 段数, 总伤害, 是否可解析)"""
    dmg_total, ok, per, hits = 0.0, True, None, 0
    for name, args in intents:
        if name in ('SingleAttackIntent', 'DeathBlowIntent'):
            d = props.ev(args[0], mode) if args else None
            if d is None:
                ok = False
                continue
            per, hits = d, hits + 1
            dmg_total += d
        elif name == 'MultiAttackIntent':
            d = props.ev(args[0], mode) if args else None
            h = props.ev(args[1], mode) if len(args) > 1 else None
            if d is None or h is None:
                ok = False
                continue
            per, hits = d, hits + h
            dmg_total += d * h
    return per, hits, dmg_total, ok


def weight_of(expr, props):
    v = props.ev(expr, 'a0')
    if v is None:
        return 1.0, True
    return v, False


def simulate(inits, states, info, mode, flags):
    """info[var] = dict(dmg, hits, str, rit, is_attack)；返回 (每回合期望伤害列表, 招式出现频率)"""
    if not inits:
        return None, collections.Counter()
    per_turn = [0.0] * TURNS
    freq = collections.Counter()
    for _ in range(RUNS):
        log = []
        cur = init = random.choice(inits)
        if states[cur].kind == 'move':
            log.append(cur)
        performed_first = False
        strength = 0.0
        ritual = 0.0
        for sp in info.get('__start__', []):
            if sp[0] == 'Strength' and sp[1]:
                strength += sp[1]
            if sp[0] == 'Ritual' and sp[1]:
                ritual += sp[1]
        # 开局自带、每个己方回合末 +力量 的能力：领地意识 Territorial / 高电压 HighVoltage
        per_turn_str = sum((sp[1] or 0) for sp in info.get('__start__', []) if sp[0] in ('Territorial', 'HighVoltage'))
        for t in range(TURNS):
            if performed_first or states[cur].kind != 'move':
                first = None
                guard = 0
                while True:
                    guard += 1
                    if guard > 50:
                        flags.add('loop')
                        return None, collections.Counter()
                    st = states[cur]
                    if st.kind == 'move':
                        nxt = st.follow
                        if nxt is None:
                            flags.add('no_followup')
                            nxt = cur   # 真实游戏里由 SetMoveImmediate/外部逻辑接管，这里按重复自身处理
                    elif st.kind == 'rand':
                        ws = []
                        for (tgt, cd, rep, mx, wexpr) in st.branches:
                            w, unk = weight_of(wexpr, PROPS_CTX[0])
                            if unk:
                                flags.add('wlambda')
                            # RandomBranchState.GetStateWeight
                            num = 1.0
                            if rep == 'UseOnlyOnce':
                                if tgt in log:
                                    num = 0.0
                            elif rep != 'CanRepeatForever':
                                n2 = 1 if rep == 'CannotRepeat' else mx
                                num = 1.0 if len(log) < n2 else 0.0
                                k = 0
                                while len(log) >= n2 and k < n2 and len(log) - k > 0:
                                    if log[len(log) - 1 - k] != tgt:
                                        num = 1.0
                                        break
                                    k += 1
                            if cd > 0:
                                recent = [x for x in reversed(log) if states[x].kind == 'move'][:cd]
                                if tgt in recent:
                                    num = 0.0
                            ws.append(num * w)
                        tot = sum(ws)
                        if tot <= 0:
                            flags.add('zero_weight')
                            nxt = st.branches[0][0]
                        else:
                            r = random.random() * tot
                            nxt = st.branches[-1][0]
                            for (b, wv) in zip(st.branches, ws):
                                r -= wv
                                if r <= 0:
                                    nxt = b[0]
                                    break
                    else:  # cond
                        flags.add('cond')
                        cands = [c[0] for c in st.conds if c[0] in states]
                        nxt = random.choice(cands) if cands else init
                    if nxt not in states:
                        flags.add('missing_state')
                        return None, collections.Counter()
                    cur = nxt
                    if first is None and states[cur].kind == 'move':
                        first = cur
                    if states[cur].kind == 'move':
                        break
                if first:
                    log.append(first)
            mi = info.get(cur, {})
            if mi.get('is_attack'):
                per_turn[t] += mi['dmg'] + strength * mi['hits']
            strength += mi.get('str', 0.0) + per_turn_str
            # RitualPower.AfterSideTurnEnd：刚被施加的那个回合跳过，之后每个己方回合末 +Amount 力量
            if mi.get('rit', 0.0):
                ritual += mi['rit']
            else:
                strength += ritual
            freq[cur] += 1
            performed_first = True
    return [x / RUNS for x in per_turn], freq


PROPS_CTX = [None]

# 静态解析不了的属性（带 get 块 / 运行时字段）按开局默认值补
PROP_OVERRIDES = {
    'Axebot': {'StockAmount': 2},          # Axebot.cs: _stockOverrideAmount.GetValueOrDefault(2)
    'WaterfallGiant': {'CurrentPressureGunDamage': 'BasePressureGunDamage'},  # 首发 20/23，每用一次 +5（PressureGunIncrease）
    'TestSubject': {'MultiClawTotalCount': 'BaseMultiClawCount'},             # 首发 3 段，每用一次 +1 段
}
# 初始态由运行时字段决定、静态取并集会错的：按开局那只的值
INIT_OVERRIDE = {
    'Axebot': ['moveState3'],              # 首只无 _stockOverrideAmount -> HAMMER_UPPERCUT；复活的才从 BOOT_UP 起
}


# ---------------------------------------------------------------- 幕 / 遭遇
def act_info():
    acts = {}
    for p in glob.glob(os.path.join(ACTS, '*.cs')):
        cls = os.path.splitext(os.path.basename(p))[0]
        s = read(p)
        m = re.search(r'GenerateAllEncounters\(\)(.*?)\n\t\}', s, re.S)
        if not m:
            continue
        acts[cls] = dict(index=int(re.search(r'int Index => (-?\d+)', s).group(1)),
                         encs=re.findall(r'ModelDb\.Encounter<(\w+)>\(\)', m.group(1)),
                         weak=int(re.search(r'NumberOfWeakEncounters => (\d+)', s).group(1)) if 'NumberOfWeakEncounters' in s else 3,
                         rooms=int(re.search(r'BaseNumberOfRooms => (\d+)', s).group(1)))
    return acts


def enc_info():
    out = {}
    for p in glob.glob(os.path.join(ENC, '*.cs')):
        cls = os.path.splitext(os.path.basename(p))[0]
        s = read(p)
        room = re.search(r'RoomType RoomType => RoomType\.(\w+)', s)
        tags = re.search(r'Tags =>(.*?);', s, re.S)
        out[cls] = dict(room=room.group(1) if room else '',
                        weak='IsWeak => true' in s,
                        tags=re.findall(r'EncounterTag\.(\w+)', tags.group(1)) if tags else [])
    return out


# 遭遇组成：('fix', 怪, 数量) / ('pick', k, [候选], distinct) / ('alt', [(概率, [组...])])
F = lambda m, n=1: ('fix', m, n)
COMPOSITION = {
    'AeonglassBoss': [F('Aeonglass')],
    'AxebotsNormal': [F('Axebot')],
    'BowlbugsNormal': [F('BowlbugRock'), ('pick', 2, ['BowlbugEgg', 'BowlbugSilk', 'BowlbugNectar'], True)],
    'BowlbugsWeak': [F('BowlbugRock'), ('pick', 1, ['BowlbugEgg', 'BowlbugNectar'], False)],
    'BygoneEffigyElite': [F('BygoneEffigy')],
    'ByrdonisElite': [F('Byrdonis')],
    'CeremonialBeastBoss': [F('CeremonialBeast')],
    'ChompersNormal': [F('Chomper', 2)],
    'ConstructMenagerieNormal': [F('PunchConstruct'), F('CubexConstruct', 2)],
    'CorpseSlugsNormal': [F('CorpseSlug', 3)],
    'CorpseSlugsWeak': [F('CorpseSlug', 2)],
    'CubexConstructNormal': [F('CubexConstruct')],
    'CultistsNormal': [F('CalcifiedCultist'), F('DampCultist')],
    'DecimillipedeElite': [F('DecimillipedeSegmentFront'), F('DecimillipedeSegmentMiddle'), F('DecimillipedeSegmentBack')],
    'DevotedSculptorWeak': [F('DevotedSculptor')],
    'EntomancerElite': [F('Entomancer')],
    'ExoskeletonsNormal': [F('Exoskeleton', 4)],
    'ExoskeletonsWeak': [F('Exoskeleton', 3)],
    'FabricatorNormal': [F('Fabricator')],
    'FlyconidNormal': [('pick', 1, ['LeafSlimeM', 'TwigSlimeM'], False), F('Flyconid')],
    'FogmogNormal': [F('Fogmog')],
    'FossilStalkerNormal': [F('FossilStalker')],
    'FrogKnightNormal': [F('FrogKnight')],
    'FuzzyWurmCrawlerWeak': [F('FuzzyWurmCrawler')],
    'GlobeHeadNormal': [F('GlobeHead')],
    'GremlinMercNormal': [F('GremlinMerc')],
    'HauntedShipNormal': [F('HauntedShip')],
    'HunterKillerNormal': [F('HunterKiller')],
    'InfestedPrismsElite': [F('InfestedPrism')],
    'InkletsNormal': [F('Inklet', 3)],
    'KaiserCrabBoss': [F('Crusher'), F('Rocket')],
    'KnightsElite': [F('FlailKnight'), F('SpectralKnight'), F('MagiKnight')],
    'KnowledgeDemonBoss': [F('KnowledgeDemon')],
    'LagavulinMatriarchBoss': [F('LagavulinMatriarch')],
    'LivingFogNormal': [F('LivingFog')],
    'LouseProgenitorNormal': [F('LouseProgenitor')],
    'MawlerNormal': [F('Mawler')],
    'MechaKnightElite': [F('MechaKnight')],
    'MytesNormal': [F('Myte', 2)],
    'NibbitsNormal': [F('Nibbit', 2)],
    'NibbitsWeak': [F('Nibbit')],
    'OvergrowthCrawlers': [F('ShrinkerBeetle'), F('FuzzyWurmCrawler')],
    'OvicopterNormal': [F('Ovicopter')],
    'OwlMagistrateNormal': [F('OwlMagistrate')],
    'PhantasmalGardenersElite': [F('PhantasmalGardener', 4)],
    'PhrogParasiteElite': [F('PhrogParasite')],
    'PunchConstructNormal': [F('PunchConstruct')],
    'QueenBoss': [F('TorchHeadAmalgam'), F('Queen')],
    'RubyRaidersNormal': [('pick', 3, ['AxeRubyRaider', 'AssassinRubyRaider', 'BruteRubyRaider', 'CrossbowRubyRaider', 'TrackerRubyRaider'], True)],
    'ScrollsOfBitingNormal': [F('ScrollOfBiting', 4)],
    'ScrollsOfBitingWeak': [F('ScrollOfBiting', 3)],
    'SeapunkNormal': [F('CalcifiedCultist'), F('Seapunk')],
    'SeapunkWeak': [F('Seapunk')],
    'SewerClamNormal': [F('SewerClam')],
    'ShrinkerBeetleWeak': [F('ShrinkerBeetle')],
    'SkulkingColonyElite': [F('SkulkingColony')],
    'SlimedBerserkerNormal': [F('SlimedBerserker')],
    'SlimesNormal': [F('TwigSlimeM'), F('LeafSlimeM'), F('LeafSlimeS'), F('TwigSlimeS')],
    'SlimesWeak': [F('LeafSlimeS'), F('TwigSlimeS'), ('pick', 1, ['LeafSlimeM', 'TwigSlimeM'], False)],
    'SlitheringStranglerNormal': [F('SlitheringStrangler'), ('alt', [
        (1 / 3, [F('SnappingJaxfruit')]),
        (1 / 3, [('pick', 1, ['LeafSlimeM', 'TwigSlimeM'], False)]),
        (1 / 3, [('pick', 2, ['LeafSlimeS', 'TwigSlimeS'], False)])])],
    'SludgeSpinnerWeak': [F('SludgeSpinner')],
    'SlumberingBeetleNormal': [F('BowlbugRock'), F('BowlbugSilk'), F('SlumberingBeetle')],
    'SnappingJaxfruitNormal': [F('SnappingJaxfruit'), F('Flyconid')],
    'SoulFyshBoss': [F('SoulFysh')],
    'SoulNexusElite': [F('SoulNexus')],
    'SpinyToadNormal': [F('SpinyToad')],
    'TerrorEelElite': [F('TerrorEel')],
    'TestSubjectBoss': [F('TestSubject')],
    'TheInsatiableBoss': [F('TheInsatiable')],
    'TheKinBoss': [F('KinFollower', 2), F('KinPriest')],
    'TheLostAndForgottenNormal': [F('TheLost'), F('TheForgotten')],
    'TheObscuraNormal': [F('TheObscura')],
    'ThievingHopperWeak': [F('ThievingHopper')],
    'ToadpolesWeak': [F('Toadpole', 2)],
    'TunnelerWeak': [F('Tunneler')],
    'TurretOperatorWeak': [F('LivingShield'), F('TurretOperator')],
    'TwoTailedRatsNormal': [F('TwoTailedRat', 3)],
    'VantomBoss': [F('Vantom')],
    'VineShamblerNormal': [F('VineShambler')],
    'WaterfallGiantBoss': [F('WaterfallGiant')],
}

# 召唤 / 复活 / 多阶段：不进开局 HP，但单列「等效总 HP」说明
SUMMONS = {
    'Fogmog': 'EyeWithTeeth', 'LivingFog': 'GasBomb', 'Ovicopter': 'ToughEgg', 'TheObscura': 'Parafright',
    'TwoTailedRat': 'TwoTailedRat', 'PhrogParasite': 'Wriggler(InfestedPower 死后孵出)',
    'GremlinMerc': 'SneakyGremlin+FatGremlin(SurprisePower)', 'Fabricator': 'Guardbot/Noisebot/Stabbot/Zapbot',
    'Axebot': 'Axebot(StockPower 复活 2 次，每次 MaxHp+10)', 'TestSubject': '三形态 100/200/300（A10 111/212/313）',
}
# 等效总 HP（多条命）：(A0 均值, A10 均值, 说明)
EFFECTIVE_HP = {
    'Axebot': (lambda a0, a10: (3 * a0 + 30, 3 * a10 + 30), '三条命：第 n 条 MaxHp +10n，Axebot.cs:44,54'),
    'TestSubject': (lambda a0, a10: (600, 636), '三形态 FirstFormHp+SecondFormHp+ThirdFormHp，TestSubject.cs'),
}


def hp_stats(mid, mons):
    m = mons.get(mid)
    if not m or m['hp_min'] is None:
        return None
    return m


def comp_eval(groups, mons, key):
    """key: 'hp_mean_a0' 等 -> 期望值；同时返回 min / max / 期望数量"""
    exp_v, mn, mx, cnt = 0.0, 0.0, 0.0, 0.0
    for g in groups:
        if g[0] == 'fix':
            m = mons[g[1]]
            exp_v += g[2] * (m[key] or 0)
            mn += g[2] * (m[key + '_lo'] if key + '_lo' in m else m[key] or 0)
            mx += g[2] * (m[key + '_hi'] if key + '_hi' in m else m[key] or 0)
            cnt += g[2]
        elif g[0] == 'pick':
            k, cands, distinct = g[1], g[2], g[3]
            vals = [mons[c][key] or 0 for c in cands]
            los = sorted(mons[c].get(key + '_lo', mons[c][key] or 0) for c in cands)
            his = sorted((mons[c].get(key + '_hi', mons[c][key] or 0) for c in cands), reverse=True)
            exp_v += k * statistics.mean(vals)
            mn += sum(los[:k]) if distinct else k * los[0]
            mx += sum(his[:k]) if distinct else k * his[0]
            cnt += k
        elif g[0] == 'alt':
            subs = [(p, comp_eval(sub, mons, key)) for p, sub in g[1]]
            exp_v += sum(p * s[0] for p, s in subs)
            mn += min(s[1] for _, s in subs)
            mx += max(s[2] for _, s in subs)
            cnt += sum(p * s[3] for p, s in subs)
    return exp_v, mn, mx, cnt


# 核查补丁：同侧怪物掷 HP 时剔除队友已用的值（Creature.SetUniqueMonsterHpValue，Creature.cs:372-384，单机口径），
# 所以同种多只的 HP 必然互不相同；千足虫三段另把 HP 调成偶数并互相错开（DecimillipedeSegment.cs:118-145）。
# HP 区间的最小/最大按此求（期望值不受影响）。
EVEN_HP = {'DecimillipedeSegmentFront', 'DecimillipedeSegmentMiddle', 'DecimillipedeSegmentBack'}


def comp_expand(groups):
    """展开成所有可能的具体组成（类名列表）"""
    combos = [[]]
    for g in groups:
        if g[0] == 'fix':
            opts = [[g[1]] * g[2]]
        elif g[0] == 'pick':
            gen = itertools.combinations if g[3] else itertools.combinations_with_replacement
            opts = [list(c) for c in gen(g[2], g[1])]
        else:  # alt
            opts = [c for _, sub in g[1] for c in comp_expand(sub)]
        combos = [a + b for a in combos for b in opts]
    return combos


def hp_bounds(groups, mons, mode):
    """-> (最小总 HP, 最大总 HP)，同侧 HP 不重复；等效 HP 的附加量（巨斧机器人补货、实验体后两形态）照加"""
    def vals(c):
        m = mons[c]
        v = range(int(m[f'hp_min_{mode}']), int(m[f'hp_max_{mode}']) + 1)
        return sorted({x + x % 2 for x in v}) if c in EVEN_HP else list(v)
    lo_best, hi_best = None, None
    for combo in comp_expand(groups):
        extra = sum(mons[c][f'hp_eff_{mode}'] - mons[c][f'hp_mean_{mode}'] for c in combo)
        tot = []
        for low in (True, False):
            used, s = set(), 0
            for c in sorted(combo, key=lambda c: vals(c)[0] if low else -vals(c)[-1]):
                vs = vals(c) if low else vals(c)[::-1]
                cand = [x for x in vs if x not in used]
                x = cand[0] if cand else vs[0]   # 区间用尽时游戏退回随机掷，这里取端点
                used.add(x)
                s += x
            tot.append(s + extra)
        lo_best = tot[0] if lo_best is None else min(lo_best, tot[0])
        hi_best = tot[1] if hi_best is None else max(hi_best, tot[1])
    return lo_best, hi_best


def comp_text(groups, mons):
    parts = []
    for g in groups:
        if g[0] == 'fix':
            nm = mons[g[1]]['name_zh'] or g[1]
            parts.append(f"{nm}" + (f"×{g[2]}" if g[2] > 1 else ''))
        elif g[0] == 'pick':
            nm = '/'.join(mons[c]['name_zh'] or c for c in g[2])
            parts.append(f"{g[1]}只{'不重复' if g[3] else ''}于[{nm}]")
        elif g[0] == 'alt':
            parts.append('三选一{' + ' | '.join(comp_text(sub, mons) for _, sub in g[1]) + '}')
    return ' + '.join(parts)


def comp_members(groups):
    out = []
    for g in groups:
        if g[0] == 'fix':
            out.append(g[1])
        elif g[0] == 'pick':
            out += g[2]
        elif g[0] == 'alt':
            for _, sub in g[1]:
                out += comp_members(sub)
    return out


# ---------------------------------------------------------------- 主流程
def main():
    files = sorted(glob.glob(os.path.join(MON, '*.cs')))
    srcs = {os.path.splitext(os.path.basename(p))[0]: read(p) for p in files}
    parent_of = {}
    for cls, s in srcs.items():
        m = re.search(r'class \w+ : (\w+)', s)
        if m and m.group(1) != 'MonsterModel':
            parent_of[cls] = m.group(1)

    mons, move_rows = {}, []
    for cls, s in srcs.items():
        par = parent_of.get(cls)
        full = (srcs[par] + '\n' + s) if par else s
        props = Props(srcs[par]) if par else None
        props = Props(s, props)
        for k, v in PROP_OVERRIDES.get(cls, {}).items():
            if isinstance(v, str):
                props.expr[k] = v
            else:
                props.const[k] = v
        PROPS_CTX[0] = props
        mid = snake(cls)
        lockey = mid
        init, states, flags = parse_state_machine(s)
        if not states and par:
            init, states, flags = parse_state_machine(srcs[par])
            flags.add('inherit_sm')
        if cls in INIT_OVERRIDE:
            init = INIT_OVERRIDE[cls]
            flags.discard('init_random')
        rec = dict(cls=cls, id=mid, name_zh=L('monsters', lockey + '.name'), name_en=L('monsters', lockey + '.name', 'eng'),
                   parent=par or '')
        if not rec['name_zh'] and par:  # 千足虫三段没有独立本地化，用父类名 + 段位
            seg = {'Front': '（头）', 'Middle': '（身）', 'Back': '（尾）'}
            suf = next((v for k, v in seg.items() if cls.endswith(k)), '')
            rec['name_zh'] = L('monsters', snake(par) + '.name') + suf
            rec['name_en'] = L('monsters', snake(par) + '.name', 'eng') + suf
        rec['name_zh'] = rec['name_zh'].replace(' #C{Count}', '')
        for mode in ('a0', 'a10'):
            lo = props.ev('MinInitialHp', mode)
            hi = props.ev('MaxInitialHp', mode)
            rec[f'hp_min_{mode}'], rec[f'hp_max_{mode}'] = lo, hi
            rec[f'hp_mean_{mode}'] = (lo + hi) / 2 if lo is not None and hi is not None else None
            rec[f'hp_mean_{mode}_lo'], rec[f'hp_mean_{mode}_hi'] = lo, hi
        rec['hp_min'] = rec['hp_min_a0']
        sp0 = start_powers(full if par else s, props, 'a0')
        sp10 = start_powers(full if par else s, props, 'a10')
        rec['start_powers'] = '; '.join(
            f"{n} {'' if v0 is None else int(v0)}" + ('' if v0 == v10 or v10 is None else f"/{int(v10)}")
            for (n, v0), (_, v10) in zip(sp0, sp10))
        info = {'a0': {'__start__': sp0}, 'a10': {'__start__': sp10}}
        srcm = full if par else s
        move_list = []
        for var, st in states.items():
            if st.kind != 'move':
                continue
            row = dict(monster=mid, monster_zh=rec['name_zh'], move=st.id,
                       move_zh=L('monsters', f"{lockey}.moves.{st.id.replace('_MOVE', '')}.title"),
                       intents='; '.join(n.replace('Intent', '') + (f"({','.join(a)})" if a else '') for n, a in st.intents),
                       followup=states[st.follow].id if st.follow in states else '',
                       must_once='Y' if st.must_once else '')
            for mode in ('a0', 'a10'):
                per, hits, tot, ok = intent_damage(st.intents, props, mode)
                sgain, rgain = move_effects(srcm, st.method, props, mode)
                is_att = any(n in ('SingleAttackIntent', 'MultiAttackIntent', 'DeathBlowIntent') for n, _ in st.intents)
                info[mode][var] = dict(dmg=tot, hits=hits, str=sgain, rit=rgain, is_attack=is_att and ok)
                row[f'dmg_{mode}'] = '' if per is None else (f"{int(per)}" if hits <= 1 else f"{int(per)}x{int(hits)}")
                row[f'total_{mode}'] = '' if not is_att else (int(tot) if ok else '?')
                row[f'self_str_{mode}'] = (int(sgain) if sgain else '') if not rgain else f"ritual {int(rgain)}"
            move_rows.append(row)
            move_list.append(row)
        rec['n_moves'] = len(move_list)
        rec['initial_move'] = '/'.join(states[i].id for i in init)
        kinds = sorted({st.kind for st in states.values()})
        rec['sm_kinds'] = '+'.join(kinds)
        rec['moves_a0_a10'] = ' | '.join(
            f"{r['move_zh'] or r['move']}:{r['dmg_a0'] or '-'}" + ('' if r['dmg_a0'] == r['dmg_a10'] else f"→{r['dmg_a10']}")
            for r in move_list)
        att = [r for r in move_list if isinstance(r['total_a0'], int)]
        rec['max_move_dmg_a0'] = max((r['total_a0'] for r in att), default=0)
        rec['max_move_dmg_a10'] = max((r['total_a10'] for r in att if isinstance(r['total_a10'], int)), default=0)
        for mode in ('a0', 'a10'):
            pt, freq = simulate(init, states, info[mode], mode, flags)
            rec[f'dmg_t1_{mode}'] = round(pt[0], 1) if pt else None
            rec[f'dmg_avg6_{mode}'] = round(sum(pt) / len(pt), 1) if pt else None
            rec[f'dmg_turns_{mode}'] = '/'.join(f"{x:.0f}" for x in pt) if pt else ''
            if mode == 'a0':
                total = sum(freq.values()) or 1
                rec['move_freq_6t'] = ' '.join(f"{states[v].id.replace('_MOVE','')}:{c / total:.0%}" for v, c in freq.most_common())
        rec['hp_mean_a0_lo'], rec['hp_mean_a0_hi'] = rec['hp_min_a0'], rec['hp_max_a0']
        rec['hp_mean_a10_lo'], rec['hp_mean_a10_hi'] = rec['hp_min_a10'], rec['hp_max_a10']
        rec['dmg_avg6_a0_v'] = rec['dmg_avg6_a0'] or 0
        rec['dmg_avg6_a10_v'] = rec['dmg_avg6_a10'] or 0
        rec['dmg_t1_a0_v'] = rec['dmg_t1_a0'] or 0
        rec['dmg_t1_a10_v'] = rec['dmg_t1_a10'] or 0
        rec['sim_flags'] = ','.join(sorted(flags))
        rec['summons'] = SUMMONS.get(cls, '')
        if cls in EFFECTIVE_HP and rec['hp_mean_a0']:
            f, note = EFFECTIVE_HP[cls]
            e0, e10 = f(rec['hp_mean_a0'], rec['hp_mean_a10'])
            rec['effective_hp'] = f"{e0:.0f}/{e10:.0f}（{note}）"
        else:
            rec['effective_hp'] = ''
        rec['file'] = f'MegaCrit.Sts2.Core.Models.Monsters/{cls}.cs'
        mons[cls] = rec

    # 有效总 HP 写回均值（Axebot / TestSubject 用多条命口径进预算）
    for cls in EFFECTIVE_HP:
        r = mons[cls]
        e0, e10 = EFFECTIVE_HP[cls][0](r['hp_mean_a0'], r['hp_mean_a10'])
        for mode, e in (('a0', e0), ('a10', e10)):
            r[f'hp_eff_{mode}'] = e
    for r in mons.values():
        for mode in ('a0', 'a10'):
            r.setdefault(f'hp_eff_{mode}', r[f'hp_mean_{mode}'])
            if r[f'hp_eff_{mode}'] is not None and r[f'hp_mean_{mode}'] is not None:
                d = r[f'hp_eff_{mode}'] - r[f'hp_mean_{mode}']
                r[f'hp_eff_{mode}_lo'] = (r[f'hp_min_{mode}'] or 0) + d
                r[f'hp_eff_{mode}_hi'] = (r[f'hp_max_{mode}'] or 0) + d

    acts, encs = act_info(), enc_info()
    act_zh = {a: L('acts', snake(a) + '.title') for a in acts}
    pool_of = {}
    enc_rows = []
    for a, d in sorted(acts.items(), key=lambda kv: (kv[1]['index'], kv[0])):
        if d['index'] < 0:
            continue
        for e in d['encs']:
            ei = encs[e]
            pool = {'Boss': 'Boss', 'Elite': '精英'}.get(ei['room'], '弱' if ei['weak'] else '普通')
            comp = COMPOSITION.get(e)
            if comp is None:
                print('!! 缺组成', e)
                continue
            row = dict(act=a, act_zh=act_zh[a], act_index=d['index'], pool=pool, encounter=e,
                       encounter_zh=L('encounters', snake(e) + '.title'), tags=','.join(ei['tags']),
                       composition=comp_text(comp, mons))
            for mode in ('a0', 'a10'):
                ev, mn, mx, cnt = comp_eval(comp, mons, f'hp_eff_{mode}')
                mn, mx = hp_bounds(comp, mons, mode)
                row[f'hp_min_{mode}'], row[f'hp_max_{mode}'], row[f'hp_exp_{mode}'] = round(mn), round(mx), round(ev)
                row['n_monsters'] = round(cnt, 2)
                dv = comp_eval(comp, mons, f'dmg_avg6_{mode}_v')[0]
                d1 = comp_eval(comp, mons, f'dmg_t1_{mode}_v')[0]
                row[f'dmg_t1_{mode}'] = round(d1, 1)
                row[f'dmg_avg6_{mode}'] = round(dv, 1)
            row['hp_asc_pct'] = f"{(row['hp_exp_a10'] / row['hp_exp_a0'] - 1) * 100:.1f}%" if row['hp_exp_a0'] else ''
            row['dmg_asc_pct'] = f"{(row['dmg_avg6_a10'] / row['dmg_avg6_a0'] - 1) * 100:.1f}%" if row['dmg_avg6_a0'] else ''
            members = comp_members(comp)
            row['sim_flags'] = ','.join(sorted({f for mm in members for f in mons[mm]['sim_flags'].split(',') if f}))
            row['summons'] = '; '.join(sorted({mons[mm]['summons'] for mm in members if mons[mm]['summons']}))
            enc_rows.append(row)
            for mm in members:
                pool_of.setdefault(mm, set()).add((a, pool, e))

    # 事件战斗 / 其他遭遇里出现的怪
    for e, ei in encs.items():
        if any(e in d['encs'] for d in acts.values()):
            continue
        s = read(os.path.join(ENC, e + '.cs'))
        for mm in set(re.findall(r'Monster<(\w+)>', s)):
            pool_of.setdefault(mm, set()).add(('-', '事件/其他', e))
    for summoner, sm in SUMMONS.items():
        for mm in re.findall(r'[A-Z][a-zA-Z]+', sm.split('(')[0]):
            if mm in mons and mm != summoner:
                for (a, p, e) in list(pool_of.get(summoner, [])):
                    pool_of.setdefault(mm, set()).add((a, p + '(召唤)', e))

    # 输出 monster_stats
    stat_cols = ['id', 'cls', 'name_zh', 'name_en', 'acts', 'pools', 'encounters',
                 'hp_min_a0', 'hp_max_a0', 'hp_min_a10', 'hp_max_a10', 'hp_asc_pct', 'effective_hp', 'start_powers',
                 'n_moves', 'initial_move', 'sm_kinds', 'moves_a0_a10', 'max_move_dmg_a0', 'max_move_dmg_a10',
                 'dmg_t1_a0', 'dmg_t1_a10', 'dmg_avg6_a0', 'dmg_avg6_a10', 'dmg_turns_a0', 'dmg_turns_a10', 'move_freq_6t',
                 'summons', 'sim_flags', 'parent', 'file']
    out_rows = []
    for cls, r in sorted(mons.items()):
        po = pool_of.get(cls, set())
        r['acts'] = '|'.join(sorted({act_zh.get(a, a) for a, _, _ in po if a != '-'}))
        r['pools'] = '|'.join(sorted({p for _, p, _ in po}))
        r['encounters'] = '|'.join(sorted({e for _, _, e in po}))
        r['hp_asc_pct'] = f"{(r['hp_mean_a10'] / r['hp_mean_a0'] - 1) * 100:.1f}%" if r['hp_mean_a0'] else ''
        out = {k: r.get(k, '') for k in stat_cols}
        for k in ('hp_min_a0', 'hp_max_a0', 'hp_min_a10', 'hp_max_a10'):
            out[k] = '' if r[k] is None else int(r[k])
        out_rows.append(out)
    write('ch04_monster_stats.csv', out_rows, stat_cols)
    mv_cols = ['monster', 'monster_zh', 'move', 'move_zh', 'intents', 'dmg_a0', 'dmg_a10', 'total_a0', 'total_a10',
               'self_str_a0', 'self_str_a10', 'followup', 'must_once']
    write('ch04_monster_moves.csv', move_rows, mv_cols)
    enc_cols = ['act', 'act_zh', 'act_index', 'pool', 'encounter', 'encounter_zh', 'tags', 'composition', 'n_monsters',
                'hp_min_a0', 'hp_max_a0', 'hp_exp_a0', 'hp_min_a10', 'hp_max_a10', 'hp_exp_a10', 'hp_asc_pct',
                'dmg_t1_a0', 'dmg_t1_a10', 'dmg_avg6_a0', 'dmg_avg6_a10', 'dmg_asc_pct', 'summons', 'sim_flags']
    write('ch04_encounter_pools.csv', enc_rows, enc_cols)

    # 按幕 x 池子汇总
    bud = []
    order = {'弱': 0, '普通': 1, '精英': 2, 'Boss': 3}
    grp = collections.defaultdict(list)
    for r in enc_rows:
        grp[(r['act_index'], r['act'], r['pool'])].append(r)
    for (idx, a, pool), rs in sorted(grp.items(), key=lambda kv: (kv[0][0], kv[0][1], order[kv[0][2]])):
        b = dict(act_index=idx, act=a, act_zh=act_zh[a], pool=pool, n_encounters=len(rs),
                 rooms=acts[a]['rooms'], weak_slots=acts[a]['weak'])
        for mode in ('a0', 'a10'):
            hp = [r[f'hp_exp_{mode}'] for r in rs]
            dm = [r[f'dmg_avg6_{mode}'] for r in rs]
            d1 = [r[f'dmg_t1_{mode}'] for r in rs]
            b[f'hp_mean_{mode}'] = round(statistics.mean(hp))
            b[f'hp_lo_{mode}'] = min(r[f'hp_min_{mode}'] for r in rs)
            b[f'hp_hi_{mode}'] = max(r[f'hp_max_{mode}'] for r in rs)
            b[f'dmg_t1_mean_{mode}'] = round(statistics.mean(d1), 1)
            b[f'dmg_avg6_mean_{mode}'] = round(statistics.mean(dm), 1)
        b['monsters_per_enc'] = round(statistics.mean(r['n_monsters'] for r in rs), 2)
        b['hp_asc_pct'] = f"{(b['hp_mean_a10'] / b['hp_mean_a0'] - 1) * 100:.1f}%"
        b['dmg_asc_pct'] = f"{(b['dmg_avg6_mean_a10'] / b['dmg_avg6_mean_a0'] - 1) * 100:.1f}%" if b['dmg_avg6_mean_a0'] else ''
        b['encounters'] = ','.join(r['encounter_zh'] or r['encounter'] for r in rs)
        bud.append(b)
        # 进阶 10 DoubleBoss：最后一幕首个 Boss 打完后再从剩下 2 个里抽 1 个（RunManager.GenerateRooms）
        if pool == 'Boss' and idx == max(d['index'] for d in acts.values()):
            pairs = [(x, y) for i, x in enumerate(rs) for y in rs[i + 1:]]
            b2 = dict(act_index=idx, act=a, act_zh=act_zh[a], pool='Boss×2(进阶10)', n_encounters=len(pairs),
                      rooms=acts[a]['rooms'], weak_slots=acts[a]['weak'])
            for mode in ('a0', 'a10'):
                b2[f'hp_mean_{mode}'] = round(statistics.mean(x[f'hp_exp_{mode}'] + y[f'hp_exp_{mode}'] for x, y in pairs))
                b2[f'hp_lo_{mode}'] = min(x[f'hp_min_{mode}'] + y[f'hp_min_{mode}'] for x, y in pairs)
                b2[f'hp_hi_{mode}'] = max(x[f'hp_max_{mode}'] + y[f'hp_max_{mode}'] for x, y in pairs)
                b2[f'dmg_t1_mean_{mode}'] = b[f'dmg_t1_mean_{mode}']
                b2[f'dmg_avg6_mean_{mode}'] = b[f'dmg_avg6_mean_{mode}']
            b2['monsters_per_enc'] = round(statistics.mean(x['n_monsters'] + y['n_monsters'] for x, y in pairs), 2)
            b2['hp_asc_pct'] = f"{(b2['hp_mean_a10'] / b['hp_mean_a0'] - 1) * 100:.1f}%（相对 A0 单 Boss）"
            b2['dmg_asc_pct'] = '两场分开打，单场伤害同 Boss 行'
            b2['encounters'] = ','.join(f"{x['encounter_zh']}+{y['encounter_zh']}" for x, y in pairs)
            bud.append(b2)
    bcols =['act_index', 'act', 'act_zh', 'pool', 'n_encounters', 'rooms', 'weak_slots', 'monsters_per_enc',
             'hp_lo_a0', 'hp_mean_a0', 'hp_hi_a0', 'hp_lo_a10', 'hp_mean_a10', 'hp_hi_a10', 'hp_asc_pct',
             'dmg_t1_mean_a0', 'dmg_t1_mean_a10', 'dmg_avg6_mean_a0', 'dmg_avg6_mean_a10', 'dmg_asc_pct', 'encounters']
    write('ch04_hp_budget_by_act.csv', bud, bcols)

    # 控制台摘要
    fl = collections.Counter(f for r in mons.values() for f in r['sim_flags'].split(',') if f)
    print('monsters', len(mons), 'moves', len(move_rows), 'act encounters', len(enc_rows))
    print('flags', dict(fl))
    for b in bud:
        print(b['act_zh'], b['pool'], b['n_encounters'], 'HP', b['hp_mean_a0'], '->', b['hp_mean_a10'],
              'dmg6', b['dmg_avg6_mean_a0'], '->', b['dmg_avg6_mean_a10'])


def write(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == '__main__':
    main()
