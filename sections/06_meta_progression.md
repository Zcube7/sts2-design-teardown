# 第 06 章 局外成长与长线目标

> 版本 v0.111.1（2026-11-13）。出处路径相对 `csharp/sts2_src/`；本地化相对 `data/pck_text/`。
> 本章新表：`data/csv/ch06_epochs.csv`（57 个纪元）、`data/csv/ch06_ascension.csv`（10 级进阶）、`data/csv/ch06_achievements_badges.csv`（33 个成就 + 25 个徽章条目）。
> 可重跑脚本：`scripts/ch06_epochs.py`、`scripts/ch06_tables.py`、`scripts/ch06_ascension_scan.py`。

---

## 0. 结论速览

1. **局外成长只有一条主轴：时间线（Timeline）**。57 个纪元（Epoch，简中叫「历史节点」）是唯一的内容解锁载体：角色、卡、遗物、药水、事件、第一幕备选的暗港、3 个先古之民、每日/自定义模式都挂在纪元上。没有金币、经验、天赋树这类可花费的局外货币；唯一跨局累计并能换到东西的点数是旺购积分（WongoPoints）：第 2 幕事件「欢迎来到旺购百货」购物攒分、存进 progress.save，每满 2000 当场送一个「没有任何作用」的徽章遗物，不能花、也不解锁内容（见第 5 章）。（`MegaCrit.Sts2.Core.Timeline/EpochModel.cs`；`MegaCrit.Sts2.Core.Models.Events/WelcomeToWongos.cs:111-131`；`ProgressSaveManager.cs:229`）
2. **纪元分三条获取通道**：局中里程碑 25 个（打过某幕 Boss、累计杀 15 精英/15 Boss）、局后里程碑 13 个（打完一局、A1 通关、3 胜、全角色等），外加 18 个「积分条」通用解锁（每局结算分数累加）。另有 1 个连锁获得（揭示涅奥时送静默猎手）。（`MegaCrit.Sts2.Core.Saves.Managers/ProgressSaveManager.cs:341-597`；`EpochModel.cs:86-120`）
3. **「获得」不等于「生效」**：纪元要在时间线界面里**点一下揭示（Revealed）**，内容才进卡池。解锁判定只认 `EpochState.Revealed`（`MegaCrit.Sts2.Core.Unlocks/UnlockState.cs:150`）。有待揭示纪元且没有进行中的存档时，主菜单会**禁用单人、多人、图鉴**，时间线按钮可点并亮小红点（设置、退出等按钮不受影响）（`MegaCrit.Sts2.Core.Nodes.Screens.MainMenu/NMainMenu.cs:630-637`）。也就是说，每次解锁的演出玩家都得看完。
4. **积分条一局最多给 1 个解锁**：分数 = 楼层分 + 金币/100 + 精英×50 + Boss×100，再乘 (1+0.1×进阶)。超出当前档的分数会被压到「下一档门槛 −1」（代码注释：Score is too awesome. Disallow double unlock）。18 档门槛从 200 涨到 2500，合计 30,700 分。（`MegaCrit.Sts2.Core.Runs/ScoreUtility.cs:46-127`；`MegaCrit.Sts2.Core.Nodes.Screens.GameOverScreen/NGameOverScreen.cs:739-849`）
5. **每个角色有一套固定 7 节模板**（铁甲战士没有第 1 节）：①解锁角色 ②打过第 1 幕 Boss → 3 张卡 ③打过第 2 幕 Boss → 3 件遗物 ④打过第 3 幕 Boss → 3 瓶专属药水 + **开放该角色的进阶** ⑤累计杀 15 精英 → 3 张卡 ⑥累计杀 15 Boss → 3 件遗物 ⑦进阶 1 通关 → 3 张卡。按角色池算，每个角色 9 张卡（约 10%）、6 件专属遗物（除初始和商店遗物外全部）、3 瓶专属药水（全部）一开始是锁着的。
6. **进阶只有 10 级**，按角色分开记录 MaxAscension，在当前最高级获胜就 +1。前 7 级都是「资源」类削减（多精英、回血打 8 折、金币 ×0.75、少 1 个药水栏、开局带永恒诅咒、删牌涨价、稀有牌减半），第 8、9 级才加怪物血量和伤害，第 10 级是双 Boss。多人进阶是所有角色共用一条进度，大厅上限取全队最小值。（`MegaCrit.Sts2.Core.Entities.Ascension/`；`ProgressSaveManager.cs:805-839`）
7. **成就系统在这个版本里是空壳**：`AchievementsUtil.Unlock()` 函数体为空，平台策略写死为 `NullAchievementStrategy`，统计界面的成就页签被禁用；补丁说明 2026-02-26 写了「抢先体验期间暂时关闭成就」。现在给玩家的局外反馈靠**徽章**：23 个徽章（8 个分铜/银/金三档，其余 15 个固定单档），按角色累计次数，并且是每日排行榜的第三排序键。
8. **每日挑战和自定义模式都关掉了纪元/成就**（`GameMode != Standard`），两种模式还会**取代涅奥的开局祝福**：有修饰符时，涅奥只按顺序弹出修饰符选项（`MegaCrit.Sts2.Core.Models.Events/Neow.cs:218,286-297`）。但积分条那条路径没有做模式检查，源码注释自己写明了这一点（`MegaCrit.Sts2.Core.Saves/SaveManager.cs:1444-1447`）。
9. **用「打建筑师」做社区长线目标**：胜利横幅写的是「胜利……？」，本局分数会记作「对建筑师造成的伤害」，同时累计到个人总值和 Steam 全球统计（`ArchitectDamage`），结算界面显示「所有挑战者合力造成 X 点伤害，建筑师依然屹立不倒」。（`NGameOverScreen.cs:487-519`；`MegaCrit.Sts2.Core.Platform/StatsManager.cs`）
10. **和一代最大的不同**（与一代对比凭公开知识）：一代是「每个角色一条分数经验条，按档吐卡/遗物」。二代把解锁拆成「里程碑任务 + 通用积分条」两条线，再用一张有叙事的时间线串起来，并强制玩家揭示。积分条只给通用内容，角色内容全部绑在「打到哪一幕、杀了多少」这类可读的目标上。

---

## 1. 局外系统全景

### 1.1 存档里存了什么（progress.save）

`ProgressState` 是局外进度的运行时对象（`MegaCrit.Sts2.Core.Saves/ProgressState.cs:19-121`），按档案（profile）保存为 `progress.save`（`ProgressSaveManager.cs:35,60-63`）。

| 分类 | 字段 | 粒度 | 用途 |
|---|---|---|---|
| 纪元 | `Epochs`（每个纪元一个 `SerializableEpoch`：Id + State + ObtainDate） | 全局 | 时间线、所有内容解锁 |
| 积分条 | `CurrentScore`；`TotalUnlocks` 由已获得的通用纪元数推导，不单独存 | 全局 | 结算积分条 |
| 角色 | `CharacterStats`：TotalWins / TotalLosses / Playtime / MaxAscension / PreferredAscension / 当前与最佳连胜 / FastestWinTime / Badges | **按角色** | 进阶、统计页、徽章 |
| 多人进阶 | `MaxMultiplayerAscension` / `PreferredMultiplayerAscension` | 全局（所有角色共用） | 多人大厅 |
| 战斗记录 | `EncounterStats` / `EnemyStats`：每个遭遇/怪物 × 角色的胜负 | 按角色 | 纪元 5/6 计数、怪物图鉴、首局 Boss 发现顺序 |
| 先古之民 | `AncientStats`：每个 Ancient × 角色的胜负 | 按角色 | 达弗纪元、统计 |
| 卡牌 | `CardStats`：选取/跳过/带着赢/带着输 | 全局 | 卡牌库里的统计 |
| 已发现 | `DiscoveredCards/Relics/Potions/Events/Acts` | 全局 | 图鉴的「已发现」状态 |
| 引导 | `FtueCompleted`（字符串集合）、`EnableFtues` | 全局 | 新手引导 |
| 成就 | `UnlockedAchievements`（成就 → 时间戳） | 全局 | 目前用不到（见 §4） |
| 趣味累计 | TotalPlaytime / FloorsClimbed / ArchitectDamage / WongoPoints / TestSubjectKills | 全局 | 总时长进统计页；ArchitectDamage 进胜利结算文案；WongoPoints 每满 2000 在旺购事件里送一个无效果徽章遗物（`Models.Events/WelcomeToWongos.cs:111-131`）；TestSubjectKills 是 Boss「实验体 #C{N}」名字里的编号（`Models.Monsters/TestSubject.cs:72`）；FloorsClimbed 目前没有读取处 |

说明：
- 开局默认只有铁甲战士，新档会把铁甲战士的起始牌和起始遗物直接记为「已发现」（`ProgressSaveManager.cs:84-96`）。
- `TotalUnlocks` 不单独存储，从纪元本身推导出来（`ProgressState.cs:124-133`）。代码注释提到 PRG-7234：以前单独存一个计数器，计数器涨了但纪元没发，那个纪元就再也拿不到了。

### 1.2 三种游戏模式的权限

`GameModeExtension.AreAchievementsAndEpochsLocked()` 的实现只有一句 `gameMode != GameMode.Standard`（`MegaCrit.Sts2.Core.Runs/GameModeExtension.cs:9-12`）。

| 进度项 | 标准 Standard | 每日 Daily | 自定义 Custom | 出处 |
|---|---|---|---|---|
| 里程碑纪元（局中/局后） | ✔ | ✘ | ✘ | `ProgressSaveManager.cs:611,636` |
| 积分条纪元 | ✔ | **✔（没检查模式）** | **✔（没检查模式）** | `SaveManager.cs:1444-1447` 注释；`NGameOverScreen.cs:608,739` |
| 胜负、连胜、进阶 +1 | ✔ | ✘ | ✘ | `ProgressSaveManager.cs:238-263` |
| 卡牌选取统计、先古之民统计 | ✔ | ✘ | ✘ | `ProgressSaveManager.cs:288-332` |
| 徽章写入存档 | ✔ | ✘ | ✘ | `NGameOverScreen.cs:682-686` |
| 总时长、楼层数、已见事件/幕 | ✔ | ✔ | ✔ | `ProgressSaveManager.cs:215-231,280-287` |
| 首局 Boss 发现顺序（教学修正） | ✔ | ✘ | ✘ | `MegaCrit.Sts2.Core.Runs/RunManager.cs:780-797` |

界面上也有提示：顶栏的锁形图标（`MegaCrit.Sts2.Core.Nodes.CommonUi/NTopBar.cs:326`），角色头像悬浮提示里会写「无法获得成就」（`MegaCrit.Sts2.Core.Helpers/AscensionHelper.cs` GetHoverTip）。补丁说明 2026-03-19 写了「Daily/Custom 不再能获得纪元」，但积分条这条路径没有跟着改（见 §12 待核实）。

---

## 2. 时间线（Timeline）

### 2.1 概念对照

| 概念 | 代码 | 数量 | 说明 |
|---|---|---|---|
| 纪元 / 历史节点 | `EpochModel` 子类 | 57 | 每个纪元有 Id、所属时代、行号、所属故事和解锁内容 |
| 时代 | `EpochEra` 枚举 | 26 个值，分 7 组 | 决定在时间线上的列；枚举值就是「年份」 |
| 行 | `EraPosition` | 0-4 | 列内的行，0 在最下面（`EpochModel.cs` 注释） |
| 故事 | `StoryModel` 子类 | 8 | 把纪元串成可以翻页阅读的章节，**章节顺序和解锁顺序无关** |
| 槽位展开 | `GetTimelineExpansion()` | — | 揭示一个纪元时，会在时间线上开出哪些新槽位 |

代码里有一条硬约束：「每个纪元都必须解锁点东西，否则同时放入两个纪元会出错」（`EpochModel.cs:374-377`）。所以 Act2B/Act3B 两个占位纪元也要弹一条「将在抢先体验期间揭晓」的文字。

### 2.2 纪元状态机

`EpochState`（`MegaCrit.Sts2.Core.Saves/EpochState.cs`）：

```
None → NoSlot → NotObtained ──满足条件──→ Obtained ──玩家点击──→ Revealed（生效）
                      ↑                       ↑
     条件先满足、槽位还没开：ObtainedNoSlot ──父纪元揭示、槽位打开──┘
```

- **NotObtained**：槽位已经出现在时间线上（锁链和模糊预览），悬浮提示显示 `unlockInfo` 写的获取条件。
- **ObtainedNoSlot**：条件已经满足但槽位还没开，比如积分条先发了一个纪元，它的父纪元还没被揭示。父纪元揭示后会升为 Obtained（`ProgressState.cs:383-400`）。
- **Revealed**：玩家点击后播放解锁演出，内容生效（`MegaCrit.Sts2.Core.Nodes.Screens.Timeline/NEpochSlot.cs:348-388`）。
- 局内拿到的纪元会进 `Player.DiscoveredEpochs`，并播放 `NGainEpochVfx`，但**本局不会用上**：一局的解锁状态在开局时就固定在 `Player.UnlockState` 里了（`UnlockState.cs` 类注释）。
- 揭示时会上传 `EpochMetric`（纪元 Id、总局数、总时长、存档里的纪元条目数——`Progress.Epochs.Count`，含还没获得的槽位）到 `sts2-metric-upload.megacrit.com/record_epoch/`（`MegaCrit.Sts2.Core.Runs.Metrics/MetricUtilities.cs:224-239`）。开发方可以直接看到「玩家平均第几局、玩了多久才揭示某个纪元」，用来调节奏（推断）。

### 2.3 获取通道与条件（全部源码核对）

| 通道 | 条件 | 涉及纪元 | 出处 |
|---|---|---|---|
| 局后：任意一局结束 | 胜、负、放弃都算（主菜单放弃也走同一个更新函数） | 涅奥 NEOW | `ProgressSaveManager.cs:343`；`NMainMenu.cs:750` |
| 连锁 | 揭示涅奥时，把静默猎手 1 直接设为 ObtainedNoSlot | SILENT1 | `MegaCrit.Sts2.Core.Timeline.Epochs/NeowEpoch.cs` QueueUnlocks |
| 局后：用某角色打完一局 | 静默猎手→储君1、储君→亡灵契约师1、亡灵契约师→故障机器人1 | REGENT1 / NECROBINDER1 / DEFECT1 | `ProgressSaveManager.cs:365-374` |
| 局中：首次打过第 N 幕 Boss | 第 1/2/3 幕分别给该角色的 2/3/4 号纪元，按角色名拼出 Id | X2 / X3 / X4 | `ProgressSaveManager.cs:564-597,765-768` |
| 局中：累计 15 精英 | 该角色所有精英遭遇的胜场合计 ≥15 | X5 | `ProgressSaveManager.cs:411-482` |
| 局中：累计 15 Boss | 该角色所有 Boss 遭遇的胜场合计 ≥15 | X6 | `ProgressSaveManager.cs:488-558` |
| 局后：进阶 1 获胜 | `run.Ascension == 1` 且胜利 | X7 | `ProgressSaveManager.cs:393-405` |
| 局后：累计 3 胜 | 本局胜利，且所有角色合计胜场 ≥3 | 种子（自定义+种子） | `ProgressSaveManager.cs:376-387` |
| 局后：全角色 | `CharacterStats` 条目数 ≥5 | 欧洛巴斯 OROBAS | `ProgressSaveManager.cs:351-354` |
| 局后：全角色 + 胜利 | 同上，并且本局胜利 | 每日挑战 DAILY_RUN | `ProgressSaveManager.cs:346-350` |
| 局后：见过所有先古之民 | 除达弗以外，`ModelDb.AllAncients` 全部在 AncientStats 里有记录 | 达弗 DARV | `ProgressSaveManager.cs:355-358` |
| 积分条 | 按 `AgnosticUnlocks` 顺序，发第一个还没拿到的 | 18 个通用纪元 | `EpochModel.cs:86-120`；`ProgressState.cs:327-336` |

细节：
- **静默猎手 1 的文案和代码对不上**：本地化写「以铁甲战士完成一局游戏」，代码里是「揭示涅奥时连带获得」。不过涅奥本身就是「打完任意一局」给的，第一局又只能用铁甲战士，所以实际效果一样（`localization/zhs/epochs.json` SILENT1_EPOCH.unlockInfo）。
- **「首次」靠去重实现**：每次打过 Boss 都会尝试发纪元，已经有了就返回 false（`ProgressSaveManager.cs:658-665`）。第 1 幕选暗港也算第 1 幕。
- **「所有角色都玩过」的判定偏宽松（推断，未实测）**：`CharacterStats` 条目由 `GetOrCreateCharacterStats` 创建，而单人大厅**只要切换角色**就会调用它（`MegaCrit.Sts2.Core.Multiplayer.Game.Lobby/StartRunLobby.cs:518`）。所以实际条件更接近「所有角色都在选角界面被点过」。
- `Ironclad7Epoch` 的旧注释写着「解锁击杀建筑师的手段 + 3 张卡」（`ProgressSaveManager.cs:390-392`），现在的实现只给 3 张卡。

### 2.4 槽位展开树（时间线怎么一点点长出来）

槽位只在父纪元被**揭示**后才出现。根节点是涅奥（第一次打开时间线时由教程放上去，`NTimelineScreen.cs:526-543`）。用 `ch06_epochs.csv` 的 `expands_slots` 列可以还原出下面这棵树：

```
涅奥 NEOW（首局结束即得）
├─ 铁甲战士 2-7（6 槽）
├─ 静默猎手 1 ─┬─ 静默猎手 2-7
│              └─ 储君 1 ─┬─ 储君 2-7
│                         └─ 亡灵契约师 1 ─┬─ 亡灵契约师 2-7
│                                          └─ 故障机器人 1 ── 故障机器人 2-7
├─ 种子（自定义模式） / 每日挑战 / 欧洛巴斯 / 达弗
└─ 先子星 Colorless1【积分条 1】
   ├─ 涂鸦 Relic1【2】   ├─ 开放 Potion1【3】
   └─ 暗港 Underdocks【4】
      ├─ 建筑师 Colorless2【5】  ├─ 先古之民 Relic2【6】
      └─ 宁静 Potion2【7】
         ├─ 某处 Act2B【8】  ├─ 两个反叛者 Colorless3【9】
         └─ 文明 Relic3【10】
            ├─ 别处 Act3B【11】  ├─ 沉睡 Colorless4【12】
            └─ 后果 Relic4【13】
               ├─ 邪教徒们 Event1【14】 ├─ 买点什么吧！ Colorless5【15】
               └─ 醒来 Relic5【16】
                  ├─ 他们回来了 Event2【17】
                  └─ 高塔 Event3【18】
```

设计意图（推断）：
- 积分条那条线是「链式」的：每一档的槽位都由前面某一档打开。所以玩家在时间线上总能看到「下一个是什么」，但看不到再往后的。
- 角色线是「一次全开」：揭示角色 1 就把 2-7 号 6 个槽位都亮出来，玩家能一眼看到这个角色的全部 6 个目标。
- 角色解锁是串行的（静默猎手 → 储君 → 亡灵契约师 → 故障机器人），每个角色的「1 号」槽位都挂在上一个角色的 1 号下面。

### 2.5 揭示流程：强制观看

| 步骤 | 行为 | 出处 |
|---|---|---|
| 1. 第一局结束 | 获得涅奥；主菜单检测到有可揭示的纪元并且没有进行中的存档 → **单人/多人/图鉴按钮禁用**，时间线可点并显示小红点（设置、退出不受影响） | `NMainMenu.cs:630-637` |
| 2. 第一次进时间线 | 先播放 `NTimelineTutorial`，结束后才放出涅奥槽位 | `NTimelineScreen.cs:510-543` |
| 3. 点击发光槽位 | 状态改为 Revealed → 打开检视页（传说文本 + 「解锁」按钮）→ `QueueUnlocks()` 排队播放解锁界面（卡牌/遗物/药水/角色/杂项/时间线拓展） | `NEpochSlot.cs:377-388`；`NEpochInspectScreen.cs:522-526`；`Nodes.Screens.Timeline.UnlockScreens/*` |
| 4. 解锁角色 | 写入 `PendingCharacterUnlock`，下次进选角界面播放角色解锁动画 | `Silent1Epoch.cs`；`NCharacterSelectScreen.cs:587-631` |
| 5. 局中途 | 有进行中的存档**且**有待揭示纪元时，时间线按钮被禁用（要先打完这一局才能揭示）；有存档但没有待揭示纪元时，时间线照常可进 | `NMainMenu.cs:640-656` |

**设计观察**：强制揭示把「解锁」从结算界面上的一行字，变成了主菜单里一个必须去做的动作，每次都带传说文本、画像和解锁卡面。代价是玩家一次连续开好几个纪元时会比较啰嗦（补丁说明 2025-04-17「同时获得多个纪元时，每个间隔 3 秒」）。

### 2.6 积分条（通用解锁）

**分数公式**（`ScoreUtility.cs:46-127`）：

| 项 | 计算 |
|---|---|
| 楼层 | Σ 第 i 幕经过的点数 × 10 × i（第 1 幕每点 10、第 2 幕 20、第 3 幕 30） |
| 金币 | 全队获得金币总和 ÷ (100 × 人数) |
| 精英 | 击杀数 × 50（死于精英那场不算） |
| Boss | 击杀数 × 100（死于 Boss 那场不算） |
| 进阶倍率 | 总分 × (1 + 0.1 × 进阶等级)，A10 为 ×2.0 |

**18 档门槛**（`EpochModel.cs:86-120`）：

| 档 | 门槛 | 纪元 | 解锁内容 |
|---|---|---|---|
| 1 | 200 | 先子星 Colorless1 | 无色牌：自动化、熵、横祸 |
| 2 | 500 | 涂鸦 Relic1 | 遗物：不安油灯、骇人头盔、爬行动物饰品 |
| 3 | 750 | 开放 Potion1 | 药水：甲虫汁、马萨雷斯的赠礼、预知之滴 |
| 4 | 1000 | 暗港 Underdocks | 第 1 幕可以选暗港（`Models.Acts/Underdocks.cs:107-110`） |
| 5 | 1250 | 建筑师 Colorless2 | 永恒铠甲、大奖、准备时间 |
| 6 | 1500 | 先古之民 Relic2 | 五轮书、冰淇淋、锁镰 |
| 7 | 1600 | 宁静 Potion2 | 消亡粉末、瓶中船、癫狂之触 |
| 8 | 1700 | 某处 Act2B | **占位**：「这个地点将会在抢先体验期间揭晓……」，代码里没有任何引用 |
| 9 | 1800 | 两个反叛者 Colorless3 | 撕碎、狠揍、非凡技艺 |
| 10 | 1900 | 文明 Relic3 | 烦人机关盒、波纹水盆、节日拉炮 |
| 11 | 2000 | 别处 Act3B | **占位**（第 3 幕 B 面） |
| 12 | 2100 | 沉睡 Colorless4 | 炼制药水、怀旧、潦草急就 |
| 13 | 2200 | 后果 Relic4 | 微型大炮、钨合金棍、白星 |
| 14 | 2300 | 邪教徒们 Event1 | 事件：垃圾堆（`ActModel.cs:331-357` 从事件池里剔除） |
| 15 | 2400 | 买点什么吧！ Colorless5 | 飞溅、天选、劫难 |
| 16 | 2500 | 醒来 Relic5 | 小邮箱、金纸、律动残余 |
| 17 | 2500 | 他们回来了 Event2 | 事件：镜中倒影 |
| 18 | 2500 | 高塔 Event3 | 事件：色彩哲学家 |

**结算规则**（`NGameOverScreen.cs:739-849`）：
- 每档门槛单独计，满档后 CurrentScore 扣掉门槛，余数带到下一档。
- **一局最多升 1 档**：余数 ≥ 下一档门槛时，存成「下一档门槛 −1」。也就是说，再高的分数也只能让下一局「差 1 分升档」。
- 18 档全部拿到后积分条隐藏，结算显示「所有历史节点已解锁！」。
- 门槛合计 30,700 分，**最少要 18 局**。

**节奏估算（推断，按每幕约 15 个点估）**：

| 局况 | 估算分数 | 大概相当于 |
|---|---|---|
| 第 1 幕中途死亡（8 点、1 精英） | 80 + 50 ≈ 130 | 两局左右凑够第 1 档 200 |
| 第 2 幕 Boss 前死亡 | 150 + 280 + 2×50 + 100 ≈ 630 | 前期大约 1 局 1 档 |
| A0 通关 | 900 + 4×50 + 3×100 + ~7 ≈ 1400 | 后期 2500 的档大约要 2 局 |
| A10 通关 | 约 2800 | 后期 1 局 1 档（但被「一局最多 1 档」卡住） |

**设计观察**：
- 前 4 档门槛很低（200/500/750/1000），新手哪怕连败也能每一两局揭示一个东西，第 4 档就开出新的第 1 幕（暗港），保证早期每局都「有东西拿」。
- 后 10 档每档只多 100，用到 2500 封顶。再叠上「一局最多 1 档」，高手也没法几局刷完，通用内容的投放速度大致锁在**每局最多 1 个**。
- 积分条的内容全是**通用**的（无色牌、共享遗物/药水、事件、幕），跟用哪个角色无关。角色内容全部走里程碑。两条线互不干扰：玩家换角色不会丢积分进度，专精一个角色也不会把通用内容刷完。

### 2.7 角色纪元矩阵（34 个）

模板（铁甲战士没有 1 号，开局就能用）：

| 节 | 获取条件 | 内容类型 | 生效处 |
|---|---|---|---|
| 1 | 用上一个角色打完一局（静默猎手例外，见 §2.3） | 角色 | `UnlockState.Characters`（`UnlockState.cs:57-78`） |
| 2 | 首次打过第 1 幕 Boss | 3 张卡 | `Models.CardPools/<角色>CardPool.cs` FilterThroughEpochs |
| 3 | 首次打过第 2 幕 Boss | 3 件专属遗物 | `Models.RelicPools/<角色>RelicPool.cs:35` |
| 4 | 首次打过第 3 幕 Boss | 3 瓶专属药水 + **开放该角色进阶** | `Models.PotionPools/<角色>PotionPool.cs:27`；`StartRunLobby.cs:520-545,569-593` |
| 5 | 累计杀 15 精英 | 3 张卡 | 同 2 |
| 6 | 累计杀 15 Boss | 3 件专属遗物 | 同 3 |
| 7 | 进阶 1 通关 | 3 张卡 | 同 2 |

具体内容（`ch06_epochs.csv`；按源码声明顺序列出，没有按稀有度排序；游戏内解锁文字会按稀有度重排，`EpochModel.cs:437-446`）：

| 角色 | 1 | 2（卡） | 3（遗物） | 4（药水+进阶） | 5（卡） | 6（遗物） | 7（卡） |
|---|---|---|---|---|---|---|---|
| 铁甲战士 | 初始可用 | 熔融之拳、残酷、主宰 | 红头骨、纸蛙、损毁头盔 | 鲜血药水、士兵炖汤、灰水 | 余烬、契约终结、战鼓 | 自成型黏土、卡戎之灰、恶魔之舌 | 血墙、扯碎、狱火 |
| 静默猎手 | 角色 | 蛇咬、咕嘟冒泡、触媒 | 结实绷带、纸鹤、铜钹 | 毒药水、罐装幽灵、狡诈药水 | 本能反应、谋划专家、手上技法 | 扭曲漏斗、异蛇头骨、螺线飞镖 | 隐秘匕首、墨之刃、幻影之刃 |
| 储君 | 角色 | 战利品、剑圣、熔炉 | 击剑指南、星系尘埃、月亮糕点 | 星星药水、宇宙药剂、王之勇气 | 下去！、武器库、超质量体 | 君王矿石、迷你储君、橙色团块 | 星星点点、天际钻头、月面射击 |
| 亡灵契约师 | 角色 | 鞭打、湮灭、倒数计时 | 骨笛、葬礼面具、修书小刀 | 灾厄药水、尸鬼瓮、骨头酿 | 来生、牺牲、钙化 | 象牙麻将牌、大帽子、书签 | 雕琢打击、刺破帷幕、女妖之嚎 |
| 故障机器人 | 角色 | 循环、空值、吞噬暗影 | 数据磁盘、共生病毒、节拍器 | 集中药水、黑暗精华、扩容药水 | 弹幕齐射、散射炮、烟囱 | 镀金缆线、情感芯片、能量电池 | 内核加速、内存清理、螺旋钻击 |

**锁了多少**（对照 `data/csv/cards.csv` / `relics.csv` / `potions.csv` 的池子）：

| 内容 | 开局锁住 | 池子总量 | 占比 |
|---|---|---|---|
| 每个角色的卡 | 9（纪元 2/5/7） | 90-91 | 约 10% |
| 每个角色的专属遗物 | 6（纪元 3/6） | 8（另外 2 件是初始遗物和商店遗物） | **能随机掉落的专属遗物全部锁住** |
| 每个角色的专属药水 | 3（纪元 4，普通/罕见/稀有各 1） | 3 | 100% |
| 无色牌 | 15（Colorless1-5） | 65 | 23% |
| 共享遗物 | 15（Relic1-5） | 115 | 13% |
| 共享药水 | 6（Potion1-2） | 45 | 13% |
| 事件 | 3 | 68 | 4% |
| 先古之民 | 涅奥（开局祝福）、欧洛巴斯（第 2 幕）、达弗（共享） | 8（DeprecatedAncientEvent 是占位，不计） | 3/8 |

（与第 3 章 `data/csv/ch03_relic_taxonomy.csv` 的 unlock_epoch 列逐件对过，45 件纪元遗物完全一致。通用药水：Potion1 的 3 瓶都是稀有，Potion2 是罕见/稀有/罕见。数量来源：`SaveManager.cs:1281-1384` 的 `GetCardUnlockEpochIds` 20 个 ×3 = 60 张卡、`GetRelicUnlockEpochIds` 15 个 ×3 = 45 件遗物、`GetPotionUnlockEpochIds` 7 个 ×3 = 21 瓶药水，统计页直接显示这三个分母。）

**设计观察**：
- **卡牌只锁 10%**，玩家第一局就能体验到角色的完整机制。锁住的是「换口味」的牌，而遗物和药水这种**改变局内体验的东西才是解锁的主菜**。
- **4 号纪元同时管专属药水和进阶入口**：「第一次通关」这个时刻同时给新道具和新难度，由选角界面的进阶首次提示弹窗承接（§8）。
- **5/6 号的「15 次累计」是按角色算的长线目标**：要大约 5 局通关（每局 3 个 Boss）才能拿到 6 号，这样玩家会在一个角色身上多停留几局，而不是解锁下一个角色就跑。

### 2.8 其他 5 个特殊纪元

| 纪元 | 条件 | 解锁 | 生效处 |
|---|---|---|---|
| 涅奥 NEOW | 打完任意一局 | 涅奥会在每局开局迎接你（开局祝福）；同时开出 12 个槽位 | `Models.Acts/Overgrowth.cs:99-106`、`Underdocks.cs:92-99` 没揭示就把涅奥移出先古之民池；`RunManager.cs:589` 记录 StartedWithNeow |
| 种子 CUSTOM_AND_SEEDS | 累计 3 胜 | 自定义模式 + 自设种子 | `NSingleplayerSubmenu.cs:142`、`NMultiplayerHostSubmenu.cs:161` |
| 每日挑战 DAILY_RUN | 全角色 + 胜利 | 每日挑战 | `NSingleplayerSubmenu.cs:141` |
| 欧洛巴斯 OROBAS | 全角色 | 第 2 幕巢穴的先古之民池加入欧洛巴斯 | `Models.Acts/Hive.cs:97-104` |
| 达弗 DARV | 见过所有其他先古之民 | 共享先古之民池加入达弗 | `UnlockState.cs:83-94` |

**第一局没有涅奥**：涅奥纪元揭示前，第 1 幕的先古之民池里没有涅奥。新玩家的第一局是「纯净」的高塔，第二局才出现开局祝福（细节见第 5 章）。

### 2.9 故事（Story）与时代（Era）

故事是「阅读顺序」，跟解锁顺序无关，在检视页里可以按章节翻页（`MegaCrit.Sts2.Core.Timeline/StoryModel.cs` PrevChapter/NextChapter 会跳过没揭示的章节）：

| 故事（STORY_*） | 章数 | 章节顺序（第 1 章 → 最后） |
|---|---|---|
| 杰作 Magnum Opus | 9 | Colorless1 → Relic1 → Colorless2 → 种子 → Relic2 → Colorless3 → Colorless4 → Relic4 → Event3 |
| 重新开放 The Reopening | 6 | Potion2 → Relic5 → Relic3 → Potion1 → 涅奥 → Event2 |
| 高塔故事 Tales From The Spire | 6 | Colorless5 → 欧洛巴斯 → Event1 → 暗港 → 达弗 → 每日挑战 |
| 铁甲战士 | 6 | 4 → 3 → 2 → 5 → 6 → 7 |
| 静默猎手 | 7 | 6 → 4 → 5 → 2 → 3 → 1 → 7 |
| 储君 | 7 | 6 → 1 → 5 → 2 → 3 → 4 → 7 |
| 亡灵契约师 | 7 | 2 → 3 → 4 → 5 → 6 → 1 → 7 |
| 故障机器人 | 7 | 6 → 3 → 4 → 5 → 1 → 2 → 7 |

（Act2B、Act3B 不属于任何故事。出处：`MegaCrit.Sts2.Core.Timeline.Stories/*.cs`。）

时代（`EpochEra` 枚举值 = 年份；`localization/zhs/eras.json`）：

| 时代组 | 年份 | 简中 | 纪元数 |
|---|---|---|---|
| Prehistoria 0-2 | −20000（显示「？？？」） | 史前 | 4 |
| Seeds 0-3 | 0 | 种子 | 8 |
| Blight 0-2 | 1201 | 感染 | 8 |
| Flourish 0-3 | 1800 | 兴盛 | 14 |
| Invitation 0-7 | 2733 | 门扉 | 23 |
| Peace 0-1 | 3000 | 终结 | **0（预留）** |
| FarFuture 0-1 | 10000 | 无本地化 | **0（预留）** |

**设计观察**：
- 「获取顺序」和「时间线位置」是两套坐标。玩家按游戏进度解锁，但纪元落在时间线上的位置是按世界史排的，所以解锁的过程像在拼一段被打乱的历史。比如静默猎手 6 号落在「史前」，故障机器人 1 号落在「门扉」。
- 「终结」和「遥远未来」两个时代一个纪元都没有，加上成就文本里的「完成第四阶段 / 真结局」，可以推断正式版会在时间线末端补上结局内容（推断）。

### 2.10 多人模式下的解锁

- **取并集**：多人局的 `RunState.UnlockState` 是全队所有人已揭示纪元的并集（`UnlockState.cs:157-171`）。有一个人解锁了，全队这一局都能刷到。
- 每个玩家自己的奖励、药水生成用自己的 `Player.UnlockState`，先古之民生成用全队的并集（`UnlockState.cs` 类注释）。
- 代码注释里承认一个漏洞：联机每日挑战可以让玩家用自己没解锁的角色，于是可能获得一个在自己时间线上看不到的纪元。`GetRevealableEpochs()` 用 BFS 从涅奥出发，把这类「够不着」的纪元过滤掉（`ProgressSaveManager.cs:681-737`）。

---

## 3. 进阶（Ascension）

### 3.1 十级规则（`ch06_ascension.csv`）

进阶是累进的：`HasLevel(level) = 当前等级 ≥ level`（`AscensionManager.cs:44-47`）。`GetValueIfAscension(级别, 进阶值, 普通值)` 的**第二个参数是进阶值**。

| 级 | 名称（类名） | 玩家看到的描述 | 实际实现与数值 | 出处 |
|---|---|---|---|---|
| 1 | 精英蜂拥（SwarmingElites） | 精英更频繁 | 每幕地图的精英点数 5 → round(5×1.6) = **8** | `MegaCrit.Sts2.Core.Map/MapPointTypeCounts.cs:15` |
| 2 | 旅途劳顿（WearyTraveler） | 先古之民只回复 80% 已损生命 | 进先古之民事件时回复「已损生命 ×0.8」。涅奥会**先把 HP 设为 0 再回复**，所以 A2 起**开局只有 80% 最大生命** | `Models/AncientEventModel.cs:176-189` |
| 3 | 贫穷（Poverty） | 敌人和宝箱掉的金币 −25% | 普通战 10-20、精英 35-45、Boss 100 的金币上下限 ×0.75；宝箱 42-52 ×0.75 | `Models/EncounterModel.cs:64-98`；`Multiplayer.Game/OneOffSynchronizer.cs:133-136` |
| 4 | 收紧腰带（TightBelt） | 药水栏 −1 | 开局药水栏 3 → **2** | `AscensionManager.cs:56-59`；`Entities.Players/Player.cs:28` |
| 5 | 进阶之灾（AscendersBane） | 开局被诅咒 | 牌组加 1 张「进阶之灾」：不能打出 + 虚无 + **永恒**（不能移除；只要在牌组里也不能变化），不可升级，不会被修饰符或战斗生成 | `AscensionManager.cs:60-65`；`Models.Cards/AscendersBane.cs`；`Models/CardModel.cs:738-751`（IsRemovable / IsTransformable） |
| 6 | 通货膨胀（Inflation） | 删牌更贵 | 商人删牌基础价 75 → **100**，每删一次涨价 25 → **50** | `Entities.Merchant/MerchantCardRemovalEntry.cs:20-22` |
| 7 | 稀缺（Scarcity） | 稀有牌和升级牌更少 | 稀有概率减半：普通战 3% → 1.49%、精英战 10% → 5%、商店 9% → 4.5%；普通牌是余量、相应提高（60 → 61.5%、50 → 55%、54 → 58.5%；代码里精英普通概率常量写成 0.549，但和另外两个普通概率常量一样从未被掷骰读取，见 §12 第 3 条）；稀有保底每次增长 0.01 → 0.005；奖励牌升级概率每幕加成 0.25 → **0.125** | `Odds/CardRarityOdds.cs:13-41`；`Factories/CardFactory.cs:23,296-300` |
| 8 | 强韧敌人（ToughEnemies） | 敌人更难杀 | 101 个怪物文件、173 处取值。其中 156 处 HP，进阶值/普通值中位数 **1.055**（中位数 +3 HP），范围 1.00-1.24；另有 17 处非 HP（覆甲、闪躲等） | `Models.Monsters/*`；统计 `scripts/ch06_ascension_scan.py` |
| 9 | 致命敌人（DeadlyEnemies） | 敌人更致命 | 96 个文件、227 处伤害/增益取值，中位数 **×1.143**（中位数 +1），范围 1.0-3.0 | 同上 |
| 10 | 双重 Boss（DoubleBoss） | 第 3 幕最后打两个 Boss | 最后一幕从本幕其他 Boss 里再抽 1 个当第二 Boss | `Runs/RunManager.cs:769-773` |

怪物逐个数值见第 4 章。

**设计观察**：
- **前 7 级全是「资源压力」，第 8 级才动怪物**。A1-A7 削的是玩家的经济（金币、药水栏、删牌、稀有牌、回血），敌人本身没变；A8/A9 加的数值也很克制（HP 中位数 +5.5%，伤害 +14%）。这跟补丁说明 2026-04-26 的表态一致：低进阶要更友好，高进阶慢慢变难，而且要逐步调。
- **开发者删掉了「改地图」的进阶**：A6 原来是 Gloom（更少休息处），2026-04-02 改成删牌涨价。理由原话大意是：改地图的进阶，玩家分不清是进阶造成的还是运气不好（`localization/eng/patch_notes/2026_04_02.md:16-18`）。**可借鉴**：难度旋钮要让玩家能感知、能归因。A1 精英蜂拥也改地图，但「精英变多」这个结果很直观。
- **A2 顺带削开局血量**：「先古之民回血打 8 折」配合涅奥的「先清零再回满」，一条规则同时管了开局 HP 和每幕开头的回血，规则面很省。

### 3.2 解锁与记录方式

| 项 | 规则 | 出处 |
|---|---|---|
| 单人：按角色记录 | `CharacterStats.MaxAscension`（0-10）和 `PreferredAscension`（上次选的等级） | `ProgressState.cs:854-906` |
| 单人：升级 | 标准模式单人**在当前最高等级获胜** → MaxAscension +1（上限 10），并把偏好等级设为新的最高级；不在最高级获胜不加 | `ProgressSaveManager.cs:805-819` |
| 单人：入口 | 还要求该角色的 **4 号纪元已揭示**，否则 MaxAscension 当 0 处理、进阶面板不可用 | `StartRunLobby.cs:520-545`；补丁说明 2025-07-24 |
| 实际节奏 | 首次通关会同时得到 4 号纪元和 MaxAscension = 1 → A1 通关拿 7 号纪元 → 之后每在最高级赢一局 +1。**最少 10 局胜利**才能玩到 A10 | 推断自上面两条 |
| 随机角色 | 上限取所有角色里的最高 MaxAscension | `StartRunLobby.cs:521-526,559-567` |
| 多人：共享进度 | `Progress.MaxMultiplayerAscension` 不分角色；多人在当前最高级获胜 +1 | `ProgressSaveManager.cs:825-839` |
| 多人：大厅上限 | 取全队成员 `maxMultiplayerAscensionUnlocked` 的**最小值** | `StartRunLobby.cs:294-306` |
| 每日挑战 | 进阶随机 0-10（`rng3.NextInt(0, 11)`），不看个人进度 | `Nodes.Screens.DailyRun/NDailyRunScreen.cs:479` |
| 自定义 | 走同一个大厅逻辑，单人上限跟角色走：自定义选角同样调用 `SetLocalCharacter` → `SetSingleplayerAscensionAfterCharacterChanged`，按该角色 MaxAscension 定上限，也要求 4 号纪元已揭示；多人自定义走全队最小值 | `Nodes.Screens.CustomRun/NCustomRunScreen.cs:632-647`；`StartRunLobby.cs:513-548,632-638` |
| 计分 | 结算分数 ×(1 + 0.1 × 进阶) | `ScoreUtility.cs:52` |
| 首次提示 | 单人：`ascension_singleplayer_ftue`，附注「A1 通关会解锁一个历史节点，更高等级完全可选」；多人：`ascension_multiplayer_ftue`，附注「多人进阶与单机分开，所有角色共用」 | `StartRunLobby.cs:549-556`；`NCharacterSelectScreen.cs:471`；`localization/zhs/ftues.json` |
| 胜利提示 | 结算横幅写「胜利……？」，在当前最高级（1-9）获胜时额外显示「解锁进阶 N+1！」 | `NGameOverScreen.cs:487-519` |

**设计观察**：「A1 给纪元，A2 以上不给任何东西」是刻意的分界：进阶 1 被当成「完整内容」的一部分（拿最后 3 张角色牌），往上纯粹是给愿意挑战的玩家。本地化的提示文案直接把这层意思讲明了。

### 3.3 进阶演化史（补丁说明摘要）

| 日期 | 变化 |
|---|---|
| 2024-10-17 / 10-24 | 首批 A1-A9：Burly Enemies、Greedy Shopkeeper、Weary Traveler、Ascender's Bane、Tough Enemies、Intruder Alert、Tight Belt、Unchantments |
| 2024-12-12 | 新增 Scarcity（A8）、Ancient's Scorn（A9）；Intruder Alert 废弃 |
| 2025-01-09 | **进阶改为按角色分别解锁**（原来是全局共用）；A1 改为 Mighty Bosses |
| 2025-07-24 | 进阶入口改为需要揭示纪元；角色专属药水锁进纪元 |
| 2025-09-25 | 新增 A10 Villainy（第 3 幕 Boss 获得新能力） |
| 2025-12-11 | 大调整：A4 Warden → Tight Belt，Scarcity A8 → A9，A8 改 Gloom，A3 改 Poverty，A10 → Ascender's Scorn |
| 2026-01-15 | A10 改为一代回归的双 Boss |
| 2026-04-02 | A6 从 Gloom 改为 Inflation（理由见 §3.1） |

来源：`localization/eng/patch_notes/` 对应日期的文件。进阶层级在两年里换过一半以上，说明 10 级这个框架是先定下来、再往里换内容的（推断）。

---

## 4. 成就与徽章

### 4.1 成就：EA 版整体关闭

| 证据 | 出处 |
|---|---|
| `AchievementsUtil.Unlock()` 函数体为空；平台策略写死 `new NullAchievementStrategy()` | `MegaCrit.Sts2.Core.Platform/AchievementsUtil.cs:16,30-32` |
| `AchievementsHelper` 的 4 个方法（局后检查、时间线完成、清空一幕所有敌人、Boss 击败后）全部为空 | `MegaCrit.Sts2.Core.Achievements/AchievementsHelper.cs` |
| 统计界面的「成就」页签 `Disable()` | `Nodes.Screens.StatsScreen/NStatsScreen.cs:151` |
| 补丁说明：2026-01-22「暂时移除部分成就」；2026-02-26「抢先体验期间暂时关闭成就」 | `patch_notes/2026_01_22.md:6`、`2026_02_26.md:5` |
| 历史：纪元**原先是通过成就揭示**的，2026-01-01 改为积分条 | `patch_notes/2026_01_01.md:6` |

成就的内容规模：`Achievement` 枚举里有 22 个值，本地化里另有 11 个枚举中没有的条目，合计 33 个。全表见 `ch06_achievements_badges.csv`。

| 类别 | 成就（简中标题） | 条件 | 状态 |
|---|---|---|---|
| 角色通关 ×5 | 铁甲战士 / 静默猎手 / 储君 / 亡灵契约师 / 故障机器人 | 用该角色通关 | 枚举在；判定写在空函数里 |
| 清空一幕的敌人 ×4 | 密林 / 暗港 / 巢穴 / 荣耀 | 打败该幕所有敌人 | 同上 |
| 杂项 | 小小开始（打败 1 个 Boss）、好多楼梯（累计 1 万层）、身无杂物（不拿遗物通关）、完美牌组（全部升级通关） | — | 同上 |
| 角色技巧 ×8 | 契约完成（一场战斗消耗 20 张）/ 最重之刃（单击 999）/ 安得奇巧（一张牌连锁 5 次奇巧）/ 几滴就好（中毒 99）/ 已经死了（灾厄 999）/ 喝奶补钙（奥斯提力量 50）/ 王者之刃（君王之剑 999）/ 群日凌空（20 辉星） | 见 csv | **有监听器** `Models.Achievements/Skill*.cs`，但最后调用的 Unlock 是空的 |
| 打牌真开心啊 | 一回合打出 20 张 | `Play20CardsSingleTurnAchievement.cs:24` | 同上 |
| 只有文本 ×11 | 恶魔/幽魂/帝王/巫妖/回响（各角色 A10）、收藏家/考古学家/探险家（发现所有卡/遗物/事件）、真结局（完成第 4 阶段）、历史学家（完成时间线）、永存者（完成其他所有成就） | — | 枚举里没有 |

**写法**：成就监听器是 `AchievementModel`，挂在战斗 Hook 上（和遗物、能力用同一套事件），用 `LocalContext.IsMine` 过滤成本机玩家（`MegaCrit.Sts2.Core.Models/AchievementModel.cs`；Hook 体系见第 1、7 章）。

### 4.2 徽章：一局一结算的「小成就」

徽章在结算界面颁发，按「角色 × 徽章 × 档位」累计次数，存在 `CharacterStats.Badges`（`NGameOverScreen.cs:675-721`）。
- `BadgeRarity` 有铜/银/金三档，注释写明：越难拿档位越高，**用于排行榜同分时的决胜**（`Models.Badges/BadgeRarity.cs`）。但实际的每日分数编码只用徽章**个数**，档位没有参与（`Runs/ScoreUtility.cs:150-157`），注释说的用法目前没有实现。
- 每个徽章有两个开关：RequiresWin（只有获胜才算）、MultiplayerOnly（只在多人局出现）（`Models.Badges/Badge.cs`）。

`BadgePool.CreateAll` 里共 23 个（`Models.Badges/BadgePool.cs`）：

| 徽章 | 条件 | 档位 | 要求获胜 | 仅多人 |
|---|---|---|---|---|
| 大牌组 BIG_DECK | 牌组张数 | 铜 ≥40 / 银 ≥60 / 金 ≥100 | ✔ | |
| 小牌组 TINY_DECK | 牌组张数 | 铜 ≤20 / 银 ≤10 / 金 ≤5 | ✔ | |
| 精英猎手 ELITE | 击杀精英数 | 铜 ≥3 / 银 ≥6 / 金 ≥9 | | |
| 吃饱 GLUTTON | 最大生命比初始多 | 铜 +15 / 银 +30 / 金 +50 | ✔ | |
| 好多好多钱 MONEY_MONEY | 结算时持有金币 | 铜 ≥200 / 银 ≥400 / 金 ≥600 | ✔ | |
| 完胜 PERFECT | 无伤击败 Boss 的场数 | 铜 1 / 银 2 / 金 ≥3 | | |
| 高速 SPEEDY | 通关用时 | 铜 ≤50 分 / 银 ≤40 分 / 金 ≤30 分 | ✔ | |
| 治愈者 HEALER | 休息处「愈合」盟友的次数 | 铜 1 / 银 2 / 金 ≥3 | | ✔ |
| 真理石板 TABLET | 最大生命恰好为 1 | 金 | ✔ | |
| 团队型选手 TEAM_PLAYER | 牌组里多人专属牌 ≥3 | 银 | | ✔ |
| 伤害第一 DAMAGE_LEADER | 全队造成伤害最多（第 1 幕至少走过 5 个点） | 铜 | | ✔ |
| 弱化专家 DEBUFFER | 全队施加减益最多（临时能力不算） | 铜 | | ✔ |
| 连连连连段攻击 CCCCOMBO | 一回合打出 20 张牌 | 铜 | | |
| 诅咒局！ CURSES | 牌组里诅咒牌 ≥5 | 铜 | ✔ | |
| 二蛇之眼 DOUBLE_SNECKO | 同时持有异蛇之眼和假异蛇之眼 | 铜 | | |
| 饥肠辘辘 FAMISHED | 最大生命 < 初始生命的一半 | 铜 | ✔ | |
| 宇宙 HIGHLANDER | 除基础牌外没有重复牌 | 铜 | ✔ | |
| 熟能生巧 HONED | 除基础牌外某张牌 ≥5 张 | 铜 | ✔ | |
| 我爱亮闪闪 ILIKESHINY | 遗物 ≥25 件 | 铜 | | |
| 感谢惠顾！ KACHING | 在商店累计花费 ≥1000 金币 | 铜 | | |
| 寻谜问道 MYSTERY_MACHINE | 进过 ≥15 个「?」房间 | 铜 | | |
| 休养生息 RESTFUL | 每个休息处都选了休息 | 铜 | ✔ | |
| 战斗不息 RESTLESS | 到过休息处但一次都没休息 | 铜 | ✔ | |

另有两个不在池里的：`Whomper`（势大力沉，单次攻击超过 100 伤害）有类，但 `IsObtained()` 恒为 false，也不在徽章池里，类注释写明「THIS BADGE IS CURRENTLY NOT IN USE」并附设计理由，是**弃用**而非待做（见第 08 章 §6.6）；`FAVORITE_CARD`（最爱好牌，一张牌打出超过 100 次）只有文本。目录里的 29 个文件 = 23 个徽章 + Whomper + 基类、池、档位枚举、2 个战斗监听器（CccComboModel、DebufferModel）。

**设计观察**：
- 徽章是成就关闭期间的替代品，而且**每局都会重新结算**，不是「拿过一次就没了」。成对出现的「大牌组 / 小牌组」「休养生息 / 战斗不息」「宇宙 / 熟能生巧」等于是官方给出的几种「玩法挑战」，变相鼓励玩家走极端路线。
- 多人局有 4 个专属徽章（伤害第一、弱化专家、治愈者、团队型选手），给队伍里不同分工的人都留了表彰。

---

## 5. 每日挑战（Daily）

| 项 | 规则 | 出处 |
|---|---|---|
| 解锁 | 每日挑战纪元（全角色 + 一次胜利） | §2.8 |
| 时间 | 先向 MegaCrit 时间服务器取时间，失败时用本地 UTC 时间 | `NDailyRunScreen.cs:403-445`；`Daily/TimeServer.cs` |
| 种子 | 用 `dd_MM_yyyy` 的哈希建主随机数，再派生出 3 条子随机数；游戏种子是 `dd_MM_yyyy_{人数}p` | `NDailyRunScreen.cs:460-469` |
| 角色 | 按玩家顺序从 5 个角色中随机，**不看个人解锁** | `NDailyRunScreen.cs:471-478` |
| 进阶 | 随机 0-10 | `NDailyRunScreen.cs:479` |
| 修饰符 | 2 个正面 + 1 个负面（`Pick2Good1Bad`）；如果抽到「某角色卡牌」修饰符，会避开本局玩家已在用的角色 | `Models/ModifierModel.cs` Pick2Good1Bad |
| 人数 | 最多 4 人，排行榜按人数分开 | `NDailyRunScreen.cs:389`；`Daily/DailyRunUtility.cs:61-70` |
| 排行榜名 | `YYYY_MM_DD_{N}p`，测试分支加 `_BETA` | `DailyRunUtility.cs:61-70` |
| 只传一次 | 队伍里任何一人已经传过当天的分数，就不再上传 | `DailyRunUtility.cs:17-49` |
| 放弃也上传 | 从主菜单放弃每日局，按失败计分上传 | `NMainMenu.cs:752-756` |
| 每日分数编码 | 胜利(2)/失败(1) × 1e8 + 楼层(≤99) × 1e6 + 徽章数(≤99) × 1e4 + (9999 − 用时秒数) | `ScoreUtility.cs:149-157` |
| 联机客户端 | 客户端上传哨兵值 −999999999，由主机带全队 ID 上传真实分数 | `ScoreUtility.cs` clientScore；`RunManager.cs:1690-1700` |
| 局外进度 | 不给纪元、进阶、徽章写入；开局没有涅奥祝福（被修饰符选项取代） | §1.2；`Neow.cs:218,286-297` |

**设计观察**：排行榜的排序键是 **胜负 → 楼层 → 徽章数 → 速度**。徽章数排在速度前面，等于告诉玩家「有花样的通关比单纯快更值钱」。全球玩家同一天同种子、同角色、同进阶、同修饰符，靠这套编码把四个维度压进 Steam 排行榜的一个 int 里。

---

## 6. 自定义模式与 17 个修饰符

### 6.1 自定义模式

- 解锁：种子纪元（累计 3 胜）。可以设置角色、进阶、种子、任意修饰符组合；「随机」按钮用和每日挑战相同的 `Pick2Good1Bad` 抽一组（`NCustomRunScreen.cs:495-506`）。
- 支持单人和多人（`NCustomRunScreen.cs:364-399`）。
- 修饰符列表 = 9 个正面 + 7 个负面。「某角色卡牌」会按 5 个角色展开成 5 个勾选项（`Nodes.Screens.MainMenu/NCustomRunModifiersList.cs:164-207`）。
- 同样不给纪元、成就、胜负记录。

### 6.2 修饰符一览（`data/csv/modifiers.csv` + 源码核对）

修饰符是「整局存在的模型」，和遗物、能力一样接收全部 Hook（`Models/ModifierModel.cs`：`ShouldReceiveCombatHooks => true`）。

| 类别 | 修饰符 | 实现要点 | 出处 |
|---|---|---|---|
| 正面 | 选牌 Draft | 清空初始牌组，10 次三选一（不能跳过）的本角色卡牌奖励 | `Models.Modifiers/Draft.cs` |
| 正面 | 现开套牌 SealedDeck | 清空初始牌组，从 30 张随机牌里选 10 张 | `SealedDeck.cs` |
| 正面 | 精神错乱 Insanity | 清空初始牌组，换成 30 张随机本角色牌 | `Insanity.cs` |
| 正面 | 囤积癖 Hoarder | 每加 1 张牌额外复制 2 张；禁止商人删牌 | `Hoarder.cs` |
| 正面 | 专精 Specialized | 开局获得 5 张同一张随机本角色牌 | `Specialized.cs` |
| 正面 | 全明星 AllStar | 开局获得 5 张随机无色牌 | `AllStar.cs` |
| 正面 | 飞行 Flight | 选路时可以无视连线 | `Flight.cs` |
| 正面 | 上等好货 Vintage | 普通战斗的卡牌奖励替换成随机遗物 | `Vintage.cs` |
| 正面 | 某角色卡牌 CharacterCards | 指定角色的卡池并入卡牌奖励和商店 | `CharacterCards.cs` |
| 负面 | 致命事件 DeadlyEvents | 「?」房间的精英基础概率设为 10%，宝箱概率增速 ×2；移除佛珠手链（JuzuBracelet） | `DeadlyEvents.cs` |
| 负面 | 诅咒局 CursedRun | 每幕开始往牌组加 1 张随机诅咒 | `CursedRun.cs` |
| 负面 | 精英猎手 BigGameHunter | 精英数 ×2.5（不受地图规则限制）；精英战的卡牌奖励只出稀有牌 | `BigGameHunter.cs` |
| 负面 | 点金手 Midas | 金币奖励 ×2；休息处去掉锻造 | `Midas.cs` |
| 负面 | 嗜杀成性 Murderous | 进入战斗时场上所有生物 +3 力量，中途加入的敌人也 +3 | `Murderous.cs` |
| 负面 | 暗夜惊魂 NightTerrors | 休息回满血，但失去 5 点最大生命 | `NightTerrors.cs` |
| 负面 | 身患绝症 Terminal | 每进一个房间失去 1 点最大生命；每场战斗开始获得 5 层覆甲 | `Terminal.cs` |
| 废弃 | DeprecatedModifier | 旧存档兼容用的占位 | `DeprecatedModifier.cs` |

说明：
- **互斥组**：选牌、现开套牌、精神错乱三者互斥（都要清空初始牌组）（`Models/ModelDb.cs:411-416`）。
- **点金手文案和数值不一致**：本地化（中英文都是）写「金币增加 200%」，代码是 ×2，也就是 +100%（`Midas.cs`；`localization/eng/modifiers.json`）。
- 「精英猎手」修饰符和 A1 精英蜂拥叠加时，是在已经生成好的地图上按精英数 ×2.5 重新生成（`BigGameHunter.cs:16-27`）。
- 「好处一次性给」的修饰符（选牌、现开套牌、精神错乱、专精、全明星）都通过**涅奥选项**交付：有修饰符时涅奥不出祝福，而是按顺序逐个弹出修饰符选项（`Neow.cs:286-311`）。所以每日挑战（固定 2 正 1 负共 3 个修饰符）一定没有涅奥祝福；自定义模式只要勾了任意修饰符也没有，一个都不勾时涅奥照常给祝福。

**设计观察**：修饰符没有单独做一套系统，而是复用了遗物/能力的 Hook 接口（改奖励、改休息处、改地图、改卡池……），每个修饰符只有 9-67 行（`wc -l` 合计 630 行）。新增玩法规则的成本很低，这也是它们能拿来做每日挑战「每天换口味」的基础。

---

## 7. 统计、跑局历史、排行榜、建筑师伤害

### 7.1 统计页（`Nodes.Screens.StatsScreen/`；`localization/zhs/stats_screen.json`）

| 区块 | 内容 |
|---|---|
| 总览 | 总游玩时间 / 最快获胜；进阶（全角色 MaxAscension 之和 / 5×10）；胜/负；最高连胜 / 进阶连胜 |
| 收藏 | 卡牌、遗物、药水各显示「已解锁 X/总数」（分母见 §2.7）和「已发现」；事件「已遭遇」；怪物「总击杀 / 已发现」；打败 Boss 数 / 结识先古之民数；成就数 / 纪元数 |
| 每个角色 | 进阶、胜负、游玩时间、最快获胜、当前与最高连胜 |
| 成就页签 | 禁用（§4.1） |

出处：`SaveManager.cs:1281-1402`（GetTotalUnlockedCards、GetAggregateAscensionProgress、GetTotalKills 等）。

### 7.2 跑局历史

- 每局结束（胜、负、放弃）都会生成一份 `RunHistory`，存成 `{StartTime}.run`，**没看到本地条数上限**，但 Steam 云同步只保留最新 100 份 / 5 MB，超出时把最旧的从云端「遗忘」（`Runs/RunHistoryUtilities.cs:17-70`；`Saves.Managers/RunHistorySaveManager.cs:13-15,57,62-69`；`Saves/CloudSaveStore.cs:950-983`）。
- 记录内容：版本号、平台、模式、胜负、种子、开始时间、用时、进阶、是否放弃、死于哪个遭遇或事件、每个玩家的牌组/遗物/药水/徽章/药水栏数、经过的幕、修饰符，以及**完整的逐点历史** `MapPointHistory`（`Runs/RunHistory.cs`）。逐点历史里有每一次选卡（拿了哪张、跳过哪些）、事件选项、先古之民选择、附魔、变化等（`MegaCrit.Sts2.Core.Runs.History/*HistoryEntry.cs`）。
- 至少有 1 份历史后，图鉴里才出现「跑局历史」按钮（`NRunHistory.cs:369-372`）。

### 7.3 排行榜

只有每日挑战用排行榜，图鉴里的「排行榜」按钮是硬隐藏的（`NCompendiumSubmenu.cs:242`）。支持全球、我附近、好友三种查询（`Leaderboard/LeaderboardQueryType.cs`），可以按天翻页（`DailyRunUtility.AddLeaderboardDays`）。目前只接了 Steam（`Leaderboard/LeaderboardManager.cs:12-35`）。

### 7.4 建筑师伤害：社区长线目标

- 获胜时，本局积分条分数会记作「对建筑师造成的伤害」：累加到个人的 `Progress.ArchitectDamage`（`ProgressSaveManager.cs:236-237`），同时调用 `SteamStatsManager.IncrementArchitectDamage` 累加到 Steam 全球统计（`RunManager.cs:1684-1688`）。
- 结算文案：「你对建筑师造成了 X 点伤害……但这还不及其皮毛……你已累计造成 Y 点。即便承受了所有挑战者合力造成的 Z 点伤害，建筑师依然屹立不倒」（`localization/zhs/game_over_screen.json` VICTORY_DAMAGE）；胜利横幅是「胜利……？」。

**设计观察**：这是「全服共同目标」的叙事钩子。通关不再是终点，而是对一个打不倒的 Boss 的一次「蹭血」，个人和全球的累计数字一直在涨。结合成就里的「真结局：完成第四阶段」和时间线上空着的「终结」时代，可以推断正式版会用某种方式「兑现」这个全球伤害（推断）。

---

## 8. 新手引导（FTUE）

FTUE 用字符串 Key 存在 `FtueCompleted` 里，**每个只弹一次**。`EnableFtues = false` 时 `SeenFtue` 一律返回 true，即全部跳过（`ProgressSaveManager.cs:845-891`）。例外是两条进阶首次提示（#12、#13）：它们走 `SeenPopup`，不看这个开关，关了教程照样会弹（`ProgressSaveManager.cs:858-865`）。设置里可以重置。

| # | Key | 触发时机 | 内容（`localization/zhs/ftues.json`） | 出处 |
|---|---|---|---|---|
| 0 | `accept_tutorials_ftue` | 第一次在选角界面点「出发」 | 询问要不要教程；选「不要」会关掉全部 FTUE | `NCharacterSelectScreen.cs:647-655`；`Nodes.Ftue/NAcceptTutorialsFtue.cs:95-105` |
| 1 | `combat_rules_ftue` | 第一场战斗开始 | 3 页战斗基础：能量和回合、格挡、意图 | `Combat/CombatManager.cs:598-609` |
| 2 | `cannot_play_card_ftue` | 第一次尝试打出能量不够的牌 | 能量不足时结束回合 | `Nodes.Combat/NCardPlay.cs:303-310` |
| 3 | `can_play_cards_ftue` | 第一次在还有可出的牌时点结束回合 | 能量指示器 2/3 的含义 | `Nodes.Combat/NEndTurnButton.cs:610-620` |
| 4 | `shuffle_ftue` | 第一次弃牌堆洗回抽牌堆 | 抽牌堆/弃牌堆的位置 | `Commands/CardPileCmd.cs:1200-1210` |
| 5 | `combat_reward_ftue` | 第一次进奖励界面 | 别忘了拿奖励 | `Nodes.Screens/NRewardsScreen.cs:750` |
| 6 | `power_card_ftue` | 第一次在卡牌奖励里出现能力牌 | 能力牌在整场战斗持续 | `Nodes.Screens.CardSelection/NCardRewardSelectionScreen.cs:420-430` |
| 7 | `map_select_ftue` | 第一次看地图 | 选相邻的上层房间 | `Nodes.Screens.Map/NMapScreen.cs:1343` |
| 8 | `obtain_potion_ftue` | 第一次获得药水 | 药水跨战斗保留 | `Nodes.Potions/NPotionContainer.cs:332-338` |
| 9 | `obtain_relic_ftue` | 第一次在宝箱或奖励里出现遗物 | 遗物从哪来 | `Nodes.Rooms/NTreasureRoom.cs:349`；`NRewardsScreen.cs:479` |
| 10 | `rest_site_ftue` | 第一次到休息处 | 只能选一个选项 | `Nodes.Rooms/NRestSiteRoom.cs:397` |
| 11 | `merchant_ftue` | 第一次进商店 | 别忘了找商人 | `Nodes.Rooms/NMerchantRoom.cs:275` |
| 12 | `ascension_singleplayer_ftue` | 任一角色 MaxAscension > 0 后进单人选角 | 进阶已解锁 + A1 会给纪元 | `StartRunLobby.cs:549-556` |
| 13 | `ascension_multiplayer_ftue` | MaxMultiplayerAscension > 0 后进多人选角 | 多人进阶所有角色共用 | `NCharacterSelectScreen.cs:471` |
| 14 | `multiplayer_warning` | 一局都还没完成（`NumberOfRuns == 0`）时第一次打开多人菜单 | 多人模式警告弹窗；打完过一局再进多人就不会弹 | `Nodes.Screens.MainMenu/NMultiplayerSubmenu.cs:355`；`Nodes.Multiplayer/NMultiplayerWarningPopup.cs:108` |
| — | 时间线教程 | 第一次打开时间线 | 「揭晓历史节点来解锁卡牌、遗物和更多……」 | `NTimelineScreen.cs:510-543`；`localization/zhs/timeline.json` TUTORIAL_TEXT |

本地化里还有附魔、侵蚀、宝箱的提示文本（ENCHANTMENT/AFFLICTION/CHEST_FTUE），没找到对应的 `N*Ftue` 节点，可能是别处的悬浮提示或者还没接上（待核实）。

**教学性的内容修正**：标准模式下（每日/自定义不会），每幕的 Boss 按「发现顺序」优先选还没见过的（`ActModel.cs:416-427`；`RunManager.cs:765-797`）。具体顺序见第 4 章。

**设计观察**：
- 全部是「情境触发、一次性」的模态提示，没有独立的教学关卡。第一局就是教学局，配合「首局没有涅奥」和「Boss 按发现顺序出」，第一局的体验被收得很干净。
- 第一个问题是「要不要教程」，老玩家可以一键关掉，不会被打扰。

---

## 9. 图鉴（Compendium）

| 入口 | 何时出现 | 条目三态（`ModelVisibility`） | 出处 |
|---|---|---|---|
| 图鉴总入口 | 至少完成 1 局（`NumberOfRuns > 0`，开发版不限） | — | `SaveManager.cs:1461-1468`；`NMainMenu.cs:625` |
| 卡牌库 | 随图鉴开放 | **锁定**（纪元没揭示）/ **未见**（已解锁但没在局里见过）/ **可见**；可见卡会显示 CardStats（选取、跳过、胜负） | `Nodes.Screens.CardLibrary/NCardLibraryGrid.cs:177-247` |
| 遗物收藏 | 随图鉴开放 | 同上三态 | `Nodes.Screens.RelicCollection/NRelicCollectionCategory.cs:258` |
| 药水实验室 | 随图鉴开放 | 同上三态 | `Nodes.Screens.PotionLab/NLabPotionHolder.cs:118-170` |
| 怪物图鉴 | 已发现至少 1 幕，且至少**击败过**一种怪物 | 怪物要 `TotalWins > 0`（打赢过）才算发现；角色筛选按「击杀 + 阵亡 > 0」解锁 | `Nodes.Screens.Bestiary/NBestiary.cs:655,808-815,1235-1242` |
| 跑局历史 | 至少有 1 份历史 | — | `NRunHistory.cs:369-372` |
| 统计 | 随图鉴开放 | — | §7.1 |
| 排行榜 | 硬隐藏 | — | `NCompendiumSubmenu.cs:242` |

「见过」的判定：卡牌、遗物、药水在局里出现时调用 `MarkXAsSeen`（`ProgressSaveManager.cs:168-190`），首次见到还会记进本局的 `Discovered*`，结算时展示「本局新发现」（`NGameOverScreen.cs:609` AnimateDiscoveries）。

**设计观察**：图鉴把「锁定」和「没见过」分开显示，玩家能看出哪些是「时间线还没给我」、哪些是「池子里有但我还没碰到」，两者对应的行动完全不同：前者去完成纪元条件，后者多打几局。

---

## 10. 节奏分析：新内容怎么投放

### 10.1 一个典型新玩家的解锁路径（推断，按代码条件推演）

| 阶段 | 玩家在做什么 | 时间线给什么 |
|---|---|---|
| 第 1 局（铁甲战士，大概率死在第 1-2 幕） | 学基础，FTUE 逐条弹出；没有涅奥 | 结束后强制进时间线：涅奥（开局祝福）→ 静默猎手；时间线一下子长出 12 + 7 个槽位 |
| 第 2-5 局 | 两个角色轮流玩，偶尔打过第 1、2 幕 Boss | 每个角色的 2、3 号；积分条前 3-4 档（无色牌、遗物、药水、**暗港**） |
| 第一次通关 | 某角色打过第 3 幕 Boss | 4 号（专属药水 + 进阶入口）+ 进阶 1；如果是静默猎手局，还会开出储君 |
| 全角色阶段 | 依次解锁储君 → 亡灵契约师 → 故障机器人 | 欧洛巴斯（全角色）、每日挑战（全角色 + 胜）、种子（3 胜） |
| 中期 | 刷 A1、累计 15 精英/15 Boss | 每个角色的 5/6/7 号；积分条中后段（每局最多 1 档） |
| 长尾 | A2-A10、徽章、每日挑战、建筑师伤害 | 进阶只有提示，不再给内容；积分条 18 档刷完后积分条隐藏 |

角色纪元 34 个 + 积分条 18 个 + 特殊 5 个。积分条最少 18 局，5 个角色的 5/6 号各需要累计 15 精英、15 Boss，粗估**全时间线要 50-80 局**（推断，取决于胜率）。

### 10.2 设计手法归纳

1. **两条进度线并行、互不干扰**：通用内容走积分条（看总投入），角色内容走里程碑（看角色熟练度）。玩家换角色不会白打，专精一个角色也不会把通用内容刷完。
2. **给目标、不给数值**：所有里程碑都是可读的行为目标（打过第 N 幕、杀 15 精英、A1 通关），悬浮提示直接写出条件。没有「经验值 3742/5000」这种黑箱。积分条是唯一的数值进度，也被「一局最多 1 档」削平了。
3. **解锁要「看」**：强制揭示 + 传说文本 + 卡牌/遗物展示，让每次解锁都有一次被读到的仪式（§2.5）。
4. **叙事化的进度**：57 个纪元同时是 8 个故事的章节和一部世界史的片段（史前到门扉）。收集进度和阅读世界观是同一件事。
5. **不锁核心机制、锁变化**：角色卡池只锁 10%，第一局就能体验完整机制；锁的是专属遗物和药水、新幕、新先古之民这类「改变局内体验」的东西。
6. **难度梯度靠资源而不是数值**：进阶 1-7 削的是经济，8-9 才轻度加怪物数值（§3.1）。

### 10.3 与一代对比（凭公开知识，未在本包中核实）

| 维度 | 一代（Slay the Spire 1） | 二代（本版本源码） |
|---|---|---|
| 解锁载体 | 每个角色一条分数经验条，每档给一批卡或遗物 | 时间线纪元：里程碑 + 通用积分条两条线 |
| 角色解锁 | 按顺序靠打完前一个角色的局解锁 | 同样串行（静默 → 储君 → 亡灵 → 故障），但会体现成时间线上的叙事节点 |
| 进阶 | 20 级，首次通关后开放 | 10 级，首次通关后开放（还需要 4 号纪元），按角色记录，多人单独一条 |
| 每日挑战 | 有，带修饰符和排行榜 | 有，固定 2 正 1 负修饰符，排行榜按人数分开，徽章数参与排序 |
| 解锁的仪式感 | 结算界面弹出 | 主菜单强制进时间线揭示 |
| 社区目标 | 无 | 建筑师伤害（个人 + 全球累计） |

核心差别：一代的解锁是「分数 → 经验条」的纯投入换产出。二代把大部分解锁挂到**行为目标**上，把投入型的积分条限定在通用内容、并限制每局最多 1 档，再用时间线把所有解锁串成叙事。

---

## 11. 可借鉴

1. **「获得」和「生效」分两步，生效时强制观看**：解锁不会被结算界面的信息淹没，每次都有一个独立的仪式时刻。要做好批量揭示的节奏（二代是间隔 3 秒）。
2. **投入型进度只投放通用内容，并且限速**：「一局最多 1 档 + 溢出压到门槛 −1」这个规则很简单，却能防止高手几局刷穿、也防止新手卡住（前几档门槛很低）。
3. **按角色给一套可读的 7 节里程碑模板**：同一套模板套 5 个角色，玩家学一次就懂；条件由易到难（打过 1/2/3 幕 → 累计 15 → A1），本身就是这个角色的「成长路线图」。
4. **难度旋钮要能被玩家归因**：开发方删掉 Gloom 的理由可以直接借鉴（§3.1）。
5. **徽章 = 每局可以重复拿的小成就 + 排行榜决胜键**：成本低，又能鼓励多样玩法。
6. **修饰符复用战斗 Hook**：新规则的边际成本很低，可以支撑每日挑战每天换口味。
7. **全服累计目标**：把每局分数变成对同一个敌人的「伤害」，个人数字和全球数字一起涨，是成本很低的社区感设计。

---

## 12. 没解决 / 拿不准的点

1. **积分条在每日/自定义模式下是否真的会发纪元**：`SaveManager.GrantNextUnlock` 的注释明确写了「忽略 AreAchievementsAndEpochsLocked」，`NGameOverScreen.AnimateScoreBar` 也没有模式判断；但补丁说明 2026-03-19 说 Daily/Custom 不能再获得纪元。按代码判断是会发的，需要实测确认。
2. **「全角色都玩过」的判定**：单人大厅切换角色时就会创建 CharacterStats 条目（`StartRunLobby.cs:518`），所以欧洛巴斯和每日挑战的「全角色」条件实际可能只要「在选角界面点过所有角色」。没有实测。
3. **稀缺的普通牌概率是静态字段**：`CardRarityOdds.regularCommonOdds` 是 `static` 字段（不是属性），类型初始化时就算定了（`Odds/CardRarityOdds.cs:13`）。不过掷骰时只读稀有和罕见两档的基础概率，普通是剩余值（`Odds/CardRarityOdds.cs:96-111`），这个字段在掷骰里从未被读到，**实际没有影响**，只是写法上的遗留（主笔复核，与第 5 章结论一致）。
4. **成就会不会在正式版恢复、恢复后纪元是否回到成就驱动**：现在只能看到空函数和 11 条没有枚举的文本。
5. **Act2B / Act3B 两个占位纪元**会解锁第 2、3 幕的 B 面（和暗港对应），目前代码里没有任何引用；「终结」「遥远未来」两个空时代的用途也是推断。
6. 积分条的「局数估算」和「全时间线 50-80 局」都是按每幕约 15 个点推算的，没有用真实存档验证。
7. 附魔、侵蚀、宝箱三条 FTUE 文本找不到对应的触发节点。

---

## 附：本章数据表

| 文件 | 行数 | 内容 |
|---|---|---|
| `data/csv/ch06_epochs.csv` | 57 | 纪元 Id、类名、标题、故事和章节、时代和年份、行、获取通道、条件（代码口径）、出处、本地化条件、哪个纪元打开它的槽位、它打开哪些槽位、解锁内容（中文名 + 类名）、生效处、积分条档位和门槛 |
| `data/csv/ch06_ascension.csv` | 10 | 等级、枚举、简中标题和描述、实现与数值、出处、补丁说明里的演化 |
| `data/csv/ch06_achievements_badges.csv` | 58 | 33 个成就（22 个枚举 + 11 个只有文本）+ 25 个徽章条目（23 个在池 + Whomper + FAVORITE_CARD）；条件、档位、是否要求获胜、是否仅多人、状态、出处 |
