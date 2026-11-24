"""第 05 章：概率常量表 + 商店定价表 + 几个派生量的计算/模拟

python -I -X utf8 scripts/ch05_build_tables.py
产出 data/csv/ch05_odds.csv、data/csv/ch05_shop_prices.csv，并把派生量打印到 stdout（正文引用的数字出自这里）。

常量全部手抄自源码（每行带出处，相对 csharp/sts2_src/），派生量用 Python 按源码逻辑复算：
  - NextGaussianInt 的离散分布：按正态 CDF 精确计算（Rng.cs:262 的拒绝采样 = 截断后归一化）
  - 未知房、卡牌稀有度保底、药水掉率：蒙特卡洛（Python random，非游戏 RNG）
"""
import csv
import math
import os
import random
import statistics
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'data', 'csv')

O = 'MegaCrit.Sts2.Core.Odds/'
ODDS = [
    # system, key, normal, ascension_value, ascension_level, note, src
    ('卡牌稀有度', '普通战斗 稀有基础概率', 0.03, 0.0149, 'A7 Scarcity 稀缺', '另加保底偏移 offset', O + 'CardRarityOdds.cs:33'),
    ('卡牌稀有度', '普通战斗 罕见概率', 0.37, '', '', '罕见区间从「稀有+offset」起算，稀有+offset<0 时罕见同样被吃掉（offset=-5% 时罕见只有 35%）；普通 = 剩余', O + 'CardRarityOdds.cs:15,99-110'),
    ('卡牌稀有度', '精英战斗 稀有基础概率', 0.10, 0.05, 'A7 Scarcity 稀缺', '另加 offset', O + 'CardRarityOdds.cs:37'),
    ('卡牌稀有度', '精英战斗 罕见概率', 0.40, '', '', '', O + 'CardRarityOdds.cs:17'),
    ('卡牌稀有度', 'Boss 战斗 稀有概率', 1.0, '', '', 'Roll 时 offset 强制按 0 计；抽到稀有后照样把 offset 重置', O + 'CardRarityOdds.cs:19-23,71'),
    ('卡牌稀有度', '商店 稀有概率', 0.09, 0.045, 'A7 Scarcity 稀缺', '商店用 RollWithoutChangingFutureOdds：读 offset 但不改它', O + 'CardRarityOdds.cs:41; Factories/CardFactory.cs:CreateForMerchant'),
    ('卡牌稀有度', '商店 罕见概率', 0.37, '', '', '', O + 'CardRarityOdds.cs:25'),
    ('卡牌稀有度', '保底 offset 初值', -0.05, '', '', '每局开局、每次出稀有后回到 -5%', O + 'CardRarityOdds.cs:27,47,74'),
    ('卡牌稀有度', '保底 offset 每次未出稀有的增量', 0.01, 0.005, 'A7 Scarcity 稀缺', '普通/罕见都 +1%（不是只算普通）', O + 'CardRarityOdds.cs:31,78'),
    ('卡牌稀有度', '保底 offset 上限', 0.40, '', '', '', O + 'CardRarityOdds.cs:29'),
    ('卡牌稀有度', '会推进保底的来源', '', '', '', '仅 Source=Encounter 且 Odds∈{普通,精英,Boss}，或带 ForceRarityOddsChange（SealedDeck 修饰符）；用 CardCreationOptions.ForRoom 生成奖励的遗物（捕梦网/转经轮/白星）来源也算 Encounter，同样读写 offset；其余事件/遗物给的卡走 RollWithBaseOdds 不读不写 offset', 'Factories/CardFactory.cs:246-262; Runs/CardCreationOptions.cs:81-90; Models.Relics/DreamCatcher.cs:22; PrayerWheel.cs:24; WhiteStar.cs:29'),
    ('卡牌升级', '战斗奖励卡（非稀有）预升级概率', '幕序号×0.25', '幕序号×0.125', 'A7 Scarcity 稀缺', '第1幕 0%/第2幕 25%/第3幕 50%；稀有卡不吃这条', 'Factories/CardFactory.cs:23,RollForUpgrade'),
    ('卡牌升级', '商店卡预升级概率', '基础 -999999999', '', '', '等于不会预升级，除非有 Hook 改', 'Factories/CardFactory.cs:CreateForMerchant'),
    ('卡牌升级', '事件给卡', '不 roll', '', '', 'ForNonCombatWithDefaultOdds 带 NoUpgradeRoll', 'Runs/CardCreationOptions.cs:116'),
    ('未知房', '敌人 基础/增量', 0.10, '', '', '没抽中的类型每次 + 自身基础值', O + 'UnknownMapPointOdds.cs:21'),
    ('未知房', '宝箱 基础/增量', 0.02, '', '', 'DeadlyEvents 修饰符下宝箱增量×2', O + 'UnknownMapPointOdds.cs:25'),
    ('未知房', '商店 基础/增量', 0.03, '', '', '上一房是商店、或下一层全是商店时本次排除商店', O + 'UnknownMapPointOdds.cs:27; Runs/RunManager.cs:668'),
    ('未知房', '精英 基础', -1, 0.10, '修饰符 DeadlyEvents', '负数=永不出且不增长', O + 'UnknownMapPointOdds.cs:23; Models.Modifiers/DeadlyEvents.cs:18'),
    ('未知房', '事件', '1-其余正值之和', '', '', '抽中的类型重置到基础值；每幕开始全部重置', O + 'UnknownMapPointOdds.cs:96; Runs/RunManager.cs:1393'),
    ('未知房', '首局教学', '前 2 个 ? 必为事件，第 3 个必为敌人', '', '', 'NumberOfRuns==0', O + 'UnknownMapPointOdds.cs:125-136'),
    ('药水掉落', '初值', 0.40, '', '', '每名玩家一份，跨幕不重置', O + 'PotionRewardOdds.cs:19'),
    ('药水掉落', '掉了 / 没掉', '-0.10 / +0.10', '', '', '无上下限钳制', O + 'PotionRewardOdds.cs:67-72'),
    ('药水掉落', '精英加成', '0.25×0.5 = +12.5%', '', '', '常量叫 eliteBonus=0.25，代码里又乘了 0.5', O + 'PotionRewardOdds.cs:17,63'),
    ('药水掉落', '设计目标', 0.50, '', '', 'targetOdds 常量只是注释用，代码未引用；全普通战斗时 ±10% 生灭链的平稳态掉率恰好 50%（从 40% 起步，前 40 场平均 48.8%）', O + 'PotionRewardOdds.cs:15'),
    ('药水稀有度', '稀有 / 罕见 / 普通', '10% / 25% / 65%', '', '', '奖励与商店共用', 'Factories/PotionFactory.cs:13-19,83'),
    ('遗物稀有度', '普通 / 罕见 / 稀有', '50% / 33% / 17%', '', '', '精英、宝箱、商店前两格共用 RollRarity', 'Factories/RelicFactory.cs:RollRarity'),
    ('金币', '普通战斗', '10–20', '7–15', 'A3 Poverty 贫穷(×0.75)', '×(1-逃跑敌人数/出场敌人数)', 'Models/EncounterModel.cs:64-99,369'),
    ('金币', '精英战斗', '35–45', '26–33', 'Poverty', '', 'Models/EncounterModel.cs:71,90'),
    ('金币', 'Boss 战斗', 100, 75, 'Poverty', '最后一幕 Boss 不给任何奖励', 'Models/EncounterModel.cs:72,91; Rewards/RewardsSet.cs:WithRewardsFromRoom'),
    ('金币', '宝箱房', '42–52', '31–39', 'Poverty', 'NextInt(42,53)', 'Multiplayer.Game/OneOffSynchronizer.cs:132-136'),
    ('金币', '首局铁甲 教学战斗', '10–20', '', '', '前 7 场普通战斗奖励写死', 'Rewards/RewardsSet.cs:TryGenerateTutorialRewards'),
    ('营火', '休息 回复', '最大HP×30%', '', '', '', 'Entities.RestSite/HealRestSiteOption.cs:92'),
    ('营火', '锻造 升级张数', 1, '', '', 'SmithCount 可被遗物改', 'Entities.RestSite/SmithRestSiteOption.cs:29'),
    ('营火', '愈合（仅多人）', '队友最大HP×30%', '', '', '', 'Entities.RestSite/MendRestSiteOption.cs:56'),
    ('先古之民', '进场回血', '回满', '回缺失量的 80%', 'A2 WearyTraveler 旅途劳顿', '涅奥先把 HP 置 0 再回，所以进阶下开局只有 80% HP', 'Models/AncientEventModel.cs:BeforeEventStarted'),
    ('地图', '精英数', 5, 8, 'A1 SwarmingElites 精英蜂拥(×1.6 四舍五入)', '', 'Map/MapPointTypeCounts.cs:15'),
    ('地图', '商店数', 3, '', '', '', 'Map/MapPointTypeCounts.cs:18'),
    ('地图', '未知数', 'Gauss(12,1)∈[10,14]', '', '', '第2/3幕再 -1', 'Map/MapPointTypeCounts.cs:34; Models.Acts/*.cs'),
    ('地图', '休息处数（不含 Boss 前一排）', '第1幕 Gauss(7,1)∈[6,7]；第2幕 Gauss(6,1)∈[6,7]；第3幕 NextInt(5,7)=5或6', '', '', '', 'Models.Acts/Overgrowth.cs:136; Hive.cs:119; Glory.cs:108'),
]

S = 'MegaCrit.Sts2.Core.Entities.Merchant/'
SHOP = [
    # slot, count, how rolled, base price, multiplier, special, src
    ('角色卡（攻击）', 2, '稀有度按商店概率 54/37/9（读保底 offset 不改）', '普通50/罕见75/稀有150', '×U(0.95,1.05) 取整', '5 张角色卡里随机 1 张半价（整数除 2）', S + 'MerchantInventory.cs:15-22,PopulateCharacterCardEntries; MerchantCardEntry.cs:GetCost,CalcCost'),
    ('角色卡（技能）', 2, '同上', '同上', '同上', '同上', S + 'MerchantInventory.cs'),
    ('角色卡（能力）', 1, '同上；5 个角色都没有普通能力牌，抽到普通按 GetNextAllowedRarity 顺延成罕见，实际 罕见91/稀有9', '罕见75/稀有150', '同上', '同上', S + 'MerchantInventory.cs; Factories/CardFactory.cs:50-51'),
    ('无色卡', 2, '固定 1 罕见 + 1 稀有', '罕见 86 / 稀有 172（=75/150×1.15 RoundToInt）', '×U(0.95,1.05)', '不参与半价', S + 'MerchantInventory.cs:24-28; MerchantCardEntry.cs:48'),
    ('遗物', 2, '遗物稀有度 50/33/17，从遗物袋「尾部」抽（奖励从头部抽）', '普通175/罕见225/稀有275', '×U(0.85,1.15) 四舍五入', '只抽 IsAllowedInShops 的', S + 'MerchantInventory.cs:PopulateRelicEntries; MerchantRelicEntry.cs:CalcCost; Models/RelicModel.cs:305'),
    ('遗物（商店专属）', 1, '固定 Shop 稀有度', 200, '×U(0.85,1.15)', 'Shop 袋空了依次降级到 普通→罕见→稀有', S + 'MerchantInventory.cs; Runs/RelicGrabBag.cs:GetAvailableDeque'),
    ('药水', 3, '药水稀有度 65/25/10', '普通50/罕见75/稀有100', '×U(0.95,1.05)', '', S + 'MerchantPotionEntry.cs:GetCost,CalcCost'),
    ('删牌服务', 1, '每家店限 1 次', '75 + 25×本局已删次数', '无随机', '进阶 A6 通货膨胀：100 + 50×次数', S + 'MerchantCardRemovalEntry.cs:20-33'),
    ('折扣：会员卡 MembershipCard', '', '', '', '×0.50', '所有商品（含删牌）', 'MegaCrit.Sts2.Core.Models.Relics/MembershipCard.cs'),
    ('折扣：送货员 TheCourier', '', '', '', '×0.80', '买完的格子立即补货', 'MegaCrit.Sts2.Core.Models.Relics/TheCourier.cs'),
    ('事件：假商人 FakeMerchant', 6, '9 件仿冒遗物洗牌取 6', 50, '', '向他扔「恶臭药水」开战，赢了拿全部未售仿品+商人的地毯', 'MegaCrit.Sts2.Core.Models.Events/FakeMerchant.cs'),
]


def write(name, header, rows):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def gauss_int_dist(mean, sd, lo, hi):
    raw = {k: phi((k + 0.5 - mean) / sd) - phi((k - 0.5 - mean) / sd) for k in range(lo, hi + 1)}
    tot = sum(raw.values())
    return {k: v / tot for k, v in raw.items()}


def sim_unknown(n_rooms=14, trials=200000, seed=1):
    """一幕内连续 n 个未知房，第 k 个的结果分布（不含商店排除规则）。"""
    rng = random.Random(seed)
    base = {'敌人': 0.10, '宝箱': 0.02, '商店': 0.03}
    per_k = [Counter() for _ in range(n_rooms)]
    for _ in range(trials):
        cur = dict(base)
        for k in range(n_rooms):
            r = rng.random()
            acc = 0
            res = '事件'
            for t in ('敌人', '宝箱', '商店'):   # Dictionary 插入序 Monster, Elite(负数跳过), Treasure, Shop
                acc += cur[t]
                if r <= acc:
                    res = t
                    break
            for t in base:
                cur[t] = base[t] if t == res else cur[t] + base[t]
            per_k[k][res] += 1
    return [{t: c[t] / trials for t in ('事件', '敌人', '宝箱', '商店')} for c in per_k]


def sim_rarity(kind, rewards=3000, trials=300, seed=2, scarcity=False):
    rng = random.Random(seed)
    rare_base = {'regular': 0.0149 if scarcity else 0.03, 'elite': 0.05 if scarcity else 0.10}[kind]
    unc = {'regular': 0.37, 'elite': 0.40}[kind]
    growth = 0.005 if scarcity else 0.01
    rare_cards = 0
    cards = 0
    rewards_with_rare = 0
    gaps = []
    for _ in range(trials):
        off = -0.05
        since = 0
        for _ in range(rewards):
            got = False
            for _ in range(3):
                r = rng.random()
                cards += 1
                since += 1
                if r < rare_base + off:
                    rare_cards += 1
                    got = True
                    gaps.append(since)
                    since = 0
                    off = -0.05
                else:
                    off = min(off + growth, 0.40)
            rewards_with_rare += got
    return rare_cards / cards, rewards_with_rare / (rewards * trials), statistics.mean(gaps)


def sim_potion(seq, trials=20000, seed=3):
    rng = random.Random(seed)
    got = Counter()
    seen = Counter()
    for _ in range(trials):
        v = 0.4
        for room in seq:
            bonus = 0.25 * 0.5 if room == 'E' else 0
            seen[room] += 1
            if rng.random() < v + bonus:
                v -= 0.1
                got[room] += 1
            else:
                v += 0.1
    return {k: got[k] / seen[k] for k in seen}


def potion_stationary():
    """全普通战斗：掉率 v∈{0,0.1,...,1}，掉了 v-0.1、没掉 v+0.1 的生灭链，精确求平稳态掉率。"""
    vals = [i / 10 for i in range(11)]
    pi = [1.0]
    for i in range(10):
        pi.append(pi[-1] * (1 - vals[i]) / vals[i + 1])
    s = sum(pi)
    return sum(p * v for p, v in zip(pi, vals)) / s


def shop_expect():
    card = 0.54 * 50 + 0.37 * 75 + 0.09 * 150            # 攻击/技能格（名义赔率，offset 按 0）
    power = 0.91 * 75 + 0.09 * 150                         # 能力格：没有普通能力牌，普通顺延成罕见
    relic_rand = 0.5 * 175 + 0.33 * 225 + 0.17 * 275
    potion = 0.65 * 50 + 0.25 * 75 + 0.10 * 100
    cards_full = 4 * card + power
    total = cards_full - cards_full / 5 / 2 + 86 + 172 + 2 * relic_rand + 200 + 3 * potion
    return card, power, relic_rand, potion, total


if __name__ == '__main__':
    write('ch05_odds.csv', ['system', 'key', 'value_normal', 'value_ascension', 'ascension_or_modifier', 'note', 'src'], ODDS)
    write('ch05_shop_prices.csv', ['slot', 'count', 'roll_rule', 'base_price', 'multiplier', 'special', 'src'], SHOP)
    print('odds rows', len(ODDS), 'shop rows', len(SHOP))

    print('\n== NextGaussianInt 离散分布')
    for label, args in [('未知 Gauss(12,1)[10,14]', (12, 1, 10, 14)), ('第1幕休息 Gauss(7,1)[6,7]', (7, 1, 6, 7)), ('第2幕休息 Gauss(6,1)[6,7]', (6, 1, 6, 7))]:
        d = gauss_int_dist(*args)
        print(label, {k: f'{v:.1%}' for k, v in d.items()}, '期望', round(sum(k * v for k, v in d.items()), 2))

    print('\n== 未知房：一幕内第 k 个 ? 的结果分布')
    res = sim_unknown()
    for k, d in enumerate(res[:8], 1):
        print(k, {t: f'{v:.1%}' for t, v in d.items()})
    tot = Counter()
    for d in res[:4]:
        for t, v in d.items():
            tot[t] += v
    print('前4个?合计期望', {t: round(v, 2) for t, v in tot.items()})

    print('\n== 卡牌稀有度保底（每份奖励 3 张，全程同一类战斗）')
    for kind in ('regular', 'elite'):
        for sc in (False, True):
            rate, per_reward, gap = sim_rarity(kind, scarcity=sc)
            print(kind, '进阶Scarcity' if sc else '普通', f'每张卡稀有率 {rate:.2%}  每份奖励至少1稀有 {per_reward:.1%}  平均每 {gap:.1f} 张出1稀有')

    print('\n== 药水掉率')
    print(f'全普通战斗 平稳态（精确）{potion_stationary():.4f}')
    print('全普通战斗 前40场（从40%起步）', sim_potion('M' * 40))
    print('普通:精英 4:1 交替 前40场', sim_potion('MMMME' * 8))

    c, pw, r, p, t = shop_expect()
    print('\n== 商店期望价（不计 ±5%/±15% 随机；名义商店赔率，offset 按 0）')
    print(f'攻击/技能卡均价 {c:.2f}  能力卡均价 {pw:.2f}  随机稀有度遗物均价 {r:.1f}  药水均价 {p:.2f}  全店清空约 {t:.0f}（不含删牌）')
