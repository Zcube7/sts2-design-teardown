# 第 01 章 战斗内核：回合、结算管线、Hook、意图、能力与关键词

> 版本 v0.111.1（commit cc1f9462）。出处路径相对 `csharp/sts2_src/`。本章新表：`data/csv/ch01_hooks.csv`（148 个 Hook 时点）、`data/csv/ch01_power_taxonomy.csv`（268 个能力）、`data/csv/ch01_intents.csv`（16 个意图类）。可重跑脚本 `scripts/ch01_extract.py`。
> 充能球细节见第 02 章，怪物招式内容见第 04 章，代码架构与联机同步见第 07 章。

## 0. 本章结论速览

| # | 结论 | 出处 |
|---|---|---|
| 1 | 基础规则沿用一代：每回合能量重置为上限 3、抽 5 张、手牌上限 10；未用完的能量清零，手牌（除保留外）回合末进弃牌堆 | `MegaCrit.Sts2.Core.Combat/CombatManager.cs:41`、`MegaCrit.Sts2.Core.Entities.Cards/CardPile.cs:21`、`MegaCrit.Sts2.Core.Models/CharacterModel.cs:97` |
| 2 | 一个玩家回合拆成 Start → AutoPrePlay → Play → AutoPostPlay → End 五个阶段，"回合开始自动打出""回合末自动打出"有专门的阶段，不和抽牌、清格挡混在一起 | `MegaCrit.Sts2.Core.Combat/PlayerTurnPhase.cs` |
| 3 | 伤害公式在代码里是固定的三轮：先所有加算（力量等），再所有乘算（易伤 1.5、虚弱 0.75），最后取上限（无实体、难以杀灭）；附魔在三轮之前只改卡面数字 | `MegaCrit.Sts2.Core.Hooks/Hook.cs:1639-1722,2664-2711` |
| 4 | 全程用 decimal 精确计算，只在最后写入格挡/扣血时向零截断，所以 7×0.75=5.25 记为 5；格挡用同一套"加算 → 乘算"规则（敏捷、脆弱 0.75） | `MegaCrit.Sts2.Core.Entities.Creatures/Creature.cs:431-467` |
| 5 | 扣血还有第二套管线：格挡结算之后有 4 轮"失血修正"（Osty 转移伤害前后各有常规轮和 Late 轮）。缓冲、钨棒、滑溜只挂在这里，不在伤害公式里；无实体两边都挂（伤害上限 1 + 失血上限 1，见 4.2） | `MegaCrit.Sts2.Core.Commands/CreatureCmd.cs:283-312` |
| 6 | Hook 一共 148 个时点：81 个事件、20 个数值修正、28 个判定、19 个改写。执行顺序不用优先级数字，靠两样东西：固定的监听者遍历顺序，加上 Early/常规/Late 多轮遍历（22 个 Hook 有多轮） | `data/csv/ch01_hooks.csv`；`MegaCrit.Sts2.Core.Combat/CombatState.cs:115-185` |
| 7 | 修正分成"纯计算"和"计算后结算"两步：Modify* 只算数，不产生副作用，预览也能调用；只有真正改动了数值的模型才会收到 AfterModifying* 回调，这时才扣层数（比如缓冲只在确实把伤害降到 0 时才消耗） | `MegaCrit.Sts2.Core.Hooks/Hook.cs:925-935`，`MegaCrit.Sts2.Core.Models.Powers/BufferPower.cs` |
| 8 | 持续型负面状态（易伤、虚弱、脆弱）统一在**敌方回合结束**时 -1。新施加到玩家身上的负面状态会跳过第一次衰减，这样敌人在自己回合给的负面，能完整覆盖玩家接下来的一个回合 | `MegaCrit.Sts2.Core.Commands/PowerCmd.cs:148-151,195-205` |
| 9 | 新关键词奇巧（Sly）：被效果弃掉时免费自动打出（回合末的弃手牌不算）；现有 7 张奇巧牌全是静默猎手的，卡面费用偏高（7 张里 6 张是 2–3 费），真正的打出方式是弃掉它 | `MegaCrit.Sts2.Core.Commands/CardCmd.cs:172-205` |
| 10 | 新关键词永恒（Eternal）：不能从牌组移除，牌组里的这张也不能被变化。7 张永恒牌里有 6 张诅咒，另 1 张是能力牌禁忌魔典 | `MegaCrit.Sts2.Core.Models/CardModel.cs:738-751` |
| 11 | 费用修饰统一成"有序修饰列表 + 3 种过期时机 + 只降不升标志"，再叠加一层实时计算的全局修饰。"本回合/本场/直到打出"都是同一个结构的不同参数 | `MegaCrit.Sts2.Core.Entities.Cards/CardEnergyCost.cs`、`LocalCostModifier.cs` |
| 12 | 随机数有 12 条跑局级流和 3 条玩家级流，另有 1 条表现专用的混沌流。洗牌前先按 ID 排序（稳定洗牌），存档点在进入房间之前，所以战斗中途 SL 刷不出不同结果（推断） | `MegaCrit.Sts2.Core.Runs/RunRngSet.cs`、`MegaCrit.Sts2.Core.Extensions/ListExtensions.cs:22-31`、`MegaCrit.Sts2.Core.Runs/RunManager.cs:907-910` |

---

## 1. 骨架：模型 + 命令 + Hook（只讲本章需要的部分，细节见第 07 章）

- **模型（Model）**：卡牌、能力、遗物、药水、怪物、附魔、苦难、充能球都继承自 `AbstractModel`。基类上有 185 个 `public virtual` 成员（其中 182 个是钩子方法，另 3 个是 CompareTo、IsMock、PreviewOutsideOfCombat），内容只需要 `override` 自己关心的时点（`MegaCrit.Sts2.Core.Models/AbstractModel.cs`）。
- **命令（Cmd）**：所有改动战斗状态的操作都走静态命令类，比如 `CreatureCmd.Damage/GainBlock/Kill`、`PowerCmd.Apply/ModifyAmount/TickDownDuration`、`CardPileCmd.Draw/Shuffle/Add`、`CardCmd.Discard/Exhaust/AutoPlay`、`PlayerCmd.GainEnergy`。Hook 由命令内部负责触发，内容代码只调命令（`MegaCrit.Sts2.Core.Commands/`）。
- **Hook**：`static class Hook` 里有 148 个 `public static` 方法，每个方法遍历当前所有监听者，调用对应的虚方法（`MegaCrit.Sts2.Core.Hooks/Hook.cs`）。

这样分层的结果：策划写一张新牌只需要组合命令，结算顺序和触发时机由框架统一决定。新牌只要复用已有命令，就不会因为写法不同而跳过某个时点。

---

## 2. 一场战斗的时序

### 2.1 开战准备

| 步骤 | 发生什么 | 出处 |
|---|---|---|
| 1 | 每个玩家新建战斗状态，**牌组克隆进抽牌堆**（战斗中对牌的改动不会写回牌组）；用 `Shuffle` 流做一次非稳定洗牌，然后派发 `ModifyShuffleOrder(isInitialShuffle:true)` | `MegaCrit.Sts2.Core.Entities.Players/Player.cs:809-818`、`MegaCrit.Sts2.Core.Entities.Cards/CardPile.cs`（RandomizeOrderInternal） |
| 2 | 怪物生成招式状态机，标记 `SpawnedThisTurn=true` | `MegaCrit.Sts2.Core.Models/MonsterModel.cs:552-556` |
| 3 | 对每个生物调用 `AfterAddedToRoom`；当前轮到玩家方时，怪物**第一次掷招式**（决定第 1 回合的意图） | `CombatManager.cs:1130-1137` |
| 4 | `IsInProgress=true` → `Hook.BeforeCombatStart`（两轮：常规、Late） | `CombatManager.cs:594-596`、`Hook.cs:455-467` |
| 5 | 开战横幅 / 新手引导 → 进入第一个玩家回合 | `CombatManager.cs:600-612` |

### 2.2 玩家回合开始（`StartTurn` + `SetupPlayerTurn`）

| 序 | 时点 | 内容 | 典型挂载 | 出处 |
|---|---|---|---|---|
| 1 | `BeforeTurnStart` | 给每个能力记一份"回合开始时层数"快照 `AmountOnTurnStart`，避免本回合中途获得的能力当回合就触发 | — | `Creature.cs:683-689`、`PowerModel.cs:205` |
| 2 | `Hook.BeforeSideTurnStart` | 回合开始前 | 怪物的覆甲在第 1 轮先给一次格挡 | `CombatManager.cs:723`、`Powers/PlatingPower.cs` |
| 3 | 阶段 = Start；**所有敌人重掷招式**（额外回合不重掷） | 玩家看到的意图在这一步定下 | — | `CombatManager.cs:727-747` |
| 4 | `AfterTurnStart` → **清格挡** | 玩家第 1 回合不清（所以开战前拿到的格挡能带进第 1 回合）；`ShouldClearBlock` 一票否决 | 壁垒、残影 | `Creature.cs:691-702,728-738` |
| 5 | `Hook.AfterBlockCleared` | 清完格挡之后 | 下回合格挡、坚韧之环 | `CombatManager.cs:764-772` |
| 6 | 能量 | `ShouldPlayerResetEnergy` 为真时重置为上限，否则把上限加到剩余能量上；然后 `AfterEnergyReset`（两轮） | 冰淇淋（第 2 回合起保留能量）、下回合能量 | `CombatManager.cs:894-903`、`Relics/IceCream.cs:10-20` |
| 7 | `Hook.BeforeHandDraw`（两轮） | 抽牌前 | 夜魇、既定事项 | `CombatManager.cs:905` |
| 8 | `Hook.ModifyHandDraw(5)`（两轮） → `AfterModifyingHandDraw` | 计算抽牌数 | 下回合抽牌、明晰等 18 个模型 | `CombatManager.cs:907-908` |
| 9 | 仅第 1 回合：带"开局置底"附魔的牌放到底部，**固有牌放到顶部**，抽牌数 = max(抽牌数, 固有牌数)，上限 10 | 固有保证上手 | — | `CombatManager.cs:910-925` |
| 10 | `CardPileCmd.Draw(fromHandDraw:true)` | 逐张抽，每张都派发 `AfterCardDrawn`（Early、常规两轮） | 混乱（抽到时随机费用） | `CombatManager.cs:926`、`CardPileCmd.cs:1010-1069` |
| 11 | `Hook.AfterPlayerTurnStart`（Early/常规/Late 三轮） | 玩家回合开始 | 22 个模型 | `CombatManager.cs:928`、`Hook.cs:1038-1061` |
| 12 | `Hook.AfterSideTurnStart`（常规、Late） | 本方回合开始。**玩家身上的中毒在这里结算，也就是在抽完牌之后** | 中毒、残影 -1、覆甲 -1 | `CombatManager.cs:785`、`Powers/PoisonPower.cs:55` |
| 13 | 充能球回合开始被动 | — | 见第 02 章 | `CombatManager.cs:789-798` |
| 14 | 阶段 = AutoPrePlay → 检查空手牌 → `AfterAutoPrePlayPhaseEntered`（三轮）→ 阶段 = Play | 回合开始时的自动打出 | HistoryCourse、Imbued 附魔、WhisperingEarring | `CombatManager.cs:864-871`、`PlayerTurnPhase.cs:25-34` |
| 15 | `CheckWinCondition` → 开放操作 | 进入出牌阶段 | — | `CombatManager.cs:832-840` |

### 2.3 一张牌从打出到结算

```
PlayCardAction.ExecuteAction                                  (GameActions/PlayCardAction.cs:62-103)
 ├─ 校验：牌必须还在手里；CanPlay（不能被打出 / 资源 / ShouldPlay 否决 / 卡牌自身条件）+ 目标合法，否则取消
 ├─ SpendResources：先扣能量（X 费取走当前全部能量）→ AfterEnergySpent → 再扣辉星 → AfterStarsSpent
 └─ OnPlayWrapper                                              (Models/CardModel.cs:1858-2019)
     ├─ 牌移入 Play 堆（打出中的临时堆，既不算手牌也不算弃牌）
     ├─ 决定去向：能力牌 / 复制品 → 移出战斗；有"消耗"或 ExhaustOnNextPlay → 消耗堆；其余 → 弃牌堆底
     │   └─ Hook.ModifyCardPlayResultLocation 可以改写（比如弹回）
     ├─ 打出次数 = 1 + 附魔重放 + 卡牌自带重放 → Hook.ModifyCardPlayCount（爆发 / 复制 / 回响形态…）
     ├─ 每次打出：BeforeCardPlayed → 卡牌 OnPlay → 附魔 OnPlay → 苦难 OnPlay → AfterCardPlayed（常规、Late）
     ├─ 移到去向堆（消耗时走 CardCmd.Exhaust → AfterCardExhausted）
     ├─ CheckForEmptyHand → AfterHandEmptied（等整张牌结算完才检查，避免"手牌空了"抽两次）
     └─ 清掉"直到打出"类费用修饰
```

要点：

- **重放时每一次都完整走一遍 Before/AfterCardPlayed**，所以"每打出一张牌"类效果对重放生效（`CardModel.cs:1896-1971`）。
- 能力牌打出后**移出战斗**，不进弃牌堆（`CardModel.cs:2086-2089`）。
- 空手牌检查的时机写在注释里：必须等整张牌结算完再检查，否则 UnceasingTop 配 PommelStrike 会多抽一次（`CombatManager.cs:1139-1156`）。
- 自动打出（`CardCmd.AutoPlay`）**不花能量**（`EnergySpent=0`），X 费按当前能量记一份 X 值；没有指定目标时用 `CombatTargets` 流随机选一个（`CardCmd.cs:51-131`）。

### 2.4 玩家回合结束：两段式

所有玩家都按下结束回合后，进入第一段（这一段允许玩家做选择）（`CombatManager.cs:1522-1596`）：

| 序 | 内容 | 典型挂载 | 出处 |
|---|---|---|---|
| 1 | 等玩家主动发起的动作队列跑完 | — | `CombatManager.cs:1482-1507` |
| 2 | 阶段 = AutoPostPlay → `AfterAutoPostPlayPhaseEntered` | 惊逃、IAmInvincible（回合末自动打出） | `PlayerTurnPhase.cs:41-48` |
| 3 | 阶段 = End → `Hook.BeforeSideTurnEnd`（VeryEarly / Early / 常规三轮） | 覆甲（Early，先于回合末伤害）、再生（Early）、炸弹倒数 | `Hook.cs:1388-1418` |
| 4 | 每个玩家：充能球回合末被动 → 先把不带"回合末在手"效果的**虚无**牌消耗（`ShouldEtherealTrigger` 可否决）→ 再让"回合末在手"类牌依次结算（结算完进弃牌堆，有虚无则消耗） | 回合末在手中受伤的状态/诅咒牌 | `CombatManager.cs:1606-1680` |
| 5 | `Hook.BeforeFlush`（常规、Late） | 沉眠精华附魔（SlumberingEssence：回合末仍在手则本张费用 -1 直到打出），目前唯一重写者 | `Hook.cs:688-711` |

第二段只做状态清理，不允许任何需要玩家选择的 Hook（`CombatManager.cs:1731-1782`）：

| 序 | 内容 | 出处 |
|---|---|---|
| 6 | **弃手牌（Flush）**：`ShouldFlush` 为假时整手保留（符文金字塔 RunicPyramid、计划妥当 WellLaidPlans 等 4 个模型）；否则除 `ShouldRetainThisTurn` 外全部进弃牌堆。注意这里调的是 `CardPileCmd.Add`，**不算"弃牌"**：不派发 `AfterCardDiscarded`，也不触发奇巧 | `CombatManager.cs:1784-1818` |
| 7 | `Hook.AfterFlush` → 所有牌做回合末清理（清本回合费用修饰、单回合保留/奇巧、ExhaustOnNextPlay） | `CardModel.cs:1611-1624` |
| 8 | `Hook.AfterSideTurnEnd`（常规、Late）——**临时力量在这里返还**，玩家方的灾厄在这里判定 | `Powers/TemporaryStrengthPower.cs:147-155`、`Powers/DoomPower.cs:68` |
| 9 | `ShouldTakeExtraTurn`：只要有一个监听者返回真，该玩家就再进行一个玩家回合（PaelsEye、龙涎香），否则切到敌方 | `CombatManager.cs:1824-1854` |

### 2.5 敌方回合

1. `BeforeTurnStart`（快照）→ `BeforeSideTurnStart(Enemy)` → 横幅 → **清怪物格挡** → `AfterBlockCleared` → `AfterSideTurnStart(Enemy)`（怪物身上的中毒结算，覆甲 -1）（`CombatManager.cs:715-786`）。
2. `ExecuteEnemyTurn`：按 `Enemies` 列表顺序（开战时按遭遇里的槽位排序，`CombatState.cs:679-685`），每个怪物播放意图动画 → `TakeTurn` → 执行 `NextMove`。**本回合新召唤的怪物不行动**（`SpawnedThisTurn`，`Creature.cs:716-726`）。每个怪物行动完都检查一次胜负（`CombatManager.cs:1419-1437`）。
3. `EndEnemyTurnInternal`：`BeforeSideTurnEnd(Enemy)`（**敌方的灾厄在这里斩杀**）→ 所有玩家的牌再做一次回合末清理 → `AfterSideTurnEnd(Enemy)`（**易伤、虚弱、脆弱、无实体在这里 -1**）（`CombatManager.cs:1695-1704`）。
4. `SwitchSides`：切回玩家方，`RoundNumber++`，每个玩家 `TurnNumber++`（`CombatManager.cs:1856-1894`）。

### 2.6 回合数与轮数、胜负

- **`TurnNumber` 按玩家各自计数，`RoundNumber` 按整轮计数**。额外回合只加前者，所以"第 N 回合触发"类效果用 `TurnNumber`，怪物"第 1 轮"类判断用 `RoundNumber`（`PlayerCombatState.cs:29-37`、`CombatManager.cs:1875-1887`）。
- **主/次要敌人**：身上有爪牙（MinionPower）、幻象之类能力的怪物算次要敌人。所有主要敌人死亡且没有监听者 `ShouldStopCombatFromEnding` 时战斗结束；剩下的若全是次要敌人会被连带击杀（`Creature.cs:253-279`、`CreatureCmd.cs:571-576`、`CombatManager.cs:418-437`）。会阻止战斗结束的有 5 个怪物能力：适者生存、寄生物、蒸汽喷发、库存、意外（复活 / 死后生怪）。
- **失败是延迟处理的**：玩家全灭时先记一个 `PendingLoss`，等到下一个安全点（`CheckWinCondition`）再真正结束，好让当前动作完整跑完（`CombatManager.cs:1263-1288`）。
- 死亡流程：`BeforeDeath` → `ShouldDie`（常规 + Late，一票否决，比如精灵瓶）→ 不死则派发 `AfterPreventingDeath`，并最多递归 10 次防止死循环（`CreatureCmd.cs:515-606`）。

### 设计观察

- **"自动打出"有单独的阶段**。一代里回合开始自动打牌和抽牌常常互相抢时机（与一代对比，凭公开知识）。二代把 AutoPrePlay/AutoPostPlay 单独切出来：自动打出发生时，抽牌和清格挡已经全部完成，状态是稳定的。
- **结束回合拆成"可选择"和"纯清理"两段**，是给联机用的：第一段每个玩家可以并行做选择，第二段保证没有阻塞。单机策划也可以借鉴：凡是需要玩家决策的回合末效果，都要放在弃手牌之前。
- **中毒在抽牌之后结算**（玩家方）。毒伤看到的是已经抽好的手牌，这对设计"回合开始掉血就触发某张手牌"类联动有影响。

---

## 3. 资源数值：能量、抽牌、手牌、牌堆

| 项 | 数值 / 规则 | 出处 |
|---|---|---|
| 能量上限 | 3（CharacterModel 默认）；实际上限 = `Hook.ModifyMaxEnergy`（16 个模型改它，比如 Sozu、PhilosophersStone、Ectoplasm、四个能力） | `Models/CharacterModel.cs:97`、`PlayerCombatState.cs:107` |
| 能量重置 | 回合开始时 `Energy = MaxEnergy`（剩余作废）；冰淇淋否决重置后改为 `Energy += MaxEnergy` | `PlayerCombatState.cs:168-176` |
| 能量范围 | 加减都夹在 0–999,999,999 | `PlayerCombatState.cs:178-194` |
| 基础抽牌 | 5（`baseHandDrawCount`），经 `ModifyHandDraw` 两轮修正 | `CombatManager.cs:41,907` |
| 抽牌取整 | 抽牌数是 decimal，**向上取整**（`Math.Ceiling`） | `CardPileCmd.cs:1025` |
| 手牌上限 | 10。抽牌时手满就停；**其他方式往手牌加牌时手满则直接进弃牌堆**，并弹出"手牌已满" | `CardPile.cs:21`、`CardPileCmd.cs:485-489,1030-1035` |
| 抽空 | 抽牌堆空就把弃牌堆洗入（ShuffleIfNecessary）；两堆都空就弹出"无牌可抽"并停止 | `CardPileCmd.cs:1189-1198,1275-1288` |
| 洗牌 | 弃牌堆 + 当前抽牌堆**合并后稳定洗牌**（先按模型 ID、再按升级等级排序，然后 Fisher–Yates），然后派发 `ModifyShuffleOrder` 和 `AfterShuffle` | `CardPileCmd.cs:1076-1136`、`ListExtensions.cs:22-31` |
| 随机位置插入 | `CardPilePosition.Random` 用 `Shuffle` 流决定插入位置 | `CardPileCmd.cs:511` |
| 辉星（储君的资源） | 与能量并列的第二资源；有星辰费用的牌两种都要付。框架预留了"能量不足时用 2 辉星抵 1 能量"（`ShouldPayExcessEnergyCostWithStars`），**但当前版本没有任何内容重写它** | `PlayerCombatState.cs:196-215`、`CardModel.cs:1807-1820` |
| X 费 | 打出时把当前全部能量（或辉星）记为 X，再经 `Hook.ModifyXValue`（ChemicalX 类效果） | `CardModel.cs:1117-1146`、`CardEnergyCost.cs:134-141` |

### 设计观察

- **"手满进弃牌堆"而不是"手满作废"**，对生成牌的设计很宽容，生成溢出也不浪费。
- **稳定洗牌**是个容易被忽略的反操控设计：洗出来的顺序只取决于"哪些牌"和 RNG 状态，和"按什么顺序弃的牌"无关（严格说排序键只有模型 ID 和升级等级：ID、等级都相同，只是附魔、苦难或临时费用不同的几张牌，彼此的相对顺序仍可能受原顺序影响，因为 `List.Sort` 不是稳定排序）。玩家没法靠调整弃牌顺序来控制下一轮抽牌；联机各端也不会因为本地牌堆顺序不同而结果分歧（`ListExtensions.cs:10-31` 注释原文说明了"结果与初始顺序无关"）。
- 抽牌向上取整，偏向玩家；伤害向零截断对双方是对称的（玩家带虚弱打 7 点同样只剩 5），谈不上偏向玩家。

---

## 4. 伤害与格挡结算管线

### 4.1 伤害类型：三个标志位

`ValueProp` 是位标志（`MegaCrit.Sts2.Core.ValueProps/ValueProp.cs`）：

| 标志 | 含义 |
|---|---|
| `Move`（8） | 来自卡牌或怪物招式的"攻击" |
| `Unpowered`（4） | 不吃力量/易伤/虚弱这类"强化修正" |
| `Unblockable`（2） | 无视格挡（失去生命） |
| `SkipHurtAnim`（16） | 只影响表现 |

预设组合（`DamageProps.cs`、`BlockProps.cs`）：

| 预设 | 标志 | 用途举例 |
|---|---|---|
| `DamageProps.card` / `monsterMove` | Move | 普通攻击，吃全部修正 |
| `cardUnpowered` | Move+Unpowered | 诅咒/状态牌对玩家造成的伤害 |
| `cardHpLoss` | Move+Unpowered+Unblockable | 卡牌的"失去 X 生命"代价 |
| `nonCardUnpowered` | Unpowered | 荆棘之类：可以被格挡，但不吃力量 |
| `nonCardHpLoss` | Unpowered+Unblockable | 中毒 |
| `BlockProps.card` | Move | 卡牌格挡，吃敏捷/脆弱 |
| `cardUnpowered` / `nonCardUnpowered` | (+Move)+Unpowered | 翻倍格挡类、覆甲：不吃敏捷 |

核心判定是 `IsPoweredAttack() = 有 Move 且没有 Unpowered`（`ValuePropExtensions.cs`；格挡侧用逻辑相同的 `IsPoweredCardOrMonsterMoveBlock()`，另有只看 Move 的 `IsCardOrMonsterMove()`）。力量、易伤、虚弱、活力都先检查这一条。

### 4.2 伤害公式（按代码执行顺序）

```
攻击层 AttackCommand.Execute                                (Commands.Builders/AttackCommand.cs:527-675)
  BeforeAttack → 段数 = Hook.ModifyAttackHitCount(原段数)
  每段：重新取存活目标（随机目标用 CombatTargets 流）→ CreatureCmd.Damage

数值层 Hook.ModifyDamage（对每个目标单独算）                   (Hooks/Hook.cs:1639-1722, 2664-2711)
  d = 卡面基础值
  ① 附魔加算   d += Enchant.Additive(d)          例：Sharp +N
  ② 附魔乘算   d *= Enchant.Multiplicative(d)    例：Corrupted ×1.5
  ③ 全局加算   d += Σ listener.ModifyDamageAdditive      力量、活力、精准…
  ④ 全局乘算   d *= Π listener.ModifyDamageMultiplicative 易伤 1.5、虚弱 0.75、双倍伤害 2、缓慢 1+0.1n…
  ⑤ 上限       d = min(d, min(listener.ModifyDamageCap))  无实体 1、难以杀灭 N
  d = max(0, d)

结算层 CreatureCmd.Damage                                   (Commands/CreatureCmd.cs:258-434)
  AfterModifyingDamageAmount(只回调真正改了数的模型) → BeforeDamageReceived
  格挡吸收  blocked = Unblockable ? 0 : min(Block, d)；Block -= (int)blocked   ← 宠物用主人的格挡
  失血修正 A  ModifyHpLostBeforeOsty → …Late（硬化外壳每回合上限）
  转移目标    ModifyUnblockedDamageTarget（亡灵契约师 → Osty，见第 02 章）
  失血修正 B  ModifyHpLostAfterOsty → …Late（无实体 ≤1、滑溜 ≤1、钨棒 -1、TheBoot 最低 5、缓冲 → 0）
  扣血        LoseHpInternal：(int) 截断，夹在 0–999,999,999；Osty 被打穿时溢出伤害再走一次 B 轮打到本体
  事后（全部目标算完才统一派发）：AfterBlockBroken → AfterCurrentHpChanged → AfterDamageGiven
       → 活着的派发 AfterDamageReceived(+Late)，死了的收集起来统一 Kill
```

**关键点：**

1. **加算全部先于乘算**，所以力量会被易伤/虚弱放大；乘算之间是交换律（易伤×虚弱 = 1.125）；上限取所有监听者里最小的那个。
2. **附魔在全局修正之前，而且只作用于卡面数字**：Corrupted 的 ×1.5 只乘基础伤害，不乘力量（②在③之前）。可以理解为"附魔改的是印在牌上的数字"（`Hook.cs:1643-1653`）。
3. **易伤和虚弱的系数本身也会被修正**：易伤 1.5，PaperPhrog +0.25，残酷每层 +1%，摧残让额外部分翻倍（1.5→2.0）；虚弱 0.75，PaperKrane -0.15（持有者受到的伤害），摧残让减少部分翻倍（0.75→0.5）（`Powers/VulnerablePower.cs:23-48`、`Powers/WeakPower.cs:23-45`、`Relics/PaperPhrog.cs`、`Powers/DebilitatePower.cs`）。系数修正写在易伤/虚弱内部，不额外占一个乘区，避免出现 1.5×1.25 这种"乘区叠乘"。
4. **无实体做了双保险**：⑤把伤害（含被格挡的部分）压到 1，B 轮再把失血压到 1；无实体不检查伤害类型，失去生命也会被压到 1（`Powers/IntangiblePower.cs:15-56`）。
5. **AfterDamageReceived 不发给被打死的生物**；需要"死时触发"的效果走 `AfterDeath`。

### 4.3 格挡公式

```
CreatureCmd.GainBlock                                        (Commands/CreatureCmd.cs:668-701)
  战斗已结束或目标已死 → 0
  BeforeBlockGained
  Hook.ModifyBlock：附魔加算 → 附魔乘算 → Σ加算（敏捷、勒紧…）→ Π乘算（脆弱 0.75）→ max(0)   (Hook.cs:1466-1496)
  AfterModifyingBlockAmount（只回调改了数的）
  Block += (int)值，上限 999,999,999                         (Creature.cs:460-467)
  AfterBlockGained
```

敏捷只作用于 `Move` 且非 `Unpowered` 的格挡，也就是卡牌和怪物招式给的格挡（`Powers/DexterityPower.cs`）；脆弱同理（`Powers/FrailPower.cs:22-33`）。覆甲、余像这类能力给的格挡用 `Unpowered`（残影不给格挡，它是否决清格挡），不吃这两者。

### 4.4 取整规则

| 环节 | 方式 | 出处 |
|---|---|---|
| 所有中间运算 | `decimal`，没有浮点误差 | Hook.cs 全篇 |
| 格挡吸收 | `(int)` 截断 | `Creature.cs:433-434` |
| 扣血 | `(int)Math.Clamp` 截断 | `Creature.cs:450` |
| 获得格挡 | `(int)` 截断 | `Creature.cs:466` |
| 卡面预览 / 意图数字 | `(int)PreviewValue` / `(int)num` 截断 | `Localization.DynamicVars/DynamicVar.cs:173`、`MonsterMoves.Intents/AttackIntent.cs:92` |
| 能力层数 | `(int)` 截断 | `PowerCmd.cs:241`、`PowerModel.cs:570` |
| 抽牌数 | 向上取整 | `CardPileCmd.cs:1025` |

算例（攻击力 6、力量 +2）：

| 情形 | 计算 | 结果 |
|---|---|---|
| 无修正 | 6+2 | 8 |
| 攻击者虚弱 | (6+2)×0.75 = 6.0 | 6 |
| 目标易伤 | 8×1.5 | 12 |
| 虚弱 + 易伤 | 8×0.75×1.5 = 9.0 | 9 |
| 攻击 7、无力量、虚弱 | 7×0.75 = 5.25 | 5 |
| 攻击 7、虚弱 + 易伤 | 7×1.125 = 7.875 | 7 |
| 目标易伤 + 摧残 | 8×2.0 | 16 |
| 目标无实体、有格挡 5 | ⑤压到 1 → 格挡吸收 1 → 失血 0 | 0（格挡剩 4） |

> 与一代对比（凭公开知识）：一代也是先算力量再乘易伤/虚弱，最后向下取整，数值手感一致。二代把"多段、多乘区、上限"写成了框架层的三轮固定顺序，内容不能自己插队。

### 4.5 "修正 → 结算"两段式

所有数值修正都分两步：

1. `ModifyX`：纯函数，只返回新值，同时记下"哪些模型真正改了数"（判断方式是值有变化，失血修正按截断后的整数比较）（`Hook.cs:1870-1918`）。
2. `AfterModifyingX(modifiers)`：**只回调第 1 步里改了数的模型**，这时才扣层数、闪图标（`Hook.cs:805-935`）。

效果：

- **预览安全**：卡面数字、意图数字直接调用 ModifyDamage，不会误扣层数（`DamageVar.cs`、`AttackIntent.cs:84-93`）。
- **消耗类能力只在"真的起作用"时才消耗**。缓冲挂在 Late 轮，源码注释写明这样安排对玩家更友好：别的效果已经把伤害降到 0 时，缓冲不用扣层（`Powers/BufferPower.cs:9-17`）。人工制品同理，只有真的挡下一个负面状态才 -1（`Powers/ArtifactPower.cs:17-41`）。

### 设计观察 / 可借鉴

- **"伤害"和"失血"是两条管线**：前者处理攻防数值（加/乘/上限），后者处理减伤规则（≤1、-1、最低值、归零），格挡夹在中间。这样做以后，"钨棒每次失血 -1"自然不会被易伤放大，"无实体"也能对失去生命生效。策划设计减伤类效果时，第一个问题应该是"挂在格挡前还是格挡后"。
- **Late 轮代替优先级数字**：顺序敏感的效果（取最小、清零）放 Late 轮，其余放常规轮。规则简单，策划能看懂，也足够用。

---

## 5. Hook 体系

### 5.1 规模与分类（`data/csv/ch01_hooks.csv`）

| 维度 | 统计 |
|---|---|
| 总数 | 148 个 `public static` 时点 |
| 返回类型 | 事件（async Task）81 / 数值修正（decimal、int）20 / 判定（bool）28 / 改写（返回位置、生物、卡牌、地图等）19 |
| 派发范围 | 战斗内且"战斗结束后静默"73 / 战斗内直派（结束中仍触发）10 / 跑局+战斗 23 / 纯跑局 42 |
| 按时点大类 | 回合流程 20、伤害与格挡 20、出牌与费用 15、牌堆流转 13、角色资源 11、死亡/召唤 11、能力 7、战斗开始/结束 5、药水 5、地图/房间 13、奖励/商店/营火/牌组 28 |
| 多轮遍历 | 22 个 Hook 有 Early/常规/Late 多轮（比如 AfterCardDrawn、AfterPlayerTurnStart、BeforeSideTurnEnd、ModifyHpLost、ShouldDie） |

**重写次数前十**（Models 目录下的 `override` 数量，Mock 除外）：AfterSideTurnEnd 67、AfterCardPlayed 66、AfterSideTurnStart 51、AfterCombatEnd 45、ModifyDamage 43（附魔/加算/乘算/上限四类重写合计）、AfterRoomEntered 37、AfterDeath 31、BeforeCardPlayed 29、BeforeSideTurnStart 27，BeforeCombatStart 与 AfterPlayerTurnStart 并列 22。可以看出内容的主体是**回合首尾触发和出牌触发**。

### 5.2 监听者遍历顺序（决定同一时点谁先触发）

战斗内 `CombatState.IterateHookListeners`（`MegaCrit.Sts2.Core.Combat/CombatState.cs:115-185`）：

```
对每个生物（先友方后敌方，各自按列表顺序）：
   ① 该生物身上的能力（按获得顺序）
   ② 怪物 → 怪物模型本身
     玩家 → 遗物（按获得顺序，已熔毁的跳过）→ 药水栏 → 充能球
           → 手牌 → 抽牌堆 → 弃牌堆 → 消耗堆 → 打出中，每张牌后面紧跟它的苦难、附魔
然后：修饰符 → 徽章 → 多人缩放模型 → Mod 订阅者
```

跑局级 `RunState.IterateHookListeners`（`MegaCrit.Sts2.Core.Runs/RunState.cs:126-201`）：牌组里的卡和附魔 →（不在战斗中时）遗物、药水、修饰符、徽章、缩放模型 → Mod → 再接战斗内列表。

**策划含义**：

- 同一时点上，**玩家能力先于遗物**，**遗物先于手牌**；玩家方整体先于敌方。举例（假设场景）：如果回合末"某能力给格挡"和"某遗物按当前格挡造成伤害"都挂在 AfterSideTurnEnd 的常规轮，能力一定先触发，遗物读到的是加过格挡之后的值。
- 顺序是确定的，不依赖哈希或注册时间。联机各端结果一致的前提就在这里。
- 需要跨类别调整顺序时，靠 Early/Late 轮次，比如覆甲放在 BeforeSideTurnEndEarly，就是为了"先于回合末伤害"（`Powers/PlatingPower.cs:58-68` 注释）。

### 5.3 派发守卫

- **战斗结束后静默**：`IterateCombatHookListeners` 在**派发开始时**检查一次战斗是否已结束或正在结束，是的话这次派发一个监听者都不调用；派发已经开始的，即使中途有人打出致命一击，剩下的监听者也照常执行（`Hook.cs:177-207` 注释）。这样"打死最后一个怪后还在抽的牌"不会再触发效果，但同一次派发里的结算不会被截断。
- **直派**：有 10 个时点必须在"击杀那一下"里完整执行，所以绕过守卫：AfterBlockBroken、AfterCardPlayed、AfterDamageGiven、AfterDiedToDoom、ShouldStopCombatFromEnding、ShouldCreatureBeRemovedFromCombatAfterDeath、ModifyUnblockedDamageTarget、ModifyKeywordsInCombat、AfterCreatureAddedToCombat、ShouldPowerBeRemovedOnDeath。其中 8 个在注释里写了理由（ModifyKeywordsInCombat、ShouldPowerBeRemovedOnDeath 没写）。另外，23 个"跑局+战斗"时点（ModifyDamage、ModifyHpLost、AfterDamageReceived、ShouldDie、AfterDeath 等）走 `RunState.IterateHookListeners`，同样不经过这道守卫。

### 5.4 判定类 Hook 的投票规则

| 规则 | Hook |
|---|---|
| **任一 false 即否决**（大多数） | ShouldPlay、ShouldDraw、ShouldClearBlock、ShouldFlush、ShouldPlayerResetEnergy、ShouldDie、ShouldAllowHitting、ShouldAllowTargeting、ShouldEtherealTrigger、ShouldAfflict… |
| **任一 true 即生效** | ShouldTakeExtraTurn、ShouldStopCombatFromEnding、ShouldPayExcessEnergyCostWithStars、ShouldAllowSelectingMoreCardRewards、ShouldRefillMerchantEntry |
| 遍历全部再取或 | ShouldForcePotionReward、ShouldAllowFreeTravel、TryModifyCardRewardOptions |

否决型 Hook 会返回 `preventer`（是谁挡的），UI 据此弹出提示气泡，比如"被 Normality 阻止"（`CardCmd.cs:64-72`）。

**预留但没用上的接口**：`ShouldPayExcessEnergyCostWithStars`、`ShouldEtherealTrigger` 当前没有任何内容重写。

### 5.5 回合首尾 Hook 的分层（最常用的四个时点）

| Hook | 轮次 | 何时 |
|---|---|---|
| BeforeSideTurnStart | 1 | 本方回合开始、清格挡之前 |
| AfterSideTurnStart | 常规 → Late | 清格挡、能量、抽牌之后（玩家方） |
| BeforeSideTurnEnd | VeryEarly → Early → 常规 | 本方回合末、弃手牌之前 |
| AfterSideTurnEnd | 常规 → Late | 弃手牌之后、切换阵营之前 |

参数里的 `side` 和 `participants` 都会传进来，所以能力常用 `participants.Contains(Owner)` 判断"是不是我方回合"，用 `side == CombatSide.Enemy` 表示"敌方回合末"（`data/csv/ch01_power_taxonomy.csv` 的 decay 列记录了每个能力用的是哪种写法）。

### 设计观察

- **用"固定遍历顺序 + 少量命名轮次"代替优先级数字**，是可维护性和可读性之间的折中：一共只有 Early/常规/Late（个别 VeryEarly）几档，策划能记住；内容数量到几百之后，优先级数字往往会膨胀成谁也说不清的"魔法数"。
- **派发守卫在开始时判断一次，不逐个判断**，这个细节值得抄：逐个判断会造成"同一时点里排在后面的效果被吞掉"这类难以复现的 bug。

---

## 6. 意图系统（框架部分；具体招式见第 04 章）

### 6.1 意图类型（`data/csv/ch01_intents.csv`）

| IntentType | 类 | 简中名 | 怪物代码里的使用次数 | 说明 |
|---|---|---|---|---|
| Attack | SingleAttackIntent / MultiAttackIntent | 攻势 | 162 / 54 | 显示伤害（多段显示"伤害×段数"），伤害可以是动态的 lambda |
| DeathBlow | DeathBlowIntent | 濒死一击 | 2 | 攻击的子类，"被摧毁前打你一下"（GasBomb、WaterfallGiant） |
| Buff | BuffIntent | 强化 | 75 | |
| Debuff / DebuffStrong | DebuffIntent(strong) | 策略 | 41（其中 strong 2） | 同一个类，用 strong 参数区分强负面 |
| Defend | DefendIntent | 守势 | 23 | |
| StatusCard | StatusIntent | 策略 | 18 | 显示塞入状态牌的张数 |
| CardDebuff | CardDebuffIntent | 恶意 | 4 | **二代新增**：对你的卡牌施加"侵蚀"（苦难，见第 03 章） |
| Summon | SummonIntent | 召唤 | 8 | |
| Stun | StunIntent | 击晕 | 8 | 被击晕时由系统临时插入 |
| Sleep | SleepIntent | 沉睡 | 5 | |
| Heal | HealIntent | 回复 | 4 | |
| Escape | EscapeIntent | 懦弱 | 2 | |
| Hidden | HiddenIntent | （无） | 5 | 不显示提示，用于 Architect、测试假人（BigDummy、OneHpMonster 等） |
| Unknown | UnknownIntent | 未知 | 0 | 定义了但当前没有怪物使用 |

### 6.2 组合意图：一个招式挂多个意图

`MoveState(stateId, onPerform, params AbstractIntent[] intents)` 可以同时挂多个意图（`MonsterMoves.MonsterMoveStateMachine/MoveState.cs:47-52`）。统计：1 意图 245 个招式、2 意图 77 个、3 意图 4 个。最常见的组合是"单段攻击 + 强化"18 次、"单段攻击 + 负面"17 次、"单段攻击 + 防御"11 次。

> 与一代对比（凭公开知识）：一代把组合写成枚举值（ATTACK_BUFF、ATTACK_DEBUFF、DEFEND_BUFF…），组合越多枚举越膨胀。二代改成意图列表，新增一种意图不用穷举组合。

### 6.3 攻击意图的显示

- 显示的数字 = 把招式基础伤害代入 `Hook.ModifyDamage`（目标取本地玩家，`ValueProp.Move`）再截断，所以力量、虚弱、易伤都会实时反映在意图上（`AttackIntent.cs:84-93`）。
- 图标按**总伤害**分 5 档：<5、<10、<20、<40、≥40（`AttackIntent.cs:43-69`）。
- 能力层数变化时会刷新意图（`PowerCmd.cs:256-270`）。

### 6.4 招式状态机（框架）

| 组件 | 规则 | 出处 |
|---|---|---|
| `MoveState` | 一个招式：执行函数 + 意图列表 + 后续状态 `FollowUpState`；`MustPerformOnceBeforeTransitioning` 表示至少执行一次才能离开 | `MoveState.cs` |
| `RandomBranchState` | 按权重随机（`MonsterAi` 流），权重可以是 lambda；重复规则有 4 种：CanRepeatForever / CanRepeatXTimes / CannotRepeat（不能连续两次）/ UseOnlyOnce（整场一次）；另有冷却 N 回合 | `RandomBranchState.cs:114-170`、`MonsterMoves/MoveRepeatType.cs` |
| `ConditionalBranchState` | 按顺序取第一个条件为真的分支 | `ConditionalBranchState.cs` |
| 怪物代码里的使用量 | RandomBranch 24 处、ConditionalBranch 17 处、CannotRepeat 45 处、UseOnlyOnce 2 处、CanRepeatForever 4 处 | grep `Models.Monsters/` |
| 掷骰时机 | 每个**玩家回合开始**时重掷，这时掷出的就是即将显示的意图；开战时先掷一次，但在执行过第一个招式之前不会跳走，所以两次掷骰不冲突 | `CombatManager.cs:741-747`、`MonsterMoveStateMachine.cs:62` |
| 眩晕 | 插入一个 `STUNNED` 招式（击晕意图），执行完回到原来的招式 | `Creature.cs:525-545` |

### 设计观察

- **"不能连续"按状态日志判断**，掷骰前就把权重置 0，而不是"掷到了再重掷"，所以不会额外消耗随机数，对复现友好（`RandomBranchState.cs:128-170`）。
- 恶意（CardDebuff）意图说明二代把"污染你的牌"提升成了和"塞状态牌"并列的一类威胁，需要单独一种预警图标。

---

## 7. 能力（268 个）怎么分类

### 7.1 三个结构轴（来自代码属性，`data/csv/ch01_power_taxonomy.csv`）

| 轴 | 取值 | 数量 | 含义 |
|---|---|---|---|
| Type | Buff / Debuff | 215 / 53（268 里含 3 个抽象基类 TemporaryStrength/Dexterity/FocusPower，都计入 Buff；可实例化的能力是 265 个） | 临时力量类的 Type 由正负决定（降力量算 Debuff，所以人工制品能挡） |
| StackType | Counter / Single / 动态 / None | 227 / 38 / 2 / 1 | Counter 显示层数；Single 不显示层数，相当于开关 |
| InstanceType | None / Instanced / InstancedPerApplier | 245 / 21 / 2 | None：同类合并层数；Instanced：每次施加都是独立实例（炸弹，每个各自倒数）；PerApplier：按施加者分开（湮灭、紧勒，联机下每个玩家各一份） |
| AllowNegative | 是 | 5 | 力量、敏捷、集中、尖叫、缩小；层数为 0 时移除，其他能力 ≤0 时移除 |
| 多人缩放 | 是 | 12 | 怪物身上的覆甲、人工制品、滑溜等按人数放大（见第 04 章） |

移除规则：`AllowNegative` 的能力层数**恰好为 0**时移除，其余 ≤0 时移除（`PowerModel.cs:473-489`）。叠加规则：`PowerCmd.Apply` 先找可以叠加的现有实例，找到就走 `ModifyAmount`，找不到才新建；`BeforeApplied/AfterApplied` 只在**首次获得**时触发（`PowerCmd.cs:105-179`、`PowerModel.cs:600-622`）。

### 7.2 持续模型（脚本按衰减写法分类，可以回源码核对）

| 持续模型 | 数量 | 典型 | 规则 |
|---|---|---|---|
| 持续（整场，层数=强度） | 129 | 力量、荆棘、仪式、恶魔形态 | 不自然衰减 |
| 限时（回合切换时整体移除） | 57 | 24 个临时力量/敏捷/集中（21 个子类 + 3 个抽象基类）、火焰屏障、不可抽牌、缠结 | "本回合"效果，回合末一次性移除 |
| 开关（整场） | 29 | 壁垒、腐化、爪牙 | Single |
| 按次消耗 | 27 | 人工制品、缓冲、活力、免费攻击、滑溜 | 触发一次 -1 或移除 |
| 回合计时（每回合 -1） | 23 | 中毒（本方回合开始时）、残影、覆甲、无实体 | 每回合固定时点 -1 |
| 回合计时（敌方回合末 -1，带首跳豁免） | 3 | 易伤、虚弱、脆弱 | 见 7.4 |

### 7.3 功能分类（按重写的 Hook 归类，取最主要的一类）

| 主类 | 数量 | 代表 |
|---|---|---|
| 回合触发 | 54 | 中毒、灾厄、恶魔形态、仪式、覆甲、毒雾 |
| 伤害修正 | 30 | 力量、易伤、虚弱、无实体、难以杀灭、双倍伤害、缓慢、巨像 |
| 出牌触发 | 29 | 余像、雷暴、谋划专家、激怒 |
| 临时属性（回合末返还） | 24 | FlexPotion、预判、黑暗镣铐（临时力量/敏捷/集中的子类） |
| 受击/攻击触发 | 26 | 荆棘、火焰屏障、涂毒、蜷身、沉睡 |
| 能量/抽牌/费用 | 21 | 腐化、缠结、免费攻击、下回合抽牌、不可抽牌 |
| 牌堆触发 | 16 | 无惧疼痛、黑暗之拥、混乱 |
| 出牌规则 | 16 | 爆发、复制、回响形态（打出次数）、昏眩、懒惰（禁止打出）、恶咒（加虚无） |
| 死亡/复活 | 15 | 爪牙、适者生存、意外、库存 |
| 被动/标记 | 12 | 后方攻击（只供"遭到包围"读取的标记） |
| 格挡修正 / 格挡保留 / 失血修正 | 6 / 3 / 3 | 敏捷、脆弱 / 壁垒、残影、埋地 / 缓冲、滑溜、硬化外壳 |
| 其他 | 13 | 目标许可（幻象、为你而死、适者生存、接续）、能力联动（厄运之衣、血肉戏法、凶恶）、充能球/铸造/星辰、额外回合（龙涎香）、施加修正（人工制品） |

**来源分布**（能力类名在哪些目录被引用）：卡牌引用、怪物不引用的 172 个（其中 164 个只出现在卡牌里，8 个也被遗物或药水引用），怪物引用、卡牌不引用的 57 个，卡牌和怪物都用的 12 个；其余 27 个卡牌和怪物都不引用（只在遗物、药水、附魔、其他能力里出现，或没有引用）（力量、敏捷、易伤、虚弱、脆弱、人工制品、无实体、覆甲、荆棘、活力、瓦解、沙坑）。也就是说**玩家能力和怪物能力基本是两套**，共用的只有一小组"通用属性"。

### 7.4 代表能力逐个讲

| 能力 | 规则（代码） | 设计要点 | 出处 |
|---|---|---|---|
| 力量（Strength / StrengthPower） | 加算 +层数，只对自己发出的强化攻击生效；可以为负 | 每段都加，多段攻击收益高 | `Powers/StrengthPower.cs:15-27` |
| 敏捷（Dexterity） | 卡牌/招式格挡 +层数；可以为负 | 和力量对称 | `Powers/DexterityPower.cs` |
| 易伤（Vulnerable） | 受到的强化攻击 ×1.5；敌方回合末 -1 | 系数可以被遗物或能力修正 | `Powers/VulnerablePower.cs:23,60-66` |
| 虚弱（Weak） | 造成的强化攻击 ×0.75；敌方回合末 -1 | | `Powers/WeakPower.cs:23,49-55` |
| 脆弱（Frail） | 获得的卡牌格挡 ×0.75；敌方回合末 -1 | | `Powers/FrailPower.cs:22-41` |
| **首跳豁免** | **新施加到玩家方**的负面状态 `SkipNextDurationTick=true`，第一次 TickDown 只清标记、不减层（叠加到已有层数上不会设置这个标记） | 怪物在自己回合给你虚弱 1，你接下来的一个回合仍然有效，敌方回合末才消失；你给怪物的易伤 2 覆盖它接下来两次行动 | `PowerCmd.cs:148-151,195-205`、`PowerModel.cs:242-257` |
| 中毒（Poison） | 本方回合开始时（AfterSideTurnStart）受到等于层数的失去生命，然后 -1；触媒（Accelerant）能让它多结算几次，但次数不超过层数 | 失去生命无视格挡，算在"回合计时" | `Powers/PoisonPower.cs:29-80` |
| 灾厄（Doom，亡灵契约师） | 当前生命 ≤ 层数时，在回合末被**直接斩杀**（敌方在 BeforeSideTurnEnd，玩家方在 AfterSideTurnEnd），并派发 `AfterDiedToDoom` | 不造成伤害、不扣血，"斩杀线"玩法 | `Powers/DoomPower.cs:60-76,144-147` |
| 人工制品（Artifact） | 在 `TryModifyPowerAmountReceived` 里把"负面且可见"的施加量改成 0，挡下后 -1 | 不可见的隐藏负面挡不住；降力量这种"临时负面"能挡 | `Powers/ArtifactPower.cs:17-41` |
| 无实体（Intangible） | 伤害上限 1 + 失血上限 1；敌方回合末 -1 | 双保险见 4.2 | `Powers/IntangiblePower.cs` |
| 缓冲（Buffer） | 失血 B 轮的 Late：归 0，实际挡下才 -1 | "友好消耗"的范例 | `Powers/BufferPower.cs` |
| 难以杀灭（HardToKill，怪物） | 每次伤害上限 = 层数 | 怪物版的"锁血" | `Powers/HardToKillPower.cs` |
| 滑溜（Slippery，怪物） | 失血上限 1，实际掉血才 -1；多人 × 人数 | | `Powers/SlipperyPower.cs` |
| 覆甲（Plating） | 回合末 Early 获得等于层数的不吃敏捷的格挡；本方回合开始 -1；怪物身上的覆甲第 1 轮开战就先给一次，多人每回合减人数层，施加量 ×(2n-1) | 用持续格挡做"慢慢变脆"的怪物 | `Powers/PlatingPower.cs:23-88` |
| 活力（Vigor） | 下一次**卡牌**攻击的每段都加层数，那次攻击结束后扣掉开始时的层数 | 一次攻击整段吃满，多段攻击就是放大器 | `Powers/VigorPower.cs:23-87` |
| 临时力量（TemporaryStrength 基类） | 获得时同时给真正的力量，本方回合末移除自己并把力量扣回；标题取来源（药水、卡牌、遗物）的名字 | 把一代的"力量下降"状态改成明确的"临时 Buff"，界面上更清楚（源码注释原意） | `Powers/TemporaryStrengthPower.cs:13-155` |
| 壁垒 / 残影 | `ShouldClearBlock` 否决清格挡；残影本方回合开始 -1 | | `Powers/BarricadePower.cs:32`、`BlurPower.cs:20-45` |
| 炸弹（TheBomb） | Instanced：每张炸弹各自倒数 | 实例化的典型 | `Entities.Powers/PowerInstanceType.cs` 注释 |
| 遭到包围 + 后方攻击 | 背后有"后方攻击"标记的攻击者打你 ×1.5 | 用标记能力表达站位 | `Powers/SurroundedPower.cs:46-72` |
| 缓慢（Slow，怪物） | 每打出一张牌，受到的攻击 +10%，本方回合开始清零 | 怪物自带的弱点，奖励"一回合多打牌"（唯一来源是旧日雕像 BygoneEffigy 给自己施加） | `Powers/SlowPower.cs` |
| 缠结（Tangled，怪物） | 本回合攻击牌费用 +层数（全局费用修饰），被影响的牌用 Entangled 苦难标记，能力移除时一并清掉 | 能力和苦难配合使用 | `Powers/TangledPower.cs` |

### 设计观察 / 可借鉴

- **能力是"带层数的 Hook 订阅者"**：268 个能力大部分只重写 1–3 个 Hook。新增能力的边际成本很低，这是二代能堆到 268 个能力的工程前提。
- **"可见性"是规则的一部分**：人工制品只挡可见的负面，隐藏的技术性能力（龙涎香）不会被误挡（`ArtifactPower.cs:28-32`）。
- **临时属性统一建模**：21 个"本回合 ±X 力量/敏捷/集中"分别继承 3 个抽象基类（TemporaryStrength/Dexterity/FocusPower），玩家看到的就是来源名字加"临时"，不用学一个新词。

---

## 8. 卡牌关键词

| 关键词 | 简中 | 卡牌数* | 规则（代码事实） | 出处 |
|---|---|---|---|---|
| 消耗（Exhaust） | 消耗 | 100 | 打出后进消耗堆（本场不再回来）；`ExhaustOnNextPlay` 是"下一次打出时消耗"的临时标记 | `CardModel.cs:2090-2094`、`CardCmd.cs:237-248` |
| 虚无（Ethereal） | 虚无 | 18 | 回合末还在手牌里就消耗（`causedByEthereal=true`），弃手牌之前执行；`ShouldEtherealTrigger` 可以否决（目前没有内容用） | `CombatManager.cs:1613-1630` |
| 固有（Innate） | 固有 | 9（另有 15 处升级加固有） | 第 1 回合抽牌前放到抽牌堆顶，抽牌数至少等于固有牌数（上限 10） | `CombatManager.cs:910-925` |
| 不能被打出（Unplayable） | 不能被打出 | 27 | `CanPlay` 直接 false；被自动打出时直接移到结果堆、不执行效果；这类牌费用为 -1，"设为 0 费"类效果对它无效 | `CardModel.cs:1734-1737`、`CardCmd.cs:59-63`、`CardEnergyCost.cs:177,199` |
| 保留（Retain） | 保留 | 12（另有 12 处升级加保留） | 回合末弃手牌时留在手里；另有"单回合保留"（`GiveSingleTurnRetain`），回合末清除 | `CardModel.cs:573-601,1348-1351`、`CombatManager.cs:1799-1808` |
| **奇巧（Sly）** | 奇巧 | 7 | 见 8.1 | `CardCmd.cs:172-205` |
| **永恒（Eternal）** | 永恒 | 7 | 见 8.2 | `CardModel.cs:738-751` |

\* 按 `data/csv/cards.csv` 的 keywords 列（卡面自带的关键词）统计；升级时增删的关键词按 `Models.Cards/` 里 `AddKeyword/RemoveKeyword` 的出现次数计：+固有 15、+保留 12、-消耗 19、-虚无 3（按出现次数，不是按牌去重）。

关键词分两种来源（`Entities.Cards/KeywordSources.cs`）：

- **Local**：写在牌上，会随克隆保留，比如 MusicBox 给的虚无。
- **Global**：由场上其他模型实时计算，不存储，比如恶咒（Hex / HexPower）让带 Hexed 苦难的牌临时获得虚无；能力消失后自动失效（`Powers/HexPower.cs:11-24`）。

卡面文字顺序固定：虚无 → 奇巧 → 保留 → 固有 → 不能被打出 → 正文 → 消耗 → 永恒（`CardKeywordOrder.cs`）。

### 8.1 奇巧（Sly）——"弃牌即打出"

**规则**（`CardCmd.DiscardAndDraw`，`CardCmd.cs:172-205`）：

1. 通过 `CardCmd.Discard` 弃牌时，先记下哪些牌这回合是奇巧（`IsSlyThisTurn`）。
2. 依次把所有被弃的牌放进弃牌堆并派发 `AfterCardDiscarded`。
3. 如果是"弃 N 抽 M"类效果，**先把牌抽完**。
4. 最后逐张 `AutoPlay(SlyDiscard)`：牌从弃牌堆拉回，**免费打出**（不花能量；X 费按当前能量计），目标随机。

**不触发的情况**：

- **回合末弃手牌不触发**（`FlushPlayerHand` 用的是 `CardPileCmd.Add`，不是"弃牌"，`CombatManager.cs:1810-1814`），这和关键词描述里"在你的回合结束前……被丢弃"一致（`localization/zhs/card_keywords.json` SLY.description）。
- 牌被"不能被打出"或 `ShouldPlay` 否决时，只移到结果堆。

**获得方式**：卡面自带 7 张，全部是静默猎手的：磨蚀（Abrasive）3 费能力、本能反应（Reflex）3 费技能、战术大师（Tactician）3 费技能、鬼祟（Sneaky）2 费能力、连续反弹（Ricochet）2 费攻击、触不可及（Untouchable）2 费技能、翻越撑击（FlickFlack）1 费攻击。另外：谋划专家（MasterPlanner）让打出的技能牌永久获得奇巧（`Powers/MasterPlannerPower.cs:14-25`）；HandTrick 类效果给单回合奇巧（`CardModel.cs:1357-1360`）。

**界面**：弃牌选择界面里，奇巧且"本来能打出或者只是费用不够"的牌会**发金光**，提示"弃这张等于免费打出"（`CardSelectCmd.cs:882-897`）。

**实现上的坑**：源码注释特别警告，批量弃牌不能循环调用单张 `Discard`，否则奇巧会在每弃一张时立刻打出，时机就错了（`CardCmd.cs:139-150`）。这说明奇巧的设计意图是"**一次弃牌动作全部结算完，再统一兑现**"。

> 与一代对比（凭公开知识）：一代的本能反应和战术大师是"不能被打出，被弃掉时抽 2 / 得 1 能量"的专属文字。二代把"被弃掉时触发"抽成通用关键词，效果改成"打出这张牌本身"：本能反应变成正常的 3 费抽牌，战术大师变成 3 费加能量。弃牌流派因此可以触发任何类型的牌，而且这些牌**也能花能量正常打出**，不再是死牌。

**设计观察**：奇巧牌的费用普遍偏高（2–3 费），等于告诉玩家这张牌的正确用法是弃掉它；同时给了一个"费用够就硬打"的保底。弃牌流派的价值从"弃牌附带效果"变成了"弃牌 = 白嫖高费牌"，构筑时会有意识地凑"弃牌源 + 奇巧高费牌"。

### 8.2 永恒（Eternal）——"甩不掉"

**规则**：`IsRemovable = 没有永恒`；`IsTransformable = 可移除，或者不在牌组里`。也就是说**牌组里的永恒牌不能移除也不能变化，战斗中的克隆可以被变化**（`CardModel.cs:738-751`）。

**生效面**：所有"从牌组选牌移除"的入口都经过 `IsRemovable` 过滤：商店删牌、营火 Cook、事件 Amalgamator / Pael / SlipperyBridge / WoodCarvings、遗物 PandorasBox（`CardSelectCmd.cs:747`、`Entities.RestSite/CookRestSiteOption.cs:64`、`Models.Events/*`、`Models.Relics/PandorasBox.cs:23`）。例外是怪物偷牌：偷窃草蜢（ThievingHopper）从抽牌堆/弃牌堆挑牌后直接 `RemoveFromDeck`，不检查 `IsRemovable`，理论上能把永恒牌暂时偷出牌组（击杀后作为奖励归还）（`Models.Monsters/ThievingHopper.cs:207-224`、`Models.Powers/SwipePower.cs:69-78`）。

**哪些牌**：进阶之灾（AscendersBane，进阶 5 塞入，见第 06 章）、霉运（BadLuck，回合末在手中失去生命）、铃铛的诅咒（CurseOfTheBell）、执迷（Enthralled，2 费，在手中时必须先打它）、愚行（Folly，固有 + 虚无 + 不能被打出）、贪婪（Greed）这 6 张诅咒，以及亡灵契约师的 Ancient 能力牌禁忌魔典（ForbiddenGrimoire，战斗结束时可以从牌组移除一张牌）。附魔 TezcatarasEmber 能给牌加上永恒（`Models.Enchantments/TezcatarasEmber.cs:18`）。

> 与一代对比（凭公开知识）：一代的进阶之灾、好奇诅咒等"不可移除"是逐张特判。二代统一成关键词，卡面直接写明。

**设计观察**：永恒把"代价不可逆"变成一种可以明码标价的属性。用在诅咒上表示"惩罚是永久的"；用在禁忌魔典这种强力 Ancient 牌上，表示"拿了就甩不掉，你得一直带着它"，正负两面都能用。

---

## 9. 费用修饰：本回合 / 本场 / 直到打出

### 9.1 本地修饰：一个有序列表

每张牌的 `CardEnergyCost` 存一个 `LocalCostModifier` 列表，**按获得顺序依次套用**（`CardEnergyCost.cs:94-121`）：

| 字段 | 取值 |
|---|---|
| Type | Absolute（设为 N）/ Relative（加减 N） |
| Expiration | EndOfCombat（本场）/ EndOfTurn（本回合）/ WhenPlayed（直到打出），后两者可以组合 |
| IsReduceOnly | 只在会**降低**当前费用时生效（"降低"类文字，如 Enlightenment：已经被降到 0 的牌不会被抬回 1） |

8 个写入 API 对应策划文本：

| API | 文本 | 例 |
|---|---|---|
| `SetUntilPlayed` | 直到打出前费用为 N | 当前没有内容调用（API 注释举的 Eidolon 已改成"打出消耗堆里的虚无牌"） |
| `SetThisTurnOrUntilPlayed` | 本回合费用为 N（隐含"或直到打出"） | BulletTime |
| `SetThisTurn` | 本回合内多次打出都保持 | Flatten（API 注释举的 Invoke 当前并不调用它） |
| `SetThisCombat` | 本场战斗费用为 N | 混乱（抽到时随机 0–3）、Enlightenment+ |
| `AddUntilPlayed` / `AddThisTurnOrUntilPlayed` / `AddThisTurn` / `AddThisCombat` | 加减 N | SlumberingEssence 附魔 / — / Pinpoint / KinglyKick |

清理时机：回合末清 EndOfTurn（`CardEnergyCost.cs:331-335`，在 `CardModel.EndOfTurnCleanup` 里调用）；打出后清 WhenPlayed（`CardEnergyCost.cs:341-345`，在 `OnPlayWrapper` 末尾调用）；本场修饰随战斗克隆一起丢弃（牌组里的原件没被改过）。

**源码注释给出的完整算例**（`LocalCostModifier.cs` 类注释）：基础 5 费 → 本场设为 2 → 本场 +1 → 本回合设为 0 → 本场 +1，当前费用 = 1；回合结束后"本回合设为 0"失效，变成 2+1+1 = 4。也就是说**"设为"会覆盖它之前的所有修饰，但不影响之后的**。

升级降费时，Absolute 修饰里大于新费用的值会被压到新费用，避免"升级后反而更贵"（`CardEnergyCost.cs:351-372`）。

### 9.2 全局修饰：实时计算，不存储

`GetWithModifiers(All)` 在本地修饰之后，再经过 `Hook.ModifyEnergyCostInCombat`（常规 + Late 两轮）（`CardEnergyCost.cs:116-119`、`Hook.cs:1727-1743`）。挂这里的有：腐化（技能 0 费）、缠结（攻击 +N）、免费攻击 / 免费技能 / 免费能力、虚空形态、预借时间、好奇、BrilliantScarf、SpikedGauntlets 等 11 个。来源消失（比如缠结能力在回合末被移除、腐化能力消失）效果立刻消失，这和本地修饰"写在牌上"有本质区别（`CostModifiers.cs` 注释讲的就是这条原理；但注释里举的执迷例子已过时，当前执迷只用 `ShouldPlay` 强制先打它，不改费用）。

最终费用统一 `max(0, …)`；费用为负（不能被打出）的牌不参与任何修饰。

### 9.3 辉星费用

辉星费用用另一套 `TemporaryCardCost` 栈：UntilPlayed / ThisTurn / ThisCombat，取**最后加入**的那个；全局修饰走 `Hook.ModifyStarCost`。"免费"类效果（`SetToFreeThisTurn` 18 处、`SetToFreeThisCombat` 2 处）同时把能量和辉星都设为 0（`CardModel.cs:1267-1292`、`Entities.Cards/TemporaryCardCost.cs`）。

### 设计观察 / 可借鉴

- **把"本回合 / 本场 / 直到打出 / 只降不升"做成正交参数**，任意组合都有确定结果，而且源码注释给了算例。做卡牌游戏时，"费用 +1 后再被设为 0，回合末怎么恢复"是高频 bug 来源，这套结构可以直接照搬。
- **本地与全局分层**：会随来源消失的效果一律走全局实时计算，永远不会出现"来源没了，费用还挂着"。

---

## 10. 随机数：分流与防 SL

### 10.1 流的划分

| 层级 | 流 | 用途（源码注释） | 引用次数（grep） |
|---|---|---|---|
| 跑局 | UpFront | 开局一次性生成：遇到的怪、事件、遗物池 | 9 |
| 跑局 | **Shuffle** | 开战洗牌、补牌洗牌、随机插入位置 | 10 |
| 跑局 | UnknownMapPoint | 问号房的房间类型 | — |
| 跑局 | **CombatCardGeneration** | 战斗中生成牌（攻击药水等），**和卡牌奖励分开** | 35 |
| 跑局 | CombatPotionGeneration | 战斗中生成药水（不会生成治疗药水） | 5 |
| 跑局 | CombatCardSelection | 战斗中随机选牌（True Grit 等）；从抽牌堆随机位置自动打出也用它 | 16 |
| 跑局 | CombatEnergyCosts | 随机费用（混乱、SneckoEye） | 3 |
| 跑局 | CombatTargets | 随机目标（随机攻击、自动打出补目标） | 17 |
| 跑局 | MonsterAi | 怪物招式掷骰 | 3 |
| 跑局 | Niche | 不在乎互相干扰的零碎随机（CursedRun 修饰等） | 18 |
| 跑局 | CombatOrbs | 随机充能球（Chaos） | 2 |
| 跑局 | TreasureRoomRelics | 联机多人抢同一宝箱遗物时的分配 | 1 |
| 玩家 | Rewards | 本玩家的卡牌/药水奖励、是否掉药水 | 16 |
| 玩家 | Shops | 本玩家的商店货架 | 8 |
| 玩家 | Transformations | 变化结果 | 2 |
| 全局 | `Rng.Chaotic` | **非确定性**，按系统时间播种，只用于不影响玩法的随机（抖动、洗牌动画间隔、怪物皮肤、文本变体；另外新开局时生成随机种子也用它，`Helpers/SeedHelper.cs:20`） | 231 |
| 按内容 | `new Rng(player, ModelId, mixin)` | 种子 = 跑局种子 + 玩家**槽位序号** + 内容 ID 哈希（+mixin），同一内容在同一局里结果固定；用槽位而不用网络 ID，保证每日挑战的一致性 | 3 |

出处：`Entities.Rngs/RunRngType.cs`、`Runs/RunRngSet.cs`、`Random/PlayerRngSet.cs`、`Random/Rng.cs:18-52`。每条流的种子 = 跑局种子 + 流名哈希（`Rng.cs` 的 `Rng(ulong seed, string name)`）；底层算法是 Xoshiro256**，状态为 4 个 64 位整数加一个调用计数（`Random/MegaRandom.cs`）。

### 10.2 为什么 SL 刷不出东西（存读档机制为推断，代码依据如下）

1. **存档点**：进入地图节点时，**在创建房间之前**存一次档（`RunManager.cs:907-910`）；战斗胜利后存一次档，并标记房间已完成（`CombatManager.cs:1343-1344`）。读档时回到最近的地图坐标，重新进入房间（`RunManager.cs:854-862`）。
2. 所有流的完整状态都序列化进存档（`RunRngSet.ToSerializable`、`PlayerRngSet.ToSerializable`）。
3. 推论：**战斗中途退出再读档，会从开战前的随机状态重来**：开局洗牌相同，第 1 回合怪物意图相同；只要操作相同，结果就完全相同。
4. **分流隔离**：战斗里怎么打（用了几瓶生成药水、触发了几次随机目标）只消耗战斗流，不影响玩家的 `Rewards` 流，所以"换个打法刷出更好的战后卡牌奖励"行不通。`CombatCardGeneration` 的注释原文就是"和卡牌奖励分开，因为我们不希望攻击药水影响卡牌奖励"。
5. **稳定洗牌**再堵一个口子：洗牌前先排序，所以靠调整弃牌顺序也改变不了下一轮抽牌（见第 3 节）。

> 与一代对比（凭公开知识）：一代也是多条 RNG 流加楼层存档，SL 同样刷不了战斗。二代多了"按内容播种"和"稳定洗牌"两层，而且把战斗内生成和战后奖励彻底拆开。

### 设计观察 / 可借鉴

- **流按"玩家是否在意互相干扰"划分**，而不是按系统划分：Niche 流的定义就是"不在乎互相干扰的零碎随机"。随机数设计的核心问题是"哪些结果应该独立"，这个划分标准可以照搬。
- **表现用的随机数必须单独一条非确定性流**（Chaotic 有 231 处引用），否则一个粒子效果就能改变战斗结果，而且联机必然分歧。

---

## 11. 本章可借鉴清单（给策划）

1. **伤害公式写死三轮**（加 → 乘 → 上限）+ 格挡前后两段失血修正；新效果只能选挂在哪一轮，不能自定义顺序。
2. **数值修正分两步**：先纯计算，只有真正改了数值的效果才执行结算（扣层、闪图标），预览零副作用。
3. **持续型负面统一在"敌方回合末"计时，加上"新施加到玩家方跳过首次"**，让双方给的负面状态手感对称。
4. **回合拆出 AutoPrePlay / AutoPostPlay 阶段**，自动打出不再和抽牌、清格挡抢时机。
5. **用 Early/常规/Late 命名轮次代替优先级数字**，监听者遍历顺序固定：能力 → 遗物 → 药水 → 充能球 → 各牌堆的牌。
6. **关键词也分本地和全局**（写在牌上 / 来源实时计算），费用同理，来源消失效果自动消失。
7. **奇巧把"弃牌触发"抽成通用关键词**，卡面高费配合"弃掉免费打出"，弃牌流派的上限是所有高费牌。
8. **永恒把"不可移除"明码标价**，正负两面都能用。
9. **随机流按"是否应该互相独立"划分**，战斗流和奖励流隔离，再加上稳定洗牌，从机制上消灭 SL 收益。

---

## 附：本章数据表

| 文件 | 行数 | 列说明 |
|---|---|---|
| `data/csv/ch01_hooks.csv` | 148 | hook / phase（时点大类）/ kind（事件·数值修正·判定·改写）/ dispatch_scope（派发范围）/ passes（遍历轮次与对应虚方法）/ bool_rule（投票规则）/ choice_context / call_sites（调用点数）/ caller_files / model_overrides（Models 下的重写数）/ source |
| `data/csv/ch01_power_taxonomy.csv` | 268 | cls / 中英名 / type / stack / instance / allow_negative / mp_scale / hidden / primary（主功能类）/ tags（全部功能标签）/ duration_model / decay（衰减写法：方法:动作(阵营)）/ src_cards·monsters·relics·potions·other（引用该能力的文件数）/ overrides / note / desc_zh / source |
| `data/csv/ch01_intents.csv` | 16 | intent_class / intent_type / loc_prefix / title_zh / desc_zh / uses_in_monsters / example_monsters / sprite（只记路径）/ source |

脚本 `scripts/ch01_extract.py` 是纯正则静态抽取：`primary` 和 `duration_model` 是按重写的 Hook 和衰减写法得出的**启发式分类**，个别能力（比如 Trigger 写在辅助方法里的中毒）要回源码核对；`src_*` 统计的是"文件里出现该类名"，不区分施加给自己还是施加给敌人。
