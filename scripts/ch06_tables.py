# -*- coding: utf-8 -*-
"""第 06 章：进阶表 + 成就/徽章表
输出 data/csv/ch06_ascension.csv、data/csv/ch06_achievements_badges.csv
用法：python -I -X utf8 scripts/ch06_tables.py
数值均为人工从源码核对后录入（出处列给出文件:行）；标题/描述从 zhs 本地化读取。
"""
import csv, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization', 'zhs')
CSV = os.path.join(ROOT, 'data', 'csv')
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')

def loc(name):
    with open(os.path.join(LOC, name), encoding='utf-8') as f:
        return json.load(f)

def strip(s):
    return re.sub(r'\[/?\w+\]', '', s or '').replace('\n', ' ')

asc = loc('ascension.json')
ach = loc('achievements.json')
bad = loc('badges.json')

# ---------------- 进阶 ----------------
A = [
    (1, 'SwarmingElites', '每幕地图精英点数 5 → round(5×1.6)=8', 'MegaCrit.Sts2.Core.Map/MapPointTypeCounts.cs:15',
     '2024-10 首版 A1 为 Burly Enemies；2025-01 改 Mighty Bosses；现为精英蜂拥'),
    (2, 'WearyTraveler', '先古之民事件开场回血：回复已损失生命的 80%（普通 100%）；涅奥开局先把 HP 置 0 再回血，所以 A2 起开局只有 80% 最大生命', 'MegaCrit.Sts2.Core.Models/AncientEventModel.cs:176-189',
     '2025-11-06 起也影响开局 HP；2025-11-13 75%→80%'),
    (3, 'Poverty', '战斗金币上下限 ×0.75（普通 10-20 / 精英 35-45 / Boss 100）；宝箱金币 42-52 ×0.75', 'MegaCrit.Sts2.Core.Models/EncounterModel.cs:64-98；MegaCrit.Sts2.Core.Multiplayer.Game/OneOffSynchronizer.cs:133；MegaCrit.Sts2.Core.Helpers/AscensionHelper.cs:PovertyAscensionGoldMultiplier',
     '2025-12-11 由别的效果改为贫穷'),
    (4, 'TightBelt', '药水栏 3 → 2（开局 SubtractFromMaxPotionCount(1)）', 'MegaCrit.Sts2.Core.Entities.Ascension/AscensionManager.cs:56-59；MegaCrit.Sts2.Core.Entities.Players/Player.cs:28',
     '2024-10 首版即有；2025-01 一度被 Warden 替换；2025-12-11 回到 A4'),
    (5, 'AscendersBane', '开局牌组加 1 张「进阶之灾」诅咒（不能打出、虚无、永恒=不可移除，不可升级）', 'MegaCrit.Sts2.Core.Entities.Ascension/AscensionManager.cs:60-65；MegaCrit.Sts2.Core.Models.Cards/AscendersBane.cs',
     '2024-10 首版即有'),
    (6, 'Inflation', '商人删牌基础价 75 → 100，每次涨价 25 → 50', 'MegaCrit.Sts2.Core.Entities.Merchant/MerchantCardRemovalEntry.cs:20-22',
     '2026-04-02 由 Gloom（更少休息处）改为通货膨胀：开发者认为改地图的进阶玩家感知不到'),
    (7, 'Scarcity', '卡牌稀有度：普通战斗稀有 3%→1.49%、普通 60%→61.5%；精英稀有 10%→5%、普通 50%→55%；商店稀有 9%→4.5%、普通 54%→58.5%（普通=1−稀有−罕见的余量；代码里的普通概率常量 0.615/0.549/0.585 从未被掷骰读取，CardRarityOdds.cs:96-133）；稀有保底增长 0.01→0.005；奖励牌升级概率系数 0.25→0.125', 'MegaCrit.Sts2.Core.Odds/CardRarityOdds.cs:13-41；MegaCrit.Sts2.Core.Factories/CardFactory.cs:23',
     '2024-12 加入（A8），2025-12-11 移到 A9，现为 A7；2025-10-30 不再影响药水'),
    (8, 'ToughEnemies', '怪物 HP 上调：156 处 HP 取值，进阶/普通中位数 1.055（+3 HP），区间 1.00-1.24；另有 17 处非 HP 数值（如覆甲、易躲）', 'MegaCrit.Sts2.Core.Models.Monsters/*（101 个文件 173 处），统计脚本 scripts/ch06_ascension_scan.py',
     '2024-10 首版即有（当时 A6）'),
    (9, 'DeadlyEnemies', '怪物伤害/增益上调：227 处，进阶/普通中位数 1.143（+1），区间 1.0-3.0', 'MegaCrit.Sts2.Core.Models.Monsters/*（96 个文件 227 处）',
     '—'),
    (10, 'DoubleBoss', '最后一幕（第 3 幕）在原 Boss 之外再抽 1 个本幕其他 Boss（不重复）', 'MegaCrit.Sts2.Core.Runs/RunManager.cs:769-773',
     '2025-09 Villainy → 2025-11 重做 → 2025-12 Ascender\'s Scorn → 2026-01-15 改为一代回归的双 Boss'),
]
rows = []
for lv, enum, mech, src, hist in A:
    k = f'LEVEL_{lv:02d}'
    rows.append({'level': lv, 'enum': enum, 'title_zh': strip(asc.get(k + '.title')), 'desc_zh': strip(asc.get(k + '.description')),
                 'implementation': mech, 'source': src, 'history_from_patch_notes': hist})
with open(os.path.join(CSV, 'ch06_ascension.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('ascension rows', len(rows))

# ---------------- 成就 ----------------
enum_txt = open(os.path.join(SRC, 'MegaCrit.Sts2.Core.Achievements', 'Achievement.cs'), encoding='utf-8').read()
enum_vals = re.findall(r'(\w+) = (\d+)', enum_txt)
def snake(s):
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', s)
    return s.upper()
WATCH = {
    'CharacterSkillIronclad1': ('一场战斗内消耗 ≥20 张牌', 'MegaCrit.Sts2.Core.Models.Achievements/SkillIronclad1Achievement.cs:26'),
    'CharacterSkillIronclad2': ('单次造成 ≥999 伤害', 'MegaCrit.Sts2.Core.Models.Achievements/SkillIronclad2Achievement.cs'),
    'CharacterSkillSilent1': ('一张牌连锁触发 ≥5 次奇巧弃牌自动打出', 'MegaCrit.Sts2.Core.Models.Achievements/SkillSilent1Achievement.cs:49'),
    'CharacterSkillSilent2': ('单个敌人中毒 ≥99', 'MegaCrit.Sts2.Core.Models.Achievements/SkillSilent2Achievement.cs:24'),
    'CharacterSkillNecrobinder1': ('单个敌人灾厄 ≥999', 'MegaCrit.Sts2.Core.Models.Achievements/SkillNecrobinder1Achievement.cs:24'),
    'CharacterSkillNecrobinder2': ('奥斯提力量 ≥50', 'MegaCrit.Sts2.Core.Models.Achievements/SkillNecrobinder2Achievement.cs:25'),
    'CharacterSkillRegent1': ('君王之剑基础伤害 ≥999', 'MegaCrit.Sts2.Core.Models.Achievements/SkillRegent1Achievement.cs:30'),
    'CharacterSkillRegent2': ('拥有 ≥20 辉星', 'MegaCrit.Sts2.Core.Models.Achievements/SkillRegent2Achievement.cs'),
    'Play20CardsSingleTurn': ('一回合打出 ≥20 张牌', 'MegaCrit.Sts2.Core.Models.Achievements/Play20CardsSingleTurnAchievement.cs:24'),
}
out = []
seen = set()
for name, val in enum_vals:
    key = snake(name)
    key = {'PLAY20_CARDS_SINGLE_TURN': 'PLAY20_CARDS_SINGLE_TURN', 'FLOOR_TEN_THOUSAND': 'FLOOR_TEN_THOUSAND'}.get(key, key)
    if key + '.title' not in ach:
        alt = [k[:-6] for k in ach if k.endswith('.title') and k.replace('_', '')[:-5] == key.replace('_', '')]
        key = alt[0] if alt else key
    seen.add(key)
    cond, src = WATCH.get(name, ('（判定写在 AchievementsHelper，当前为空函数）', 'MegaCrit.Sts2.Core.Achievements/AchievementsHelper.cs'))
    out.append({'kind': '成就', 'id': key, 'enum_value': val, 'title_zh': strip(ach.get(key + '.title')),
                'condition_zh': strip(ach.get(key + '.description')), 'condition_code': cond,
                'tiers': '', 'requires_win': '', 'multiplayer_only': '',
                'status': '枚举在；Unlock() 为空函数（抢先体验禁用）', 'source': src})
for k in ach:
    if k.endswith('.title') and not k.startswith('LOCKED'):
        key = k[:-6]
        if key not in seen:
            out.append({'kind': '成就', 'id': key, 'enum_value': '', 'title_zh': strip(ach[k]),
                        'condition_zh': strip(ach.get(key + '.description')), 'condition_code': '',
                        'tiers': '', 'requires_win': '', 'multiplayer_only': '',
                        'status': '只有本地化文本，枚举里没有（暂时移除）', 'source': 'localization/zhs/achievements.json'})

# ---------------- 徽章 ----------------
B = [
    ('BigDeck', 'BIG_DECK', '牌组张数', '铜≥40 / 银≥60 / 金≥100', True, False),
    ('CccCombo', 'CCCCOMBO', '一回合打出 ≥20 张牌（CccComboModel 战斗中记标记）', '铜', False, False),
    ('Curses', 'CURSES', '牌组诅咒牌 ≥5', '铜', True, False),
    ('DamageLeader', 'DAMAGE_LEADER', '全队造成伤害最多（第 1 幕至少走过 5 个点）', '铜', False, True),
    ('Debuffer', 'DEBUFFER', '全队施加减益次数最多（第 1 幕至少 5 个点；DebufferModel 计数，临时能力不算）', '铜', False, True),
    ('DoubleSnecko', 'DOUBLE_SNECKO', '同时持有异蛇之眼与假异蛇之眼', '铜', False, False),
    ('EliteKiller', 'ELITE', '击杀精英数（死于精英那场不算）', '铜≥3 / 银≥6 / 金≥9', False, False),
    ('Famished', 'FAMISHED', '最大生命 < 角色初始生命的一半（向上取整）', '铜', True, False),
    ('Glutton', 'GLUTTON', '最大生命比初始多', '铜≥15 / 银≥30 / 金≥50', True, False),
    ('Healer', 'HEALER', '休息处选「愈合」（MEND，多人专属）次数', '铜1 / 银2 / 金≥3', False, True),
    ('Highlander', 'HIGHLANDER', '除基础牌外没有重复牌', '铜', True, False),
    ('Honed', 'HONED', '除基础牌外某张牌 ≥5 张', '铜', True, False),
    ('ILikeShiny', 'ILIKESHINY', '遗物 ≥25 件', '铜', False, False),
    ('KaChing', 'KACHING', '在商店累计花费 ≥1000 金币', '铜', False, False),
    ('MoneyMoney', 'MONEY_MONEY', '结算时持有金币', '铜≥200 / 银≥400 / 金≥600', True, False),
    ('MysteryMachine', 'MYSTERY_MACHINE', '走过 ≥15 个 ? 房间', '铜', False, False),
    ('Perfect', 'PERFECT', '无伤击败 Boss 的场数', '铜1 / 银2 / 金≥3', False, False),
    ('Restful', 'RESTFUL', '每个休息处都选了休息（且至少到过 1 个）', '铜', True, False),
    ('Restless', 'RESTLESS', '到过休息处但一次都没休息', '铜', True, False),
    ('Speedy', 'SPEEDY', '通关用时（秒）', '铜≤3000 / 银≤2400 / 金≤1800', True, False),
    ('TabletBadge', 'TABLET', '最大生命恰为 1', '金', True, False),
    ('TeamPlayer', 'TEAM_PLAYER', '牌组中多人专属牌 ≥3', '银', False, True),
    ('TinyDeck', 'TINY_DECK', '牌组张数', '铜≤20 / 银≤10 / 金≤5', True, False),
    ('Whomper', 'WHOMPER', '单次攻击 >100 伤害（常量 100）', '铜', False, False),
]
for cls, bid, cond, tiers, rw, mp in B:
    title = bad.get(bid + '.title') or bad.get(bid + '.bronzeTitle')
    desc = bad.get(bid + '.description') or ' / '.join(strip(bad.get(f'{bid}.{t}Description')) for t in ('bronze', 'silver', 'gold'))
    status = '在 BadgePool（23 个）中' if cls != 'Whomper' else '类存在但 IsObtained() 恒为 false，且不在 BadgePool'
    out.append({'kind': '徽章', 'id': bid, 'enum_value': '', 'title_zh': strip(title), 'condition_zh': strip(desc), 'condition_code': cond,
                'tiers': tiers, 'requires_win': rw, 'multiplayer_only': mp, 'status': status,
                'source': f'MegaCrit.Sts2.Core.Models.Badges/{cls}.cs'})
out.append({'kind': '徽章', 'id': 'FAVORITE_CARD', 'enum_value': '', 'title_zh': strip(bad.get('FAVORITE_CARD.title')),
            'condition_zh': strip(bad.get('FAVORITE_CARD.description')), 'condition_code': '', 'tiers': '', 'requires_win': '',
            'multiplayer_only': '', 'status': '只有本地化文本，无实现', 'source': 'localization/zhs/badges.json'})
with open(os.path.join(CSV, 'ch06_achievements_badges.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
from collections import Counter
print('achievements/badges rows', len(out), Counter((r['kind'], r['status'][:8]) for r in out))
for r in out:
    if not r['title_zh']:
        print('NO TITLE', r['id'])
