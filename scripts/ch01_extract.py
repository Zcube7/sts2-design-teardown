# -*- coding: utf-8 -*-
"""第 01 章（战斗内核）抽表脚本。

产出（相对项目根）:
  data/csv/ch01_hooks.csv            Hook.cs 里全部 public static 时点：类型/派发范围/轮次/调用点数/被重写次数
  data/csv/ch01_power_taxonomy.csv   268 个能力：Buff/Debuff、叠加类型、实例化方式、衰减方式、功能标签、来源分布
  data/csv/ch01_intents.csv          意图类型：类、本地化名、怪物里的使用次数与示例

用法: python -I -X utf8 scripts/ch01_extract.py  （在项目根目录或任意目录均可）
纯正则静态抽取，复杂写法（多行 getter、条件分支）会在 note 列标出，需回源码核对。
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "csharp", "sts2_src")
OUT = os.path.join(ROOT, "data", "csv")
LOC = os.path.join(ROOT, "data", "pck_text", "localization", "zhs")


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def rel(path):
    return os.path.relpath(path, SRC).replace("\\", "/")


def all_cs():
    for d, _, files in os.walk(SRC):
        for fn in files:
            if fn.endswith(".cs"):
                yield os.path.join(d, fn)


ALL_FILES = list(all_cs())
FILE_TEXT = {p: read(p) for p in ALL_FILES}


# ---------------------------------------------------------------- hooks
def split_methods(text, start_pat):
    """按 start_pat 切出方法块，返回 [(name, line_no, sig, body)]."""
    lines = text.split("\n")
    idx = [i for i, l in enumerate(lines) if re.match(start_pat, l)]
    out = []
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(lines)
        # 方法块到下一个 /// <summary> 之前为止，避免吞进下一个方法的注释
        body_lines = lines[i:j]
        sig = lines[i].strip()
        m = re.search(r"\b(\w+)\s*(?:<[^>]*>)?\(", sig)
        name = m.group(1) if m else "?"
        out.append((name, i + 1, sig, "\n".join(body_lines)))
    return out


HOOK_PHASE = [
    # (关键字, 时点大类) —— 按顺序匹配
    (r"CombatStart|CombatEnd|CombatVictory|CombatReward|ShouldStopCombatFromEnding", "战斗开始/结束"),
    (r"SideTurn|PlayerTurnStart|AutoPrePlay|AutoPostPlay|EnergyReset|HandDraw|Flush|ExtraTurn|BlockCleared|PreventingBlockClear|ShouldClearBlock|ShouldPlayerResetEnergy|ShouldTakeExtraTurn", "回合流程"),
    (r"CardPlayed|CardAutoPlayed|CardPlayCount|CardPlayResultLocation|ShouldPlay$|EnergySpent|StarsSpent|XValue|EnergyCost|StarCost|Keywords|Ethereal|PayExcess", "出牌与费用"),
    (r"CardDrawn|Draw|Shuffle|Discarded|Exhausted|CardEnteredCombat|CardGenerated|HandEmptied|CardChangedPiles|Afflict", "牌堆流转"),
    (r"Damage|Attack|HpLost|Block|Hitting|Targeting|CurrentHp", "伤害与格挡"),
    (r"Power", "能力"),
    (r"Death|Die|Doom|Revive|Osty|Summon|Removed|CreatureAdded", "死亡/召唤"),
    (r"Orb|Forge|Stars|EnergyGain|MaxEnergy", "角色资源"),
    (r"Potion", "药水"),
    (r"Map|Room|Act|Unknown|Treasure|FreeTravel|ProceedToNextMapPoint|Ancient|Event", "地图/房间"),
    (r"Reward|Merchant|Item|Gold|Deck|CardRemoved|RestSite|Upgrade", "奖励/商店/营火/牌组"),
]


def hook_phase(name):
    for pat, cat in HOOK_PHASE:
        if re.search(pat, name):
            return cat
    return "其他"


def build_hooks():
    hook_path = os.path.join(SRC, "MegaCrit.Sts2.Core.Hooks", "Hook.cs")
    text = read(hook_path)
    methods = split_methods(text, r"^\t(?:public|private) static ")
    # 调用点统计
    callers = defaultdict(Counter)
    for p, t in FILE_TEXT.items():
        if p == hook_path:
            continue
        for m in re.finditer(r"\bHook\.(\w+)\(", t):
            callers[m.group(1)][rel(p)] += 1
    # 模型重写统计（排除 Mocks / 测试）
    overrides = Counter()
    for p, t in FILE_TEXT.items():
        rp = rel(p)
        if not rp.startswith("MegaCrit.Sts2.Core.Models.") or "Mocks" in rp or ".Mock/" in rp:
            continue
        for m in re.finditer(r"public override (?:async )?[\w<>\[\]?, ]+? (\w+)\(", t):
            overrides[m.group(1)] += 1
    rows = []
    for name, line, sig, body in methods:
        if name in ("IterateCombatHookListeners", "ModifyDamageInternal") or sig.startswith("private"):
            continue
        ret = re.match(r"public static (?:async )?([\w<>\[\]?, ]+?) \w+", sig)
        ret = ret.group(1) if ret else ""
        if "Task" in ret:
            kind = "事件(通知)"
        elif ret in ("decimal", "int"):
            kind = "数值修正"
        elif ret == "bool":
            kind = "判定(否决/许可)"
        else:
            kind = "改写(" + ret + ")"
        if "IterateCombatHookListeners(combatState)" in body:
            scope = "战斗(结束后静默)"
        elif "combatState.IterateHookListeners()" in body or "CombatState.IterateHookListeners()" in body:
            scope = "战斗(直派,结束中仍触发)"
        elif "IterateHookListeners(null)" in body:
            scope = "跑局(无战斗对象)"
        elif "runState.IterateHookListeners(combatState)" in body:
            scope = "跑局+战斗"
        elif "ModifyDamageInternal(" in body:
            scope = "跑局+战斗"
        else:
            scope = "特殊"
        passes = []
        for m in re.finditer(r"\b(?:model\d?|item\d?|modifier)\.(\w+)\(", body):
            if m.group(1) not in passes and m.group(1) not in ("InvokeExecutionFinished",):
                passes.append(m.group(1))
        if name == "ModifyDamage":
            # 真正的三轮遍历在 private ModifyDamageInternal 里
            passes = ["EnchantDamageAdditive", "EnchantDamageMultiplicative",
                      "ModifyDamageAdditive", "ModifyDamageMultiplicative", "ModifyDamageCap"]
        bool_rule = ""
        if kind.startswith("判定"):
            if re.search(r"if \(!item\d?\.\w+\(", body):
                bool_rule = "任一返回 false 即否决"
            elif re.search(r"if \(item\d?\.\w+\(", body):
                bool_rule = "任一返回 true 即生效"
            elif "flag || " in body:
                bool_rule = "任一返回 true 即生效(遍历全部)"
        choice = ""
        if "new HookPlayerChoiceContext" in body:
            choice = "每监听者独立选择上下文(可并行等待)"
        elif "PushModel" in body:
            choice = "共用调用方选择上下文(串行)"
        cs = callers.get(name, Counter())
        ov = sum(overrides.get(p, 0) for p in passes) if passes else 0
        rows.append({
            "hook": name,
            "phase": hook_phase(name),
            "kind": kind,
            "return": ret,
            "dispatch_scope": scope,
            "passes": " → ".join(passes),
            "bool_rule": bool_rule,
            "choice_context": choice,
            "call_sites": sum(cs.values()),
            "caller_files": "; ".join(f for f, _ in cs.most_common(3)),
            "model_overrides": ov,
            "source": "MegaCrit.Sts2.Core.Hooks/Hook.cs:%d" % line,
        })
    write_csv("ch01_hooks.csv", rows)
    return rows


# ---------------------------------------------------------------- powers
TAGS = [
    ("伤害修正", r"ModifyDamage(Additive|Multiplicative|Cap)\b"),
    ("失血修正", r"ModifyHpLost\w*\b"),
    ("格挡修正", r"ModifyBlock(Additive|Multiplicative)\b"),
    ("格挡保留", r"ShouldClearBlock\b"),
    ("能力施加修正", r"ModifyPowerAmount\w+|TryModifyPowerAmountReceived\b"),
    ("能量/抽牌/费用", r"ModifyEnergyGain|ModifyMaxEnergy|ModifyHandDraw\w*|ShouldDraw\b|ShouldPlayerResetEnergy|TryModifyEnergyCost\w*|TryModifyStarCost|ModifyXValue|ShouldPayExcessEnergyCostWithStars"),
    ("出牌规则", r"ModifyCardPlayCount|ShouldPlay\b|ModifyCardPlayResultLocation|TryModifyKeywordsInCombat|ShouldEtherealTrigger|ShouldFlush"),
    ("受击/攻击触发", r"BeforeDamageReceived|AfterDamageReceived\w*|AfterDamageGiven|BeforeAttack|AfterAttack|ModifyAttackHitCount|AfterBlockBroken|AfterBlockGained|BeforeBlockGained|AfterCurrentHpChanged|ModifyUnblockedDamageTarget"),
    ("出牌触发", r"BeforeCardPlayed|AfterCardPlayed\w*|AfterEnergySpent|AfterStarsSpent|BeforeCardAutoPlayed"),
    ("牌堆触发", r"AfterCardDrawn\w*|AfterCardDiscarded|AfterCardExhausted|AfterShuffle|AfterCardEnteredCombat|AfterCardGeneratedForCombat|AfterHandEmptied|AfterCardChangedPiles\w*"),
    ("回合触发", r"BeforeSideTurnStart|AfterSideTurnStart\w*|BeforeSideTurnEnd\w*|AfterSideTurnEnd\w*|AfterPlayerTurnStart|AfterEnergyReset\w*|BeforeHandDraw\w*|BeforeFlush\w*|AfterFlush|AfterBlockCleared|AfterAutoP\w+PhaseEntered"),
    ("死亡/复活", r"ShouldDie\w*|BeforeDeath|AfterDeath|AfterPreventingDeath|ShouldCreatureBeRemovedFromCombatAfterDeath|ShouldPowerBeRemovedAfterOwnerDeath|ShouldStopCombatFromEnding|AfterDiedToDoom|ShouldOwnerDeathTriggerFatal"),
    ("能力联动", r"AfterPowerAmountChanged|BeforePowerAmountChanged"),
    ("目标/可被攻击", r"ShouldAllowHitting|ShouldAllowTargeting"),
    ("额外回合", r"ShouldTakeExtraTurn|AfterTakingExtraTurn"),
    ("充能球/召唤/铸造/星辰", r"AfterOrb\w+|ModifyOrb\w+|AfterSummon|ModifySummonAmount|AfterForge|AfterStarsGained|ShouldGainStars|AfterOstyRevived"),
]
PRIMARY_ORDER = ["伤害修正", "失血修正", "格挡修正", "能力施加修正", "能量/抽牌/费用", "出牌规则", "格挡保留",
                 "额外回合", "目标/可被攻击", "死亡/复活", "受击/攻击触发", "出牌触发", "牌堆触发",
                 "充能球/召唤/铸造/星辰", "能力联动", "回合触发"]

SRC_DIRS = {
    "卡牌": "MegaCrit.Sts2.Core.Models.Cards/",
    "怪物": "MegaCrit.Sts2.Core.Models.Monsters/",
    "遗物": "MegaCrit.Sts2.Core.Models.Relics/",
    "药水": "MegaCrit.Sts2.Core.Models.Potions/",
    "附魔": "MegaCrit.Sts2.Core.Models.Enchantments/",
    "事件": "MegaCrit.Sts2.Core.Models.Events/",
    "充能球": "MegaCrit.Sts2.Core.Models.Orbs/",
    "能力": "MegaCrit.Sts2.Core.Models.Powers/",
    "苦难/修饰": "MegaCrit.Sts2.Core.Models.Afflictions/|MegaCrit.Sts2.Core.Models.Modifiers/",
}


def method_blocks(text):
    """切出 override 方法块: [(name, body)]"""
    lines = text.split("\n")
    idx = [i for i, l in enumerate(lines) if re.match(r"^\t(public|protected) override ", l)]
    out = []
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(lines)
        m = re.search(r"\b(\w+)\s*\(", lines[i])
        if m:
            out.append((m.group(1), "\n".join(lines[i:j])))
    return out


def decay_info(text):
    acts = []
    for name, body in method_blocks(text):
        act = None
        if "TickDownDuration(this)" in body:
            act = "TickDown"
        elif re.search(r"PowerCmd\.Decrement\(this\)", body):
            act = "-1"
        elif re.search(r"PowerCmd\.Remove\(this\)", body):
            act = "移除"
        elif re.search(r"PowerCmd\.ModifyAmount\([^;]*this,\s*-", body):
            act = "减层"
        if not act:
            continue
        side = ""
        if "CombatSide.Enemy" in body:
            side = "敌方侧"
        elif "CombatSide.Player" in body:
            side = "玩家侧"
        elif "participants.Contains(base.Owner)" in body or "side == base.Owner.Side" in body or "side != base.Owner.Side" in body:
            side = "持有者侧"
        acts.append("%s:%s%s" % (name, act, "(" + side + ")" if side else ""))
    return acts


def duration_model(stack, acts, text):
    turn_hooks = ("AfterSideTurnEnd", "AfterSideTurnStart", "BeforeSideTurnEnd", "BeforeSideTurnStart",
                  "AfterPlayerTurnStart", "AfterEnergyReset", "BeforeHandDraw", "AfterTurnEnd",
                  "AfterSideTurnEndLate", "BeforeSideTurnEndEarly", "BeforeSideTurnEndVeryEarly", "AfterFlush", "BeforeFlush")
    if any(":TickDown" in a for a in acts):
        return "回合计时(敌方回合末-1)"
    turn_acts = [a for a in acts if a.split(":")[0] in turn_hooks]
    other_acts = [a for a in acts if a.split(":")[0] not in turn_hooks]
    if any(":移除" in a for a in turn_acts) and not any(":-1" in a or ":减层" in a for a in turn_acts):
        return "限时(回合切换时整体移除)"
    if any(":-1" in a or ":减层" in a for a in turn_acts):
        return "回合计时(每回合-1)"
    if other_acts:
        return "按次消耗(触发后-1/移除)"
    if stack == "Single":
        return "开关(整场)"
    return "持续(整场,层数=强度)"


def build_powers():
    pdir = os.path.join(SRC, "MegaCrit.Sts2.Core.Models.Powers")
    base_rows = {}
    pcsv = os.path.join(OUT, "powers.csv")
    if os.path.exists(pcsv):
        with open(pcsv, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                base_rows[r["cls"]] = r
    # 基类解析（处理 TemporaryStrength 等）
    texts = {}
    bases = {}
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".cs"):
            continue
        cls = fn[:-3]
        t = read(os.path.join(pdir, fn))
        texts[cls] = t
        m = re.search(r"class %s\s*:\s*(\w+)" % cls, t)
        bases[cls] = m.group(1) if m else ""
    # 来源统计
    src_count = defaultdict(Counter)
    for p, t in FILE_TEXT.items():
        rp = rel(p)
        cat = None
        for k, v in SRC_DIRS.items():
            if any(rp.startswith(x) for x in v.split("|")):
                cat = k
                break
        if not cat or "Mocks" in rp:
            continue
        for m in set(re.findall(r"\b(\w+Power)\b", t)):
            if m in texts and not rp.endswith("/" + m + ".cs"):
                src_count[m][cat] += 1

    def chain(cls):
        out, c = [], cls
        while c in texts:
            out.append(c)
            c = bases.get(c, "")
        return out

    rows = []
    for cls in sorted(texts):
        t = "\n".join(texts[c] for c in chain(cls))  # 子类+父类文本，便于继承属性
        own = texts[cls]
        note = []

        def prop(pattern, default=""):
            m = re.search(pattern, t)
            return m.group(1) if m else default

        ptype = prop(r"PowerType Type => PowerType\.(\w+);")
        if not ptype:
            if "override PowerType Type" in t:
                ptype = "动态"
                if "IsPositive" in t:
                    pos = re.search(r"override bool IsPositive => (\w+);", own)
                    ptype = "Debuff" if (pos and pos.group(1) == "false") else "Buff"
                    note.append("Type 由 IsPositive 决定")
        stack = prop(r"PowerStackType StackType => PowerStackType\.(\w+);")
        if not stack and "PowerStackType StackType" in t:
            stack = "动态"
            note.append("StackType 为条件 getter")
        inst = prop(r"PowerInstanceType InstanceType => PowerInstanceType\.(\w+);", "None")
        allow_neg = "是" if re.search(r"AllowNegative => true", t) else ""
        mp_scale = "是" if re.search(r"ShouldScaleInMultiplayer => true", t) else ""
        hidden = "是" if re.search(r"IsVisibleInternal => false", t) else ""
        ovs = sorted(set(re.findall(r"(?:public|protected) override (?:async )?[\w<>\[\]?, ]+? (\w+)\(", t)))
        ovs = [o for o in ovs if o not in ("GetScaledAmountForMultiplayer", "InitInternalData", "AddDumbVariablesToDescription")]
        tags = []
        for tag, pat in TAGS:
            if any(re.fullmatch(pat, o) for o in ovs):
                tags.append(tag)
        primary = next((p for p in PRIMARY_ORDER if p in tags), "被动/标记")
        # 只认「类声明里实现了 ITemporaryPower」或继承 Temporary*Power 的；
        # 只是在方法体里引用 ITemporaryPower（如 IllusionPower、SleightOfFleshPower 的 `is ITemporaryPower` 判断）的不算
        is_temp = any(re.search(r"class %s\s*:[^{\n]*\bITemporaryPower\b" % c, texts[c]) for c in chain(cls)) \
            or bases.get(cls, "").startswith("Temporary")
        if is_temp:
            primary = "临时属性(回合末返还)"
        acts = decay_info(t)
        dur = duration_model(stack, acts, t)
        if bases.get(cls, "PowerModel") not in ("PowerModel", ""):
            note.append("继承 " + bases[cls])
        b = dict(base_rows.get(cls, {}))
        if is_temp and not b.get("name_zh"):
            b["name_zh"] = "(标题取来源卡/药水/遗物名)"
        sc = src_count.get(cls, Counter())
        rows.append({
            "cls": cls,
            "name_zh": b.get("name_zh", ""),
            "name_en": b.get("name_en", ""),
            "type": ptype,
            "stack": stack,
            "instance": inst,
            "allow_negative": allow_neg,
            "mp_scale": mp_scale,
            "hidden": hidden,
            "primary": primary,
            "tags": "/".join(tags),
            "duration_model": dur,
            "decay": "; ".join(acts),
            "src_cards": sc.get("卡牌", 0),
            "src_monsters": sc.get("怪物", 0),
            "src_relics": sc.get("遗物", 0),
            "src_potions": sc.get("药水", 0),
            "src_other": sum(v for k, v in sc.items() if k not in ("卡牌", "怪物", "遗物", "药水")),
            "overrides": " ".join(ovs),
            "note": "; ".join(note),
            "desc_zh": b.get("desc_zh", ""),
            "source": "MegaCrit.Sts2.Core.Models.Powers/%s.cs" % cls,
        })
    write_csv("ch01_power_taxonomy.csv", rows)
    return rows


# ---------------------------------------------------------------- intents
def build_intents():
    idir = os.path.join(SRC, "MegaCrit.Sts2.Core.MonsterMoves.Intents")
    loc = {}
    lp = os.path.join(LOC, "intents.json")
    if os.path.exists(lp):
        with open(lp, encoding="utf-8") as f:
            loc = json.load(f)
    mon_files = [p for p in ALL_FILES if rel(p).startswith("MegaCrit.Sts2.Core.Models.Monsters/")]
    rows = []
    for fn in sorted(os.listdir(idir)):
        cls = fn[:-3]
        if cls in ("IntentType", "AbstractIntent"):
            continue
        t = read(os.path.join(idir, fn))
        itype = re.search(r"IntentType IntentType => IntentType\.(\w+);", t)
        itype = itype.group(1) if itype else ("Debuff/DebuffStrong" if cls == "DebuffIntent" else
                                              "Attack(继承)" if re.search(r":\s*\w*AttackIntent", t) else "(抽象)")
        prefix = re.search(r'IntentPrefix => "(\w+)"', t) or re.search(r'_intentPrefix = "(\w+)"', t)
        prefix = prefix.group(1) if prefix else ("ATTACK" if "Attack" in cls else "")
        sprite = re.search(r'SpritePath => "([^"]+)"', t) or re.search(r'_spritePath = "([^"]+)"', t)
        sprite = sprite.group(1) if sprite else ""
        uses, examples = 0, []
        for p in mon_files:
            n = len(re.findall(r"new %s\(" % cls, FILE_TEXT[p]))
            if n:
                uses += n
                if len(examples) < 4:
                    examples.append(os.path.basename(p)[:-3])
        rows.append({
            "intent_class": cls,
            "intent_type": itype,
            "loc_prefix": prefix,
            "title_zh": loc.get(prefix + ".title", ""),
            "desc_zh": loc.get(prefix + ".description", ""),
            "uses_in_monsters": uses,
            "example_monsters": "/".join(examples),
            "sprite": sprite,
            "source": "MegaCrit.Sts2.Core.MonsterMoves.Intents/%s" % fn,
        })
    write_csv("ch01_intents.csv", rows)
    return rows


def write_csv(name, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote", name, len(rows))


if __name__ == "__main__":
    h = build_hooks()
    p = build_powers()
    i = build_intents()
    # 汇总打印，方便写正文
    print("hook kinds", Counter(r["kind"].split("(")[0] for r in h))
    print("hook scope", Counter(r["dispatch_scope"] for r in h))
    print("hook phase", Counter(r["phase"] for r in h))
    print("power type", Counter(r["type"] for r in p))
    print("power stack", Counter(r["stack"] for r in p))
    print("power inst", Counter(r["instance"] for r in p))
    print("power primary", Counter(r["primary"] for r in p))
    print("power duration", Counter(r["duration_model"] for r in p))
    print("power src", Counter(("卡" if int(r["src_cards"]) else "") + ("怪" if int(r["src_monsters"]) else "")
                                 + ("遗" if int(r["src_relics"]) else "") + ("药" if int(r["src_potions"]) else "") for r in p))
