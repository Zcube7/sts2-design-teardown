"""第 05 章：59 个普通事件 + 9 个 Ancient 事件的结构化抽取 -> data/csv/ch05_events_detail.csv / ch05_ancients.csv

python -I -X utf8 scripts/ch05_extract_events.py
(在 outputs/sts2_rea_Claude 目录下跑；只读 csharp/ 与 data/pck_text/，不碰游戏目录)

做法：正则读事件 .cs（IsAllowed 条件、命令调用、战斗/宠物/任务标记）+ 简中本地化（页面、选项标题/描述）。
命令标签是"代码里出现过"的粗粒度信号，具体数值和分支要回源码看。
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
EV_DIR = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Events')
ACT_DIR = os.path.join(SRC, 'MegaCrit.Sts2.Core.Models.Acts')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization')
OUT = os.path.join(ROOT, 'data', 'csv')


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def read(p):
    with open(p, encoding='utf-8-sig') as f:
        return f.read()


ev_zh = load_json(os.path.join(LOC, 'zhs', 'events.json'))
anc_zh = load_json(os.path.join(LOC, 'zhs', 'ancients.json'))
anc_en = load_json(os.path.join(LOC, 'eng', 'ancients.json'))
rel_zh = load_json(os.path.join(LOC, 'zhs', 'relics.json'))

base_rows = {r['cls']: r for r in csv.DictReader(open(os.path.join(OUT, 'events.csv'), encoding='utf-8-sig'))}


def snake(name):
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name)
    s = re.sub(r'(?<=[A-Z])([A-Z][a-z])', r'_\1', s)
    return s.upper()


# ---------- 事件归属：各幕 AllEvents + ModelDb.AllSharedEvents ----------
pool = {}
for act in ['Overgrowth', 'Underdocks', 'Hive', 'Glory']:
    t = read(os.path.join(ACT_DIR, act + '.cs'))
    m = re.search(r'AllEvents\s*=>.*?\}\);', t, re.S)
    for e in re.findall(r'ModelDb\.Event<(\w+)>', m.group(0)):
        pool.setdefault(e, []).append(act)
t = read(os.path.join(SRC, 'MegaCrit.Sts2.Core.Models', 'ModelDb.cs'))
m = re.search(r'AllSharedEvents\s*=>.*?\}\)\);', t, re.S)
for e in re.findall(r'Event<(\w+)>', m.group(0)):
    pool.setdefault(e, []).append('Shared')

epoch_gate = {}
for i in (1, 2, 3):
    t = read(os.path.join(SRC, 'MegaCrit.Sts2.Core.Timeline.Epochs', f'Event{i}Epoch.cs'))
    for e in re.findall(r'ModelDb\.Event<(\w+)>', t):
        epoch_gate[e] = f'Event{i}Epoch'

ACT_ZH = {'Overgrowth': '密林', 'Underdocks': '暗港', 'Hive': '巢穴', 'Glory': '荣耀', 'Shared': '通用'}

# ---------- 命令标签 ----------
TAGS = [
    ('得金币', r'PlayerCmd\.GainGold|new GoldReward'),
    ('失金币', r'PlayerCmd\.LoseGold'),
    ('扣血', r'CreatureCmd\.Damage|ThatDoesDamage'),
    ('回血', r'CreatureCmd\.Heal|MimicRestSiteHeal'),
    ('加最大HP', r'CreatureCmd\.GainMaxHp'),
    ('减最大HP', r'CreatureCmd\.LoseMaxHp|ThatDecreasesMaxHp'),
    ('得遗物', r'RelicCmd\.Obtain|new RelicReward|RelicFactory\.Pull'),
    ('失遗物', r'RelicCmd\.Remove'),
    ('得卡', r'new CardReward|new SpecialCardReward|SelectCardsToAddToDeck|CardFactory\.CreateForReward|CardPileCmd\.Add\('),
    ('得诅咒', r'AddCurseToDeck|AddCursesToDeck'),
    ('升级', r'CardCmd\.Upgrade|FromDeckForUpgrade'),
    ('降级', r'CardCmd\.Downgrade'),
    ('删牌', r'FromDeckForRemoval|CardPileCmd\.RemoveFromDeck'),
    ('变化', r'FromDeckForTransformation|CardCmd\.Transform'),
    ('附魔', r'CardCmd\.Enchant|FromDeckForEnchantment'),
    ('苦难', r'CardCmd\.Afflict|Affliction<'),
    ('得药水', r'new PotionReward|PotionCmd\.TryToProcure'),
    ('失药水', r'PotionCmd\.Discard'),
    ('进战斗', r'EnterCombatWithoutExitingEvent|CanonicalEncounter'),
    ('任务卡', r'CardType\.Quest|Quest\b|CompleteQuest'),
    ('宠物', r'HasEventPet|Pet\b'),
]


def method_body(text, sig_regex):
    m = re.search(sig_regex, text)
    if not m:
        return None
    i = text.find('{', m.end())
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return None


BB = re.compile(r'\[/?[a-z_]+(?:[= ][^\]]*)?\]')


def clean(s, vars_map):
    s = BB.sub('', s or '')
    def rep(m):
        name = m.group(1)
        v = str(vars_map.get(name, ''))
        v = re.sub(r'ModelDb\.\w+<(\w+)>\(\)(?:\.\w+(?:\(\))?)*', lambda mm: '<' + mm.group(1) + '>', v)
        # 运行时才算出的值（CalculateVars 里随机/按 HP 算）在基础表里是 0，保留占位符
        if not v or v in ('0', '0m') or v.startswith('-'):
            return '{' + name + '}'
        return v
    s = re.sub(r'\{(\w+)(?::[^{}]*(?:\{[^{}]*\}[^{}]*)*)?\}', rep, s)
    return re.sub(r'\s+', ' ', s).strip()


def parse_vars(vs):
    out = {}
    for part in (vs or '').split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out


rows = []
for fn in sorted(os.listdir(EV_DIR)):
    cls = fn[:-3]
    text = read(os.path.join(EV_DIR, fn))
    b = base_rows.get(cls, {})
    base = b.get('base', '')
    if base == 'AncientEventModel':
        continue
    eid = b.get('id') or snake(cls)
    vars_map = parse_vars(b.get('vars'))
    # 选项（只取 INITIAL 页）
    opts = []
    pref = f'{eid}.pages.INITIAL.options.'
    names = []
    for k in ev_zh:
        if k.startswith(pref) and k.endswith('.title'):
            names.append(k[len(pref):-len('.title')])
    for n in names:
        title = clean(ev_zh.get(pref + n + '.title'), vars_map)
        desc = clean(ev_zh.get(pref + n + '.description'), vars_map)
        opts.append(f'{title}：{desc}' if desc else title)
    pages = sorted({k.split('.')[2] for k in ev_zh if k.startswith(eid + '.pages.')})
    all_opt_cnt = len([k for k in ev_zh if k.startswith(eid + '.pages.') and '.options.' in k and k.endswith('.title')])
    allowed = method_body(text, r'public override bool IsAllowed\(IRunState runState\)')
    allowed = re.sub(r'\s+', ' ', allowed).strip() if allowed else ''
    tags = [name for name, rx in TAGS if re.search(rx, text)]
    layout = re.search(r'LayoutType\s*=>\s*EventLayoutType\.(\w+)', text)
    rows.append({
        'id': eid,
        'cls': cls,
        'name_zh': b.get('name_zh') or ev_zh.get(eid + '.title', ''),
        'name_en': b.get('name_en', ''),
        'pool': '/'.join(ACT_ZH[a] for a in pool.get(cls, [])) or '特殊',
        'epoch_gate': epoch_gate.get(cls, ''),
        'is_shared_mp': 'IsShared => true' in text,
        'layout': layout.group(1) if layout else 'Default',
        'is_allowed': allowed[:400],
        'n_initial_options': len(names),
        'n_all_options': all_opt_cnt,
        'n_pages': len(pages),
        'pages': '|'.join(pages),
        'tags': '|'.join(tags),
        'vars': b.get('vars', ''),
        'initial_options_zh': ' ／ '.join(opts),
        'src_lines': text.count('\n') + 1,
        'src': f'MegaCrit.Sts2.Core.Models.Events/{fn}',
    })

with open(os.path.join(OUT, 'ch05_events_detail.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print('events:', len(rows))

# ---------- Ancient ----------
ANC_META = {
    'Neow': ('第1幕起点（密林/暗港）', 'NeowEpoch 揭示前不出现（首局起点改为怪物房）',
             '1 个「带代价」遗物（10 选 1，已过滤 IsAllowedAtNeow）+ 2 个正面遗物（14 个基础正面 + 3 组二选一[熔岩石/小型扭蛋][营养牡蛎/石炉加湿器][涅奥的护符/橙型香盒]，剔除与代价项互斥的）洗牌取 2；有自定义修饰符时改为修饰符选项'),
    'Orobas': ('第2幕起点（巢穴）', 'OrobasEpoch 揭示前从候选中移除',
               '池1[放电异虾/玻璃眼珠 + (1/3 棱彩宝石 或 2/3 随机另一已解锁角色的海玻璃)]取1 + 池2[炼金箱/浮木/发光珍珠/沙堡]取1 + 池3[欧洛巴斯之触/古老牙齿（需 SetupForPlayer 成功，都失败则显示锁定项）]取1'),
    'Pael': ('第2幕起点（巢穴）', '无',
             '池1[佩尔之肉/角/泪]取1 + 池2[佩尔之翼；≥3 张可附魔 Goopy 时加佩尔之爪；≥5 张可移除牌时加佩尔之牙；整表复制一份后再加 1 个佩尔的增生组织（其权重减半）]取1 + 池3[佩尔之眼/血；无事件宠物时加佩尔的士兵]取1'),
    'Tezcatara': ('第2幕起点（巢穴）', '无',
                  '池1[烫嘴可可/美味饼干；牌组有基础打击时加营养汤]取1 + 池2[大～抱抱/故事书/烘焙手套]取1 + 池3[黄金罗盘/南瓜蜡烛/玩具盒/黄金印]取1'),
    'Nonupeipe': ('第3幕起点（荣耀）', '无',
                  '9 个遗物（≥4 张牌可附魔 Swift「迅速」时加华美手镯）洗牌取 3'),
    'Tanx': ('第3幕起点（荣耀）', '无',
             '9 个武器系遗物（≥3 张牌可附魔 Instinct 时加三刃回旋镖）洗牌取 3'),
    'Vakuu': ('第3幕起点（荣耀）', '无',
              '池1[血染玫瑰/低语耳环/小提琴]、池2[腌制活雾/原初之爪(选项附带减 9 最大HP)/卓越斗篷]、池3[选择悖论/音乐盒/领主阳伞/宝石面具] 各取 1'),
    'Darv': ('共享：第2幕 50%、第3幕 25% 进入候选', 'DarvEpoch 揭示前不出现',
             '11 组「条件+遗物」（星盘/黑星/召唤铃铛/空鸟笼/潘多拉魔盒[无清牌组修饰符]/符文金字塔/异蛇之眼/灵体外质[仅第2幕]/添水[仅第2幕]/贤者之石[第2幕起]/天鹅绒颈圈[第2幕起]）过滤后洗牌；50% 取 2 个 + 尘封魔典，50% 取 3 个'),
    'DeprecatedAncientEvent': ('—', '—', '存档兼容用的占位类，不参与生成'),
}
anc_rows = []
for cls, (where, gate, rule) in ANC_META.items():
    text = read(os.path.join(EV_DIR, cls + '.cs'))
    key = snake(cls)
    relics = []
    for r in re.findall(r'(?:RelicOption<|Relic<)(\w+)>', text):
        if r not in relics:
            relics.append(r)
    rz = [f'{rel_zh.get(snake(r) + ".title", r)}({r})' for r in relics]
    m = re.search(r'GenerateInitialOptions\(\)', text)
    anc_rows.append({
        'cls': cls,
        'name_zh': anc_zh.get(key + '.title', ''),
        'epithet_zh': anc_zh.get(key + '.epithet', ''),
        'epithet_en': anc_en.get(key + '.epithet', ''),
        'where': where,
        'unlock_gate': gate,
        'option_rule': rule,
        'n_relics_in_pools': len(relics),
        'relics': '；'.join(rz),
        'n_dialogue_keys_zh': len([k for k in anc_zh if k.startswith(key + '.talk.')]),
        'src': f'MegaCrit.Sts2.Core.Models.Events/{cls}.cs',
    })
with open(os.path.join(OUT, 'ch05_ancients.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(anc_rows[0].keys()))
    w.writeheader()
    w.writerows(anc_rows)
print('ancients:', len(anc_rows))
