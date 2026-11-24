"""第 03 章：遗物 / 药水 / 附魔 的派生表。

输出（data/csv/）：
  ch03_relic_taxonomy.csv      每个遗物一行：稀有度/池/掉落来源/效果分类/标签/价格/限制条件/解锁纪元/引用来源
  ch03_ancient_relics.csv      102 个 Ancient 遗物 × 9 个 Ancient 事件的挂钩（槽位、出现条件、源码行号）
  ch03_potions_detail.csv      65 个药水：稀有度/时机/目标/池/角色/解锁纪元/战斗内可生成/效果分类/商店基础价
  ch03_enchantments_detail.csv 23 个附魔：可附魔条件/叠加/钩子/获取来源
并在 stdout 打印正文要用的统计。

python -I -X utf8 scripts/ch03_relics_potions.py
（在 outputs/sts2_rea_Claude 下跑；只读源码，不碰游戏目录）
"""
import collections, csv, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization')
OUT = os.path.join(ROOT, 'data', 'csv')
P = lambda *a: os.path.join(SRC, *a)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def snake(cls):
    return re.sub(r'(?<=[A-Za-z0-9])([A-Z])', r'_\1', cls).upper()


def strip_tags(s):
    return re.sub(r'\[/?\w+\]', '', s or '').replace('\n', ' ')


def w(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8-sig') as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    print(f'[write] {name}: {len(rows)} rows')


loc_zhs = {t: json.load(open(os.path.join(LOC, 'zhs', t + '.json'), encoding='utf-8')) for t in ('relics', 'potions', 'enchantments')}
loc_eng = {t: json.load(open(os.path.join(LOC, 'eng', t + '.json'), encoding='utf-8')) for t in ('relics', 'potions', 'enchantments')}

# ---------------------------------------------------------------- 全源码引用索引
ALL_FILES = glob.glob(os.path.join(SRC, '*', '*.cs'))
SKIP_DIRS = ('RelicPools', 'PotionPools', 'Timeline.Epochs')


REF_PAT = {
    'Relic': r'(?:Relic|RelicOption|Obtain|FromRelic)<(?:[\w.]+\.)?(\w+)>',
    'Potion': r'(?:Potion|FromPotion)<(?:[\w.]+\.)?(\w+)>',
    'Enchantment': r'(?:Enchantment|Enchant|FromEnchantment)<(?:[\w.]+\.)?(\w+)>',
}
OWN_DIR = {'Relic': 'Relics', 'Potion': 'Potions', 'Enchantment': 'Enchantments'}


def ref_index(kind):
    """kind=Relic/Potion/Enchantment -> {cls: [短文件名...]}（排除池、纪元、ModelDb 注册表、自身文件）"""
    idx = collections.defaultdict(set)
    pat = re.compile(REF_PAT[kind])
    for p in ALL_FILES:
        d = os.path.basename(os.path.dirname(p)).replace('MegaCrit.Sts2.Core.', '')
        if any(s in d for s in SKIP_DIRS) or os.path.basename(p) in ('AbstractModelSubtypes.cs', 'ModelDb.cs'):
            continue
        short = d.split('.')[-1] + '/' + os.path.basename(p)[:-3]
        for c in set(pat.findall(read(p))):
            if short != OWN_DIR[kind] + '/' + c:
                idx[c].add(short)
    return idx


def epoch_index(kind):
    """{cls: EpochName}：Timeline.Epochs 里 ModelDb.Relic<X>() / ModelDb.Potion<X>()"""
    m = {}
    for p in glob.glob(P('MegaCrit.Sts2.Core.Timeline.Epochs', '*.cs')):
        ep = os.path.basename(p)[:-3]
        for c in re.findall(r'ModelDb\.' + kind + r'<(\w+)>\(\)', read(p)):
            m.setdefault(c, ep)
    return m


def pool_index(folder, kind):
    m = collections.defaultdict(list)
    for p in glob.glob(P('MegaCrit.Sts2.Core.Models.' + folder, '*.cs')):
        pool = os.path.basename(p)[:-3].replace(kind + 'Pool', '')
        for c in re.findall(r'ModelDb\.' + kind + r'<(\w+)>\(\)', read(p)):
            if pool not in m[c]:
                m[c].append(pool)
    return m


# ================================================================ 遗物
# 主效果分类（互斥，人工逐条读源码定的）
CAT_DEF = collections.OrderedDict([
    ('pickup', '拾取即生效'),
    ('combat_start', '战斗开始'),
    ('turn', '回合节奏'),
    ('card_play', '打牌/牌堆触发'),
    ('combat_event', '受击/生命/战斗事件'),
    ('combat_end', '战斗结束结算'),
    ('energy', '每回合能量(多带代价)'),
    ('passive', '常驻规则/数值改写'),
    ('run_economy', '经济/奖励/构筑'),
    ('map_rest', '地图/休息处/路线'),
    ('none', '无效果/占位'),
])
CAT = {
    'pickup': """AlchemicalCoffer ArcaneScroll ArchaicTooth Astrolabe BeautifulBracelet BigMushroom BiiigHug Byrdpip CallingBell
        Cauldron Claws CursedPearl DistinguishedCape DollysMirror DowsingRod DustyTome ElectricShrymp EmptyCage FakeLeesWaffle
        FakeMango FragrantMushroom GlassEye GnarledHammer GoldenPearl HeftyTablet JewelryBox Kaleidoscope Kifuda LargeCapsule
        LeadPaperweight LeafyPoultice LeesWaffle LoomingFruit LostCoffer Mango MassiveScroll NeowsBones NeowsSacrifice
        NeowsTalisman NeowsTorment NewLeaf NutritiousOyster NutritiousSoup OldCoin Orrery PaelsClaw PaelsHorn PaelsTooth
        PandorasBox Pear PhialHolster Pomander PotionBelt PrecariousShears PreciseScissors PreservedFog PunchDagger RoyalStamp
        SandCastle ScrollBoxes SeaGlass SereTalon SignetRing SmallCapsule Storybook Strawberry TanxsWhistle TouchOfOrobas
        ToyBox TriBoomerang WarPaint Whetstone YummyCookie""",
    'combat_start': """Akabeko Anchor BagOfMarbles BagOfPreparation Bellows BigHat BloodVial BoneTea BoomingConch BronzeScales
        ChoicesParadox CrackedCore DataDisk DelicateFrond DiamondDiadem DivineDestiny DivineRight EmberTea FakeAnchor
        FakeBloodVial FakeSneckoEye FakeVenerableTeaSet FencingManual FestivePopper FuneraryMask GamblingChip Gorget InfusedCore
        JeweledMask Lantern NinjaScroll OddlySmoothStone OrangeDough Pantograph PetrifiedToad PowerCell RadiantPearl RedMask
        RingOfTheDrake RingOfTheSnake RingingTriangle RoyalPoison RunicCapacitor SlingOfCourage StoneCracker SwordOfJade
        SymbioticVirus TeaOfDiscourtesy Toolbox TwistedFunnel Vajra VenerableTeaSet VeryHotCocoa VexingPuzzlebox""",
    'turn': """ArtOfWar BoundPhylactery Bookmark Brimstone Candelabra CaptainsWheel Chandelier CloakClasp Crossbow EmotionChip
        FakeHappyFlower FakeOrichalcum Fiddle HappyFlower HistoryCourse HornCleat LunarPastry MercuryHourglass MrStruggles
        Orichalcum PaelsBlood PaelsEye PaelsTears ParryingShield Pendulum PhylacteryUnbound PollinousCore Pocketwatch
        RippleBasin Sai ScreamingFlagon SealOfGold SparklingRouge StoneCalendar ToastyMittens""",
    'card_play': """BrilliantScarf BurningSticks CharonsAshes DaughterOfTheWind ForgottenSoul GamePiece HelicalDart
        IntimidatingHelmet IronClub IvoryTile JossPaper Kunai Kusarigama LetterOpener LostWisp MummifiedHand MusicBox Nunchaku
        OrnamentalFan PaelsLegion PenNib Permafrost RainbowRing RazorTooth Regalite Shuriken TheAbacus ThrowingAxe Tingsha
        ToughBandages TuningFork UnceasingTop UnsettlingLamp Vambrace""",
    'combat_event': """BeatingRemnant BeltBuckle BoneFlute BookRepairKnife CentennialPuzzle DemonTongue GalacticDust
        GremlinHorn HandDrill LizardTail Metronome MiniRegent RedSkull ReptileTrinket SelfFormingClay TungstenRod""",
    'combat_end': """BlackBlood BurningBlood ChosenCheese FishingRod MeatOnTheBone SwordOfStone WarHammer
        WongosMysteryTicket""",
    'energy': """BlessedAntler BloodSoakedRose Bread Ectoplasm PaelsFlesh PhilosophersStone PrismaticGem PumpkinCandle Sozu
        SpikedGauntlets VelvetChoker WhisperingEarring""",
    'passive': """ChemicalX FakeStrikeDummy GhostSeed GoldPlatedCables IceCream MiniatureCannon MysticLighter PaperKrane
        PaperPhrog RuinedHelmet RunicPyramid SneckoEye SneckoSkull StrikeDummy SturdyClamp TheBoot UndyingSigil
        VitruvianMinion""",
    'run_economy': """AmethystAubergine BingBong BlackStar BookOfFiveRings BowlerHat DarkstonePeriapt DingyRug DragonFruit
        Driftwood FresnelLens FrozenEgg Glitter LastingCandy LavaLamp LavaRock LordsParasol LuckyFysh MawBank MembershipCard
        MoltenEgg PaelsWing PrayerWheel SilkenTress SilverCrucible TheCourier ToxicEgg WhiteBeastStatue WhiteStar WingCharm""",
    'map_rest': """DreamCatcher EternalFeather FurCoat Girya GoldenCompass JuzuBracelet MealTicket MeatCleaver MiniatureTent
        PaelsGrowth Planisphere RegalPillow Shovel StoneHumidifier TinyMailbox WingedBoots""",
    'none': """Circlet DeprecatedRelic FakeMerchantsRug WongoCustomerAppreciationBadge""",
}
CAT = {k: v.split() for k, v in CAT.items()}

# 有明确代价/副作用（诅咒、扣血扣上限、限制、给敌人加强等）
DRAWBACK = set("""BigMushroom BiiigHug BlessedAntler BloodSoakedRose Bread Brimstone CallingBell CursedPearl DistinguishedCape
    DowsingRod Ectoplasm FakeSneckoEye Fiddle FragrantMushroom HeftyTablet LargeCapsule LeafyPoultice NeowsBones NeowsSacrifice
    PhilosophersStone PrecariousShears PreservedFog PumpkinCandle RoyalPoison SealOfGold SereTalon SilkenTress SilverCrucible
    SneckoEye Sozu SpikedGauntlets TeaOfDiscourtesy ToastyMittens ToyBox VelvetChoker WhisperingEarring""".split())
# 会给牌附魔的遗物
ENCHANTS = set("""BeautifulBracelet ElectricShrymp FresnelLens Glitter GnarledHammer Kifuda NutritiousSoup PaelsClaw PaelsGrowth
    PunchDagger RoyalStamp SilkenTress TriBoomerang WingCharm""".split())
# 角色专属机制关键词（充能球/辉星/奥斯提/灾厄/铸造/小刀/毒…）
CHAR_MECH = {
    'BoundPhylactery': 'Osty召唤', 'PhylacteryUnbound': 'Osty召唤', 'BoneFlute': 'Osty', 'BookRepairKnife': '灾厄',
    'UndyingSigil': '灾厄', 'FuneraryMask': '灵魂牌', 'BigHat': '虚无', 'Bookmark': '保留', 'IvoryTile': '高费',
    'CrackedCore': '充能球', 'InfusedCore': '充能球', 'DataDisk': '集中', 'EmotionChip': '充能球', 'GoldPlatedCables': '充能球',
    'Metronome': '充能球', 'PowerCell': '0费', 'RunicCapacitor': '充能球栏', 'SymbioticVirus': '充能球',
    'DivineRight': '辉星', 'DivineDestiny': '辉星', 'GalacticDust': '辉星', 'LunarPastry': '辉星', 'MiniRegent': '辉星',
    'FencingManual': '铸造', 'Regalite': '生成牌', 'OrangeDough': '无色牌', 'VitruvianMinion': '仆从',
    'HelicalDart': '小刀', 'NinjaScroll': '小刀', 'SneckoSkull': '中毒', 'TwistedFunnel': '中毒', 'Tingsha': '丢弃',
    'ToughBandages': '丢弃', 'PaperKrane': '虚弱', 'RingOfTheSnake': '抽牌', 'RingOfTheDrake': '抽牌',
    'BurningBlood': '回血', 'BlackBlood': '回血', 'CharonsAshes': '消耗', 'DemonTongue': '失去生命', 'PaperPhrog': '易伤',
    'RedSkull': '低血', 'RuinedHelmet': '力量', 'SelfFormingClay': '失去生命', 'Brimstone': '力量',
}
UPGRADED_STARTER = {'BlackBlood': 'Ironclad', 'RingOfTheDrake': 'Silent', 'DivineDestiny': 'Regent',
                    'PhylacteryUnbound': 'Necrobinder', 'InfusedCore': 'Defect'}
DEFAULT_COST = {'Common': 175, 'Uncommon': 225, 'Rare': 275, 'Shop': 200, 'Ancient': 999999999, 'Starter': 999999999,
                'Event': 999999999, 'None': 1}
HOOK_RE = re.compile(r'override\s+(?:async\s+)?[\w<>\[\]?, ]+?\s+(\w+)\(')
CHARS = ['Ironclad', 'Silent', 'Defect', 'Regent', 'Necrobinder']


def parse_relic(src):
    d = {}
    m = re.search(r'RelicRarity Rarity => RelicRarity\.(\w+)', src)
    d['rarity'] = m.group(1) if m else ''
    for f in ['HasUponPickupEffect', 'ShowCounter', 'IsStackable', 'SpawnsPets', 'AddsPet']:
        mm = re.search(r'override bool ' + f + r' => (\w+);', src)
        d[f] = (mm.group(1) == 'true') if mm else (('override bool ' + f) in src and f == 'ShowCounter')
    d['IsUsedUp'] = 'override bool IsUsedUp' in src
    d['NoShop'] = 'override bool IsAllowedInShops => false' in src
    mm = re.search(r'override int MerchantCost => (\d+)', src)
    d['cost_override'] = mm.group(1) if mm else ''
    d['hooks'] = [h for h in dict.fromkeys(HOOK_RE.findall(src))]
    mm = re.search(r'override bool IsAllowed\(IRunState runState\)\s*\{(.*?)\n\t\}', src, re.S)
    body = re.sub(r'\s+', ' ', mm.group(1)) if mm else ''
    if 'IsBeforeAct3TreasureChest' in body and 'Ironclad' in body:
        d['allowed'] = '第3幕宝箱前 且 非铁甲首局'
    elif 'IsBeforeAct3TreasureChest' in body:
        d['allowed'] = '第3幕宝箱前(单人41层/多人38层前)'
    elif 'Players.Count > 1' in body:
        d['allowed'] = '仅多人'
    elif 'Players.Count == 1' in body:
        d['allowed'] = '仅单人'
    else:
        d['allowed'] = body[:80]
    if 'IsAllowedAtNeow' in d['hooks']:
        d['allowed'] = (d['allowed'] + '; ' if d['allowed'] else '') + 'Neow专用条件'
    return d


def relics():
    pools = pool_index('RelicPools', 'Relic')
    epochs = epoch_index('Relic')
    refs = ref_index('Relic')
    base = {r['cls']: r for r in csv.DictReader(open(os.path.join(OUT, 'relics.csv'), encoding='utf-8-sig'))}
    cat_of = {}
    for k, lst in CAT.items():
        for c in lst:
            assert c not in cat_of, ('dup', c)
            cat_of[c] = k
    rows = []
    for p in sorted(glob.glob(P('MegaCrit.Sts2.Core.Models.Relics', '*.cs'))):
        cls = p.split(os.sep)[-1][:-3]
        src = read(p)
        if ': RelicModel' not in src:
            continue  # VakuuCardSelector 不是遗物
        d = parse_relic(src)
        mid = snake(cls)
        pl = pools.get(cls, [])
        char = next((c for c in CHARS if c in pl), UPGRADED_STARTER.get(cls, ''))
        # 掉落来源：RelicGrabBag 只收 Shared + 本角色池 的 Common/Uncommon/Rare/Shop
        rollable = d['rarity'] in ('Common', 'Uncommon', 'Rare', 'Shop') and any(x in pl for x in ['Shared'] + CHARS)
        if rollable:
            drop = '随机池(' + ('角色:' + char if char and 'Shared' not in pl else '共享') + ')'
        elif d['rarity'] == 'Ancient':
            drop = 'Ancient事件'
        elif d['rarity'] == 'Starter':
            drop = '初始遗物' if cls not in UPGRADED_STARTER else '欧洛巴斯之触(初始遗物升级)'
        elif d['rarity'] == 'Event':
            drop = '事件/特定来源'
        else:
            drop = '兜底/弃用'
        tags = []
        if d['HasUponPickupEffect']:
            tags.append('拾取效果标志')
        if d['ShowCounter']:
            tags.append('计数器')
        if d['IsUsedUp']:
            tags.append('可耗尽')
        if d['IsStackable']:
            tags.append('可堆叠')
        if d['SpawnsPets'] or d['AddsPet']:
            tags.append('宠物/召唤')
        if cls in DRAWBACK:
            tags.append('有代价')
        if cls in ENCHANTS:
            tags.append('附魔')
        if 'IsBeforeAct3TreasureChest' in src:
            tags.append('后期不出')
        if cls.startswith('Fake'):
            tags.append('仿制品')
        cost = d['cost_override'] or DEFAULT_COST.get(d['rarity'], '')
        rf = sorted(x for x in refs.get(cls, set()) if not x.startswith('Relics/') or x.split('/')[1] != cls)
        b = base.get(cls, {})
        rows.append(dict(
            id=mid, cls=cls, name_zh=loc_zhs['relics'].get(mid + '.title', ''), name_en=loc_eng['relics'].get(mid + '.title', ''),
            rarity=d['rarity'], pools='|'.join(pl), character=char, drop_source=drop,
            category=cat_of.get(cls, '??'), category_zh=CAT_DEF.get(cat_of.get(cls, ''), '??'),
            tags='|'.join(tags), char_mechanic=CHAR_MECH.get(cls, ''),
            merchant_cost=cost, cost_overridden='Y' if d['cost_override'] else '', shop_allowed='N' if d['NoShop'] else 'Y',
            tradable='N' if (d['HasUponPickupEffect'] or d['IsUsedUp'] or d['SpawnsPets'] or d['rarity'] in ('Starter', 'Event', 'Ancient')) else 'Y',
            allowed_cond=d['allowed'], unlock_epoch=epochs.get(cls, ''), vars=b.get('vars', ''),
            hooks='|'.join(d['hooks']), referenced_by='|'.join(rf),
            desc_zh=strip_tags(loc_zhs['relics'].get(mid + '.description', '')),
            file='MegaCrit.Sts2.Core.Models.Relics/' + cls + '.cs'))
    miss = [r['cls'] for r in rows if r['category'] == '??']
    extra = set(cat_of) - {r['cls'] for r in rows}
    assert not miss and not extra, (miss, extra)
    w('ch03_relic_taxonomy.csv', rows, list(rows[0].keys()))
    return rows


# ---------------------------------------------------------------- Ancient 事件 × 遗物
ANCIENT_SLOTS = {
    # event: [(slot_label, rule, [relics])]
    'Neow': [
        ('正面池', '14 选项进候选，最终与加塞项一起洗牌取 2', 'ArcaneScroll BoomingConch FishingRod GoldenPearl Kaleidoscope LeadPaperweight LostCoffer MassiveScroll NeowsTorment NewLeaf PhialHolster PreciseScissors ScrollBoxes WingedBoots'),
        ('正面加塞A', '二选一(50%)；代价项为巨大扭蛋时不加', 'LavaRock SmallCapsule'),
        ('正面加塞B', '二选一(50%)', 'NutritiousOyster StoneHumidifier'),
        ('正面加塞C', '二选一(50%)', 'NeowsTalisman Pomander'),
        ('代价池', '必出 1 个；与正面项互斥：诅咒珍珠×金色珍珠、沉重石板×奥术卷轴、树叶药膏×新叶、松动羊毛剪×精准剪刀、涅奥的牺牲×药瓶皮套/失物盒', 'CursedPearl DowsingRod HeftyTablet LargeCapsule LeafyPoultice NeowsBones NeowsSacrifice PrecariousShears SilkenTress SilverCrucible'),
    ],
    'Darv': [
        ('单品集', '11 个单品集按条件过滤后，每集出 1 个；50% 取 2 个 + 尘封魔典，50% 取 3 个', 'Astrolabe BlackStar CallingBell EmptyCage PandorasBox RunicPyramid SneckoEye Ectoplasm Sozu PhilosophersStone VelvetChoker'),
        ('尘封魔典', '50% 概率固定占 1 格（给本角色一张非“超越”的先古牌并升级）', 'DustyTome'),
    ],
    'Orobas': [
        ('槽1', '从 [放电异虾, 玻璃眼珠, X] 随机 1；X = 1/3 棱彩宝石，2/3 海玻璃(随机另一个已解锁角色)', 'ElectricShrymp GlassEye PrismaticGem SeaGlass'),
        ('槽2', '4 选 1', 'AlchemicalCoffer Driftwood RadiantPearl SandCastle'),
        ('槽3', '2 选 1；各自要求玩家还持有可升级的初始遗物/初始牌，否则显示锁定', 'TouchOfOrobas ArchaicTooth'),
    ],
    'Pael': [
        ('槽1', '3 选 1', 'PaelsFlesh PaelsHorn PaelsTears'),
        ('槽2', '佩尔之翼 + 条件项(爪:≥3 张可附魔“黏糊”的防御；牙:≥5 张可移除牌) 整表复制一份后再加 1 个增生组织 → 增生组织权重减半', 'PaelsWing PaelsClaw PaelsTooth PaelsGrowth'),
        ('槽3', '眼/血 + 士兵(无事件宠物时) 中 1', 'PaelsEye PaelsBlood PaelsLegion'),
    ],
    'Tanx': [
        ('武器池', '9 个基础 + 三刃回旋镖(≥3 张可附魔“本能”的攻击牌)，洗牌取 3', 'Claws Crossbow IronClub MeatCleaver Sai SpikedGauntlets TanxsWhistle ThrowingAxe WarHammer TriBoomerang'),
    ],
    'Tezcatara': [
        ('槽1', '可可/饼干 + 营养汤(牌组有基础打击时) 中 1', 'VeryHotCocoa YummyCookie NutritiousSoup'),
        ('槽2', '3 选 1', 'BiiigHug Storybook ToastyMittens'),
        ('槽3', '4 选 1', 'GoldenCompass PumpkinCandle ToyBox SealOfGold'),
    ],
    'Vakuu': [
        ('池1', '3 选 1', 'BloodSoakedRose WhisperingEarring Fiddle'),
        ('池2', '3 选 1（原初之爪选项额外标注 -9 最大生命）', 'PreservedFog SereTalon DistinguishedCape'),
        ('池3', '4 选 1', 'ChoicesParadox MusicBox LordsParasol JeweledMask'),
    ],
    'Nonupeipe': [
        ('饰品池', '9 个基础 + 华美手镯(≥4 张可附魔“迅捷”的牌)，洗牌取 3', 'BlessedAntler BrilliantScarf DelicateFrond DiamondDiadem FurCoat Glitter JewelryBox LoomingFruit SignetRing BeautifulBracelet'),
    ],
}
ANCIENT_ACT = {'Neow': '第1幕开局(Index0)', 'Orobas': '第2幕(Hive)', 'Pael': '第2幕(Hive)', 'Tezcatara': '第2幕(Hive)',
               'Nonupeipe': '第3幕(Glory)', 'Tanx': '第3幕(Glory)', 'Vakuu': '第3幕(Glory)', 'Darv': '共享Ancient(ModelDb.AllSharedAncients)'}
DARV_COND = {'PandorasBox': '无“清空牌组”类修饰符', 'Ectoplasm': 'CurrentActIndex==1', 'Sozu': 'CurrentActIndex==1',
             'PhilosophersStone': 'CurrentActIndex>=1', 'VelvetChoker': 'CurrentActIndex>=1'}
POWER_TAG = {  # 人工：强度定位标签
    'energy': '永久+1能量',
}


def ancients(relic_rows):
    by_cls = {r['cls']: r for r in relic_rows}
    ancient_names = json.load(open(os.path.join(LOC, 'zhs', 'ancients.json'), encoding='utf-8'))
    rows, seen = [], collections.Counter()
    for ev, slots in ANCIENT_SLOTS.items():
        src = read(P('MegaCrit.Sts2.Core.Models.Events', ev + '.cs')).split('\n')
        ev_zh = ancient_names.get(snake(ev) + '.title', '')
        for slot, rule, rl in slots:
            for cls in rl.split():
                seen[cls] += 1
                line = next((i + 1 for i, s in enumerate(src) if re.search(r'Relic(Option)?<' + cls + r'>', s)), '')
                r = by_cls[cls]
                tags = r['tags'].split('|') if r['tags'] else []
                rows.append(dict(
                    ancient=ev, ancient_zh=ev_zh, act=ANCIENT_ACT[ev], slot=slot, slot_rule=rule,
                    condition=DARV_COND.get(cls, '') if ev == 'Darv' else '',
                    relic=cls, name_zh=r['name_zh'], rarity=r['rarity'], pools=r['pools'],
                    category_zh=r['category_zh'], drawback='Y' if '有代价' in tags else '',
                    energy_plus1='Y' if r['category'] == 'energy' else '', enchant='Y' if '附魔' in tags else '',
                    desc_zh=r['desc_zh'], src=f'MegaCrit.Sts2.Core.Models.Events/{ev}.cs:{line}'))
    anc = {r['cls'] for r in relic_rows if r['rarity'] == 'Ancient'}
    mapped = set(seen)
    print('[ancient] Ancient-rarity relics:', len(anc), ' mapped:', len(mapped), ' rows:', len(rows))
    print('  ancient but unmapped:', sorted(anc - mapped))
    print('  mapped but not Ancient rarity:', sorted(mapped - anc))
    print('  mapped twice:', [k for k, v in seen.items() if v > 1])
    w('ch03_ancient_relics.csv', rows, list(rows[0].keys()))
    return rows


# ================================================================ 药水
POT_CAT = {
    '伤害': 'ExplosiveAmpoule FirePotion PotionShapedRock FoulPotion PowderedDemise PoisonPotion PotionOfDoom',
    '减益敌人': 'VulnerablePotion WeakPotion PotionOfBinding ShacklingPotion BeetleJuice',
    '防御': 'BlockPotion Fortifier HeartOfIron LiquidBronze ShipInABottle GhostInAJar LuckyTonic',
    '力量/敏捷': 'StrengthPotion DexterityPotion FlexPotion SpeedPotion FyshOil MazalethsGift GigantificationPotion',
    '能量/抽牌/操控': 'EnergyPotion SwiftPotion CureAll Clarity RadiantTincture BottledPotential GamblersBrew SneckoOil GlowwaterPotion StableSerum Ashwater DropletOfPrecognition LiquidMemories Duplicator DistilledChaos TouchOfInsanity BlessingOfTheForge',
    '生成卡牌': 'AttackPotion SkillPotion PowerPotion ColorlessPotion OrobicAcid CosmicConcoction CunningPotion PotOfGhouls',
    '生命': 'BloodPotion FruitJuice RegenPotion FairyInABottle Ambergris',
    '角色资源': 'FocusPotion EssenceOfDarkness PotionOfCapacity StarPotion KingsCourage BoneBrew SoldiersStew',
    '药水栏': 'EntropicBrew',
    '弃用': 'DeprecatedPotion',
}
POT_COST = {'Rare': 100, 'Uncommon': 75}


def potions():
    pools = pool_index('PotionPools', 'Potion')
    epochs = epoch_index('Potion')
    refs = ref_index('Potion')
    base = {r['cls']: r for r in csv.DictReader(open(os.path.join(OUT, 'potions.csv'), encoding='utf-8-sig'))}
    char_of = {}
    for ch in CHARS:
        for c in re.findall(r'ModelDb\.Potion<(\w+)>\(\)', read(P('MegaCrit.Sts2.Core.Timeline.Epochs', ch + '4Epoch.cs'))):
            char_of[c] = ch
    cat_of = {c: k for k, v in POT_CAT.items() for c in v.split()}
    rows = []
    for p in sorted(glob.glob(P('MegaCrit.Sts2.Core.Models.Potions', '*.cs'))):
        cls = p.split(os.sep)[-1][:-3]
        src = read(p)
        mid = snake(cls)
        g = lambda pat: (re.search(pat, src).group(1) if re.search(pat, src) else '')
        tgt = g(r'TargetType TargetType => TargetType\.(\w+)') or ('动态:战斗中AllEnemies/否则TargetedNoCreature' if cls == 'FoulPotion' else '')
        pl = pools.get(cls, [])
        ch = char_of.get(cls, '')
        pool = ('角色:' + ch) if ch else '|'.join(pl)
        rar = g(r'PotionRarity Rarity => PotionRarity\.(\w+)')
        rows.append(dict(
            id=mid, cls=cls, name_zh=loc_zhs['potions'].get(mid + '.title', ''), name_en=loc_eng['potions'].get(mid + '.title', ''),
            rarity=rar, usage=g(r'PotionUsage Usage => PotionUsage\.(\w+)'), target=tgt, pool=pool, character=ch,
            unlock_epoch=epochs.get(cls, ''), in_combat_generatable='N' if 'CanBeGeneratedInCombat => false' in src else 'Y',
            custom_usability='Y' if 'PassesCustomUsabilityCheck' in src else '',
            category=cat_of.get(cls, '??'), shop_base_cost=POT_COST.get(rar, 50) if rar in ('Common', 'Uncommon', 'Rare') else '',
            vars=base.get(cls, {}).get('vars', ''), referenced_by='|'.join(sorted(refs.get(cls, set()))),
            desc_zh=strip_tags(loc_zhs['potions'].get(mid + '.description', '')),
            file='MegaCrit.Sts2.Core.Models.Potions/' + cls + '.cs'))
    assert all(r['category'] != '??' for r in rows), [r['cls'] for r in rows if r['category'] == '??']
    w('ch03_potions_detail.csv', rows, list(rows[0].keys()))
    return rows


# ================================================================ 附魔
ENCH_RULE = {  # 人工读 CanEnchant / CanEnchantCardType 得出
    'Adroit': '任意(非状态/诅咒/任务、牌组中非不能打出)', 'Clone': '任意', 'Corrupted': '仅攻击', 'Glam': '任意',
    'Goopy': '带“防御”标签', 'Imbued': '仅技能', 'Inky': '任意', 'Instinct': '仅攻击', 'Momentum': '仅攻击',
    'Nimble': '会获得格挡的牌', 'PerfectFit': '任意', 'RoyallyApproved': '攻击或技能', 'Sharp': '仅攻击',
    'Slither': '非X费、非不能打出', 'SlumberingEssence': '任意', 'SoulsPower': '自带“消耗”的牌', 'Sown': '任意',
    'Spiral': '基础稀有度的打击/防御', 'Steady': '任意', 'Swift': '任意', 'TezcatarasEmber': '任意(营养汤只挑基础打击)',
    'Vigorous': '仅攻击', 'DeprecatedEnchantment': '-'}
ENCH_KIND = {
    'Adroit': '打出时追加效果', 'Inky': '打出时追加效果', 'Corrupted': '数值倍率(+代价)', 'Instinct': '数值倍率',
    'Sharp': '数值加成', 'Nimble': '数值加成', 'Vigorous': '首次打出加成', 'Momentum': '成长(战斗内)', 'Goopy': '成长(永久)',
    'Glam': '重放', 'Spiral': '重放', 'Swift': '首次打出加成', 'Sown': '首次打出加成', 'Imbued': '开局自动打出',
    'PerfectFit': '牌序操控', 'Slither': '费用随机', 'SlumberingEssence': '费用递减', 'TezcatarasEmber': '改费用+关键词',
    'RoyallyApproved': '加关键词', 'Steady': '加关键词', 'SoulsPower': '去关键词', 'Clone': '标记(休息处复制)',
    'DeprecatedEnchantment': '弃用'}


def enchantments():
    refs = ref_index('Enchantment')
    rows = []
    for p in sorted(glob.glob(P('MegaCrit.Sts2.Core.Models.Enchantments', '*.cs'))):
        cls = p.split(os.sep)[-1][:-3]
        src = read(p)
        mid = snake(cls)
        hooks = [h for h in dict.fromkeys(HOOK_RE.findall(src)) if h not in ('CanEnchant', 'CanEnchantCardType')]
        rf = sorted(x for x in refs.get(cls, set()) if not x.startswith('Enchantments/'))
        rows.append(dict(
            id=mid, cls=cls, name_zh=loc_zhs['enchantments'].get(mid + '.title', ''), name_en=loc_eng['enchantments'].get(mid + '.title', ''),
            can_enchant=ENCH_RULE.get(cls, ''), kind=ENCH_KIND.get(cls, ''),
            stackable='Y' if 'IsStackable => true' in src else '', show_amount='Y' if 'ShowAmount => true' in src else '',
            hooks='|'.join(hooks), sources='|'.join(rf),
            desc_zh=strip_tags(loc_zhs['enchantments'].get(mid + '.description', '')),
            file='MegaCrit.Sts2.Core.Models.Enchantments/' + cls + '.cs'))
    w('ch03_enchantments_detail.csv', rows, list(rows[0].keys()))
    return rows


# ================================================================ 统计输出
def stats(rr, pr):
    print('\n== relic rarity x pool (按 pools 首项；多池单列)')
    real = [r for r in rr]
    c = collections.Counter()
    for r in real:
        c[(r['rarity'], r['pools'])] += 1
    for k, v in sorted(c.items()):
        print('  ', k, v)
    print('rarity:', collections.Counter(r['rarity'] for r in real))
    print('drop_source:', collections.Counter(r['drop_source'] for r in real))
    print('category:', collections.Counter(r['category_zh'] for r in real))
    print('category x rarity:')
    cr = collections.Counter((r['category_zh'], r['rarity']) for r in real)
    rars = ['Starter', 'Common', 'Uncommon', 'Rare', 'Shop', 'Event', 'Ancient', 'None']
    print('   ' + '\t'.join(rars))
    for k in CAT_DEF.values():
        print('  ', k, '\t'.join(str(cr[(k, x)]) for x in rars))
    tagc = collections.Counter(t for r in real for t in r['tags'].split('|') if t)
    print('tags:', tagc)
    print('cost overridden:', [(r['cls'], r['merchant_cost']) for r in real if r['cost_overridden']])
    print('no shop:', [(r['cls'], r['rarity']) for r in real if r['shop_allowed'] == 'N'])
    print('allowed cond:', collections.Counter(r['allowed_cond'] for r in real if r['allowed_cond']))
    print('late-gated:', [r['cls'] for r in real if '后期不出' in r['tags']])
    print('epoch-locked relics:', collections.Counter(r['unlock_epoch'] for r in real if r['unlock_epoch']))
    rollable = [r for r in real if r['drop_source'].startswith('随机池')]
    print('rollable per char (shared+own):', len([r for r in rollable if r['character'] == '']),
          {ch: len([r for r in rollable if r['character'] == ch]) for ch in CHARS})
    print('rollable shared by rarity:', collections.Counter(r['rarity'] for r in rollable if r['character'] == ''))
    print('char pools by rarity:', collections.Counter((r['character'], r['rarity']) for r in rollable if r['character']))
    print('\n== potions')
    print('rarity:', collections.Counter(r['rarity'] for r in pr))
    print('usage:', collections.Counter(r['usage'] for r in pr))
    print('target:', collections.Counter(r['target'] for r in pr))
    print('pool:', collections.Counter(r['pool'] for r in pr))
    print('category:', collections.Counter(r['category'] for r in pr))
    print('rarity x pool:', collections.Counter((r['rarity'], r['pool'].split(':')[0]) for r in pr))
    print('not in-combat generatable:', [r['cls'] for r in pr if r['in_combat_generatable'] == 'N'])
    print('epoch:', collections.Counter(r['unlock_epoch'] for r in pr if r['unlock_epoch']))


if __name__ == '__main__':
    rr = relics()
    ancients(rr)
    pr = potions()
    enchantments()
    stats(rr, pr)
