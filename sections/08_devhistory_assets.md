# 第 08 章　开发史、设计迭代与资源清单

> 范围：127 份英文补丁说明（另有 1 份简中）梳理出的开发时间线和设计迭代；代码里的弃用、Mock、调试遗迹；美术、音频、动画资源的路径清单（**只列路径和统计，不导出任何资源**）。
>
> 出处写法：补丁写成 `PN 2024_05_10`，即 `data/pck_text/localization/eng/patch_notes/2024_05_10.md`；代码写成 `MegaCrit.Sts2.Core.Models/CardModel.cs:143`（相对 `csharp/sts2_src/`）。
>
> 本章数据：`data/csv/ch08_patch_notes_entries.csv`（每条补丁条目一行）、`ch08_patch_timeline.csv`（每份补丁一行）、`ch08_patch_monthly.csv`、`ch08_patch_top_entities.csv`、`ch08_patch_renames.csv`、`ch08_asset_catalog.csv`、`ch08_asset_paths_by_entity.csv`、`ch08_import_map.csv`、`ch08_shaders.csv`。脚本：`scripts/ch08_patch_notes.py`、`scripts/ch08_assets.py`，都能重跑。

## 0. 本章结论速览

1. 这批补丁说明是**内部测试服的全部历史**：第一份自称「我们内测服里贴过的最早一份补丁说明」（`PN 2023_02_09`），之后每周五出包，到 EA 后改成 beta 分支双周更。127 份英文补丁一共拆出 10,332 条条目；剔除 3 份主分支合集后剩 9,688 条，其中修 Bug 占 32%，平衡占 25%。
2. 开发可以切成 5 段。中间有一个 **7 个月空窗（2023-09 → 2024-04）**：`PN 2023_09_15` 说「因为 Unity 最近的风波……我们在研究迁移方案」，`PN 2024_04_12` 写着「旧引擎有些问题，但我们回来了」，Bug 修复栏里还有一条「Removed Unity」。也就是说，现存补丁覆盖的前 7 个月（2023-02～09）是 Unity 版，之后整体迁到了 Godot。开发并不始于 2023-02：最早一份补丁已经在修内部工单（`#STS-49xx`），还说「年初以来一直在做大规模架构迁移」。
3. **角色是反复推倒重来的**。亡灵契约师（Necrobinder）至少大改了 5 轮（双角色换位 → 自身低血战后回满 → 召唤和魂 → 2025-06 再大改 → 2026-01 改起始牌组）；故障机器人（Defect）2023-08 进来，2024-07 被锁掉，2025-04 重新开放，2025-07「又一次推倒重建」；储君（Regent）的「引力 Gravity」机制在 2024-05 开始淘汰；包里那个零引用的 `GravityPower` 其实是后来引力井 Gravity Well 卡给玩家的本回合增益（2024-11 重做，2025-12 随卡弃用后成了死件），不是 2024-05 那套引力机制的残留。
4. **补丁里明确写着 Deprecated / Removed 的卡名约 170 个**（启发式拆分，两种独立抽法分别得 172、174 个；其中约 15 个后来以同名回归，如 Expertise、Chill、Barrage、Juggernaut、Dual Wield、Entrench、Caltrops，净删约 155 张），而当前卡池是 596 张。这些卡的本地化 key 有 22 个还留着；卡图图集里还有 34 张没有对应模型的成品卡图，里面有不少一代卡名。
5. 平衡改动的分布：**卡牌改动很分散，怪物和古神（Ancient）的改动很集中**。被提到最多的卡也只出现在 13 条平衡条目里；而涅奥（Neow）在平衡段出现了 62 次，偷窃草蜢（Thieving Hopper）16 次，知识恶魔（Knowledge Demon）14 次。古神的祝福和 Boss 是被反复打磨的「体验锚点」。
6. 几个系统被做出来又拿掉了：Boss 遗物（2024-05 改由古神提供，2025-01-16 加回 Boss 专属遗物，2 周后又整体废弃）、传奇稀有度（2024-09 加入，2025-02 换成 Ancient）、Act 3 Boss「造梦者 Dreamer → 造门者 Doormaker → 永世沙漏 Aeonglass」（Doormaker 多次重做后被删，理由是「超出了我们想要的复杂度阈值」，`PN 2026_05_07`）。
7. **改名约 250 次（252），约 46% 集中在 2025-12 到 2026-02**（另一波高峰是 2025-08，42 次），官方给的理由是「为翻译做准备」（`PN 2025_12_18`），2026-01-15 那次还专门叫「遗物大改名：第二部」。临时力量的弃用在代码注释里也留了痕迹：它以前叫 Strength Down（`MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs:20`，`PN 2025_09_18`）。
8. EA 之后补丁里开始出现**设计师署名的说明**（Anthony，`PN 2026_03_26` 起），常用胜率、选取率和「数百万局」的数据来解释改动，比如「杂技（Acrobatics）作为普通卡同时霸占胜率和选取率」（`PN 2026_04_09`）。这段数据驱动的平衡方法值得直接学。
9. 代码里的 `Deprecated*` 类**不装被删的内容**。它们是给存档和对局历史用的「墓碑」：读档时找不到 id 就换成它（`MegaCrit.Sts2.Core.Saves/SaveUtil.cs:23-113`）。被砍内容真正的证据在三处：本地化残留、图集孤儿子图、没有任何引用的类（4 个能力、1 个遭遇、对手 1～3 型 The Adversary 三只怪，外加注释标明「NOT IN USE」的徽章 `Whomper`）。
10. 还没上线的内容有明确痕迹：纪元表里的 `ACT2_B_EPOCH` 和 `ACT3_B_EPOCH` 写着「此地将在抢先体验期间揭晓」，FMOD 音乐 bank 只有 `act1_b1`（暗港 Underdocks），由此推断第 2、3 幕各自也会有一个 B 版本；5 个角色的第 8、9 纪元全是 `TODO`；补丁 `PN 2026_11_13` 还提到 beta 分支上有新角色，但当前主分支的包里找不到任何痕迹。
11. 资源方面：PCK 1.99 GB 里，**字体占 19.6%（主要是中日韩字体），事件插图占 16.4%，FMOD 音频占 15.9%，房间背景占 11.0%**，卡图原图只占 8.5%。卡图按「图集子图 → 单张 PNG → beta PNG → 缺图占位」四级回退（`MegaCrit.Sts2.Core.Assets/AtlasResourceLoader.cs:272-368`）。Godot 导入物的文件名是 `<原文件名>-<md5("res://原路径")>`，3,970 个全部验证通过。
12. 一个容易被忽略的事实：`debug_audio/` 这批「临时 mp3」**至今仍在正式流程里播放**，比如获得遗物、消耗、胜利、回合横幅，有 60 多处调用（`MegaCrit.Sts2.Core.Audio.Debug/TmpSfx.cs:7-84`）。

---

## 1. 史料与方法

### 1.1 这批补丁说明是什么

- 位置：`localization/eng/patch_notes/*.md` 一共 127 份，从 2023-02-09 到 2026-11-13；`localization/zhs/patch_notes/` 下只有 `2026_03_26.md` 一份，是同日英文版的中文翻译（152 行，英文版 149 行）。其余语言没有补丁说明。
- 来历：`PN 2024_09_12` 的 UI 栏写着「加入游戏内补丁说明界面，**并上传了所有以前的补丁说明**」，所以 2024-09 以前的内容是事后补录进游戏的。补录时外链统一换成了 `REDACTED`（比如 `PN 2023_04_21` 里的「Link: REDACTED」）。
- 读者：EA（2026-03）以前是写给**内测玩家**看的（「Hey playtesters」，最晚见于 `PN 2025_11_06`），2026-03 之后写给公众（「Hey Slayers」）。所以早期补丁口语化、混着内部工单号（比如 `#STS-4975`，`PN 2023_02_09`），后期才变成规范的分段格式。

### 1.2 三种格式与解析规则

| 时期 | 格式 | 例 |
|---|---|---|
| 2023-02 | 每行开头是「类型: 正文」 | `BALANCE: Changes to Roaches encounter`（`PN 2023_02_09`） |
| 2023-04 ~ 2024-09 | `**Art & Animation**` 这类粗体标题，下面跟裸行或 `-` 列表，混着大段闲聊 | `PN 2023_04_21` 一份 370 行，按美术、UI、内容、修 Bug 分块 |
| 2024-09-12 起 | `[blue][b]CONTENT:[/b][/blue]` 是段标题，`Ironclad:` 是子类，`- ` 是条目，缩进 `  - ` 是子项；2026-01-22 起实体名都加了 `[b]…[/b]` | `PN 2024_09_12` |

脚本 `ch08_patch_notes.py` 的处理方式如下：

- 段标题归成 17 种规范类型：BUGFIX、BALANCE、CONTENT、CONTENT_BALANCE、ART、UI_UX、WORDING、AUDIO、PERFORMANCE、MODDING、LOCALIZATION、FEATURE、DEBUG、KNOWN_ISSUE、GENERAL、NARRATIVE（导语），以及 DEV_COMMENTARY（设计师说明）。2023 年的 `GAMEPLAY:` 归进 BALANCE。
- 一级条目算一行，缩进子项并进父条目。还有一种写法是「Added new cards:」后面跟着同级列表，脚本也会把这些同级项并进来。
- 按条目开头的动词打上动作标签：ADD、DEPRECATE、REWORK、RENAME、REVERT、BUFF、NERF、CHANGE、FIX、OTHER。2024-09 以后补丁统一用「Buffed / Nerfed X」开头，所以 BUFF 和 NERF 只能可靠统计 2024 年以后的数据。
- 实体识别：用当前英文本地化的 15 类名字（卡、遗物、药水、能力、怪物、遭遇、事件、古神、附魔、苦难、修饰符、充能球、角色、幕、进阶）做最长优先匹配；再用「Xxx card/relic/boss…」句式和加粗名补抓已经删掉的旧名，这部分标成 `legacy_*`。
- **剔除合集**：`2026_05_28`（把 beta 的修复搬到主分支）、`2026_06_18`（主分支大更新 2，「4 合 1」）、`2026_11_13`（主分支大更新 3，「v0.108.0-v0.111.0」）这三份重复了 beta 补丁的内容，按月统计和实体统计时都剔除，否则会重复计数。

已知局限：一是实体按**当前名字**匹配，改名前的旧名（比如 Transfuse，后来改叫 Unleash）只能靠 `legacy_` 补抓，所以旧内容的频次会偏低；二是 `PN 2023_04_21` 这类裸行清单偶尔会把美术日志也算成条目。

### 1.3 总量

| 规范类型 | 条目数（剔除合集） | 占比 |
|---|---:|---:|
| BUGFIX 修 Bug | 3,068 | 31.7% |
| BALANCE 平衡 | 2,387 | 24.6% |
| UI_UX 界面体验 | 1,366 | 14.1% |
| CONTENT 内容 | 866 | 8.9% |
| ART 美术 | 828 | 8.5% |
| WORDING 文案 | 548 | 5.7% |
| CONTENT_BALANCE（EA 后「内容与平衡」合并段） | 220 | 2.3% |
| NARRATIVE 导语 / DEV_COMMENTARY 设计说明 | 176 / 23 | 2.1% |
| PERFORMANCE / AUDIO / LOCALIZATION / MODDING / 其它 | 73 / 73 / 28 / 20 / 12 | 2.1% |
| **合计** | **9,688** | |

来源：`data/csv/ch08_patch_notes_entries.csv` 中 `is_rollup=0` 的行。

---

## 2. 开发阶段划分

### 2.1 五个阶段

| 阶段 | 时间 | 份数 / 条目 | 标志事件（出处） |
|---|---|---|---|
| **P0 Unity 内测** | 2023-02-09 → 2023-09-15 | 20 / 1,259 | 最早一份补丁，说「年初以来一直在做大规模架构迁移」（`PN 2023_02_09`）；动作系统重写（`PN 2023_04_21`）；存读档到 2023-06 才可用（`PN 2023_06_02`）；开始收集指标（`PN 2023_06_30`）；Defect 首次加入，约 63 张卡（`PN 2023_08_04`）；本地化架构大改（同上）；因为 Unity 风波暂停出包（`PN 2023_09_15`） |
| *空窗* | 2023-09 → 2024-04 | 0 | 迁移引擎。`PN 2024_04_12` 写了「Removed Unity」，还说「这个包暂时没有声音」 |
| **P1 Godot 重启** | 2024-04-12 → 2024-09-06 | 19 / 1,522 | 储君首次登场（`PN 2024_04_12`）；第一个有音乐音效的 Godot 包，引力机制开始淘汰（`PN 2024_05_04`）；古神系统加入（`PN 2024_05_10`）；改用 Steam 分发测试包（`PN 2024_08_09`）；支持 macOS（`PN 2024_08_23`）；出包日从周五改到周四（`PN 2024_08_30`） |
| **P2 结构化周更** | 2024-09-12 → 2025-01-23 | 17 / 1,242 | 游戏内补丁页上线，补丁换成新格式（`PN 2024_09_12`）；进阶 1～6 级（`PN 2024_10_17`）、7～9 级（`PN 2024_10_24`）；亡灵契约师全面重新设计（`PN 2024_11_01`）；进阶改成按角色分别解锁（`PN 2025_01_09`） |
| **P3 联机上线 → EA 前** | 2025-01-30 → 2026-02-26 | 54 / 4,501 | 「Multiplayer is here!!」（`PN 2025_01_30`）；Ancient 稀有度替代传奇稀有度（`PN 2025_02_06`）；时间线（`PN 2025_02_27`）；暗港（`PN 2025_03_06`）；F2 反馈（同上）；每日挑战回归（`PN 2025_05_22`）；自定义模式和联机专属卡（`PN 2025_05_29`）；时间线重新上线并开始锁内容（`PN 2025_07_17`）；Steam 云存档（`PN 2025_10_30`）；古神对话（`PN 2025_12_04`）；法语、简中（`PN 2026_01_29`）；EA 预告和随机角色（`PN 2026_02_19`）；「EA 上线前最后一次周更」（`PN 2026_02_26`） |
| **P4 抢先体验（EA）** | 2026-03-12 → 2026-11-13 | 14 / 1,164（另有 3 份合集，644 条） | 上线一周后推出 public-beta 分支（`PN 2026_03_12`，所以推断 EA 在 2026-03-05 前后开放）；以「让无限连更难成立」为主线的大平衡，同时加入恐惧症模式（`PN 2026_03_19`）；设计师说明（`PN 2026_03_26`）；徽章（`PN 2026_04_02`）；排行榜只显示好友（`PN 2026_04_09`）；改成双周更（`PN 2026_05_07`）；主分支大更新 2，加入 RNG 重写和创意工坊（`PN 2026_06_18`）；繁中（`PN 2026_07_16`）；印尼语（`PN 2026_08_13`）；主分支大更新 3，即本包 v0.111.1（`PN 2026_11_13`） |

几个跨阶段的观察：

- **出包节奏**是从内测周五 → 周四（`PN 2024_08_30`，理由是「出了问题还有余地发热修」）→ EA 后 beta 分支双周更（`PN 2026_05_07`），原话是「一代每周更新，那太累了，真的很糟」。一年多的周更维持了很高的迭代密度：P3 阶段平均每份补丁 83 条。
- **主分支和 beta 分离**：EA 后实验性的改动先进 beta，再攒成「大更新」合并到主分支（`PN 2026_06_18`、`PN 2026_11_13`）。所以本包虽然是 v0.111.1，内容其实**落后于 beta**，beta 上的新角色和新模式不在这个包里（`PN 2026_11_13`：「beta 分支上的新角色和游戏模式……还需要大量测试打磨」）。

### 2.2 按季度的节奏（剔除合集，完整按月数据见 `ch08_patch_monthly.csv`）

| 季度 | 份数 | 条目 | 内容 | 平衡 | 修 Bug | 美术 | 界面 | 文案 | 新增 | 删除 | 重做 | 加强 | 削弱 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023Q1 | 2 | 66 | 0 | 9 | 36 | 0 | 8 | 3 | 1 | 1 | 1 | – | – |
| 2023Q2 | 10 | 847 | 45 | 69 | 364 | 256 | 87 | 0 | 133 | 21 | 19 | – | – |
| 2023Q3 | 8 | 346 | 31 | 29 | 126 | 77 | 47 | 8 | 44 | 7 | 11 | – | – |
| 2024Q2 | 12 | 1,072 | 147 | 307 | 327 | 39 | 168 | 39 | 151 | 26 | 94 | 30 | 28 |
| 2024Q3 | 11 | 588 | 40 | 105 | 194 | 59 | 137 | 39 | 79 | 6 | 27 | 22 | 14 |
| 2024Q4 | 10 | 851 | 103 | 331 | 212 | 91 | 77 | 36 | 86 | 27 | 59 | 72 | 41 |
| 2025Q1 | 11 | 847 | 104 | 280 | 243 | 52 | 94 | 57 | 88 | 27 | 42 | 50 | 62 |
| 2025Q2 | 13 | 976 | 102 | 246 | 259 | 51 | 222 | 64 | 123 | 22 | 36 | 71 | 40 |
| 2025Q3 | 13 | 1,147 | 104 | 300 | 384 | 40 | 160 | 134 | 104 | 34 | 44 | 89 | 74 |
| 2025Q4 | 11 | 933 | 116 | 345 | 226 | 38 | 114 | 54 | 86 | 36 | 69 | 68 | 75 |
| 2026Q1 | 12 | 1,137 | 95 | 339 | 316 | 71 | 156 | 81 | 120 | 24 | 52 | 114 | 81 |
| 2026Q2 | 7 | 520 | 79 | 27 | 252 | 31 | 57 | 23 | 48 | 4 | 15 | 35 | 20 |
| 2026Q3 | 4 | 358 | 120 | 0 | 129 | 23 | 39 | 10 | 36 | 3 | 14 | 49 | 25 |

说明：2026Q2 起「平衡」大多并进了 CONTENT & BALANCE 合并段，所以计在「内容」列里。「加强 / 削弱」只统计以 Buffed / Nerfed 开头的条目，2024Q2 之前补丁不用这种写法。

读表能看出四点：
- **2023Q2 美术占比最高**（256 条，接近修 Bug 的 70%）。那时在批量接入骨骼动画和卡图（`PN 2023_04_21`、`PN 2023_06_09`），是 Unity 版的「填资产期」。
- **2024Q2 的「重做」数是全期峰值**（94）。Godot 重启后，储君、亡灵契约师和古神系统同时在大改。
- **2025Q3 文案最多**（134）：`PN 2025_08_14` 的 WRITING 段原文 90 行（脚本合并列表后计 39 条），内容是卡 / 药水 / 遗物措辞修订、对话调整和 28 个遗物改名；再加上 9 月的事件重写（`PN 2025_09_25` 导语）。
- **删除数在 EA 后断崖式下降**（2026Q2～Q3 一共 7 条）：上线以后官方几乎不再直接删内容，改成重做和数值微调；`PN 2026_03_19` 还加了「已弃用卡」占位，专门处理玩家存档里的被删卡（见 6.1）。

---

## 3. 每个阶段加了什么

### 3.1 角色线

| 角色 | 首次出现 | 关键迭代（出处） | 现状 |
|---|---|---|---|
| 铁甲战士 Ironclad | 2023-02 已在 | 2024-10 弃用 Reckless Charge、Clothesline、Immolate、Power Through，新增 8 张（`PN 2024_10_10`）；2024-11 弃用灼热攻击 Searing Blow（`PN 2024_11_14`）；2025-01 弃用 Blood for Blood、Dual Wield、Entrench（`PN 2025_01_09`）；2026-04「专门提高铁甲的生存能力」：巨像 Colossus 降为罕见，删掉擒抱 Grapple，加入 Not Yet（`PN 2026_04_09`） | 80 HP，卡池 90 |
| 静默猎手 Silent | 2023-02 已在 | 2024-11 弃用 Choke、Distraction、Stall（`PN 2024_11_07`）；2025-06「套路大改」，删掉 Catalyst、Glass Knife、A Thousand Cuts（`PN 2025_06_26`）；2026-03 Prepared 改了又改回（`PN 2026_03_19` → `PN 2026_03_26`） | 70 HP |
| 亡灵契约师 Necrobinder | 2023-02 已在（奥斯提 Osty 的名字 Bug，`PN 2023_02_09`） | ① 2023-06「大幅翻修」，「Osty 不再有意图、不再单独行动，改为承受所有伤害」（`PN 2023_06_16`）② 2023-09 加入护盾 Shield、活力 Vigor，可以切换前后排（`PN 2023_09_08`）③ 2024-05「不再换位！自身 HP 只有原来的一小部分，但战斗结束回满血、复活 Osty」（`PN 2024_05_04`）④ 2024-11「全面重新设计」，引入召唤 X 和魂 Souls，一次弃用 21 张亡灵卡（`PN 2024_11_01`）⑤ 2025-06「又一次大改」（`PN 2025_06_26`）⑥ 2026-01 起始牌组重做（`PN 2026_01_01`） | 66 HP |
| 故障机器人 Defect | 2023-08-04「约 63 张卡，美术缺很多」（`PN 2023_08_04`） | 2024-07「暂时锁定亡灵契约师和 Defect」（`PN 2024_07_12`）；2025-04「Defect 又能玩了」，加入新充能球 Scrap（`PN 2025_04_25`）；2025-07 加入 Glass 球，同时删掉 Scrap 球（`PN 2025_07_03`）；2025-07「再一次推倒重建」（`PN 2025_07_17`） | 75 HP，充能球 5 种 |
| 储君 Regent | 2024-04-12，Godot 第一包（`PN 2024_04_12`） | 引力开始淘汰（`PN 2024_05_04`）；锻造 Forge 和星光剑 Starlight Sword 加入（`PN 2024_06_07`），一周后改名君王之剑 Sovereign Blade（`PN 2024_06_14`）；「不再有星星上限！」（`PN 2025_01_16`）；2025-12 弃用引力井 Gravity Well（`PN 2025_12_11`） | 75 HP |
| 随机角色 | 2026-02-19（`PN 2026_02_19`） | — | 见第 6 章 |
| 新角色（beta） | 2026-11 仅在 beta 上（`PN 2026_11_13`） | 当前包没有对应的类、卡池和资源（已核查 `MegaCrit.Sts2.Core.Models.Characters/` 只有 8 个类） | 未进主分支 |

**设计观察**：五个角色里有两个经历过「锁起来回炉」：亡灵契约师两次（`PN 2023_08_04`「这一版先休息」、`PN 2024_07_12` 起锁到 `PN 2024_11_01`），Defect 一次。官方在内测期允许角色在相当长的时间里不可玩，比如 Defect 从 2024-07-12 锁到 2025-04-25，9 个多月；这期间先把战斗内核、联机和古神做稳。对我们的启示是：**第 3 个以后的角色不必和系统并行定稿**，可以等底层规则稳定后再整体重做。

### 3.2 幕与 Boss 线

| 幕位 | 现有 Boss（`data/csv/acts.csv`） | 被替换或删除的历史 Boss（出处） |
|---|---|---|
| 第一幕 密林 Overgrowth | 墨影幻灵 Vantom、仪式兽 Ceremonial Beast、同族小队 The Kin | Vantom 和 The Kin 在 2024-08-09 加入（`PN 2024_08_09`）；仪式兽至少重做了 4 次（`PN 2025_09_18`、`PN 2025_09_25`「又一次重做」、`PN 2025_11_20`、`PN 2025_12_04`） |
| 第一幕 暗港 Underdocks（2025-03-06 加入） | 瀑布巨兽 Waterfall Giant、灵魂异鱼 Soul Fysh、乐加维林族母 Lagavulin Matriarch | Soul Fysh 升为 Boss（`PN 2025_04_10`）；族母加入（`PN 2025_05_22`），之后刻意向一代的乐加维林看齐（`PN 2025_06_20`） |
| 第二幕 巢穴 Hive | 无厌沙虫 The Insatiable、知识恶魔、帝皇蟹 Kaiser Crab | 千足虫 Decemillipede 被蚁狮 Antlion 换掉（`PN 2024_06_07`），之后降为精英（`PN 2024_10_24`）；Antlion 改名 The Insatiable（`PN 2024_08_23`）；Insect Repulsor 先「暂时弃用以便重做」（`PN 2025_01_09`），后来没再回来；Infested Guardian/Purifier（`PN 2025_05_01`）改名帝皇蟹（`PN 2026_02_19`） |
| 第三幕 荣耀 Glory | 女王 Queen、实验体 Test Subject、永世沙漏 Aeonglass | 封印之剑 Sealed Sword（`PN 2024_08_23` 加入 → `PN 2025_01_09` 暂停 → `PN 2025_02_20`「完成弃用」）；幻术师 Illusionist（`PN 2025_09_11`）→ 改名造梦者 Dreamer（`PN 2025_09_18`）→ 被造门者 Doormaker 取代（`PN 2025_10_16`）→ Doormaker 重做 4 次（`PN 2025_12_18`、`PN 2026_03_19`、`PN 2026_03_26`、`PN 2026_04_02`）→ 被 Aeonglass 取代（`PN 2026_05_07`） |
| 终局 | 建筑师 The Architect（事件战斗） | 「最终战里玩家改为先手」（`PN 2026_02_19`） |

另外两点：

- **每幕房间数递减**（15/14/13，见第 4 章）是 `PN 2024_05_24` 定下来的：「每幕房间数比上一幕少 1」。
- **A/B 幕规划**：暗港的音乐 bank 叫 `act1_b1`（`MegaCrit.Sts2.Core.Models.Acts/Underdocks.cs:50`），密林是 `act1_a1/a2`（`Overgrowth.cs:55`）；纪元表里又有 `ACT2_B_EPOCH`「Somewhere」和 `ACT3_B_EPOCH`「Elsewhere」，描述是「此地将在抢先体验期间揭晓……」（`localization/eng/epochs.json:2-11`）。**推断**：第 2、3 幕也会各出一个 B 版本，和暗港一样做「同层二选一」。

### 3.3 系统线

| 系统 | 首次出现 | 关键迭代 | 备注（章节） |
|---|---|---|---|
| 存读档 | 2023-04 开工（`PN 2023_04_29`） | 2023-06「应该可用了」（`PN 2023_06_02`）；多次因为格式变更重置存档（`PN 2024_06_29`、`PN 2026_02_12`）；云存档（`PN 2025_10_30`） | 第 7 章 |
| 指标 / 遥测 | `PN 2023_06_30`「我们会监视你们打得怎么样……不收集个人身份信息」 | 图鉴里显示卡牌选取率和胜率（`PN 2024_08_09`）；按角色统计每个遭遇的胜负（`PN 2025_05_15`） | 第 7 章 |
| 古神 Ancients | `PN 2024_05_10`（Pael、Vlad） | 特兹卡塔拉（`PN 2024_05_17`）；囤积者 Hoarder（`PN 2024_05_31`；**推断**就是后来的达弗 Darv，补丁里没有这条改名记录，Darv 从 `PN 2024_11_01` 起才出现）；坦克斯 Tanx（`PN 2024_09_12`）；欧洛巴斯 Orobas（`PN 2024_09_19`）；诺奴佩普 Nonupeipe（`PN 2025_07_10`）；Vlad 改名 Zlatir（`PN 2024_06_29`），又改成瓦库 Vakuu（`PN 2026_01_01`）；祝福遗物化（`PN 2025_04_03`/`04_10`）；会说话（`PN 2025_12_04`） | 第 3、5 章 |
| Boss 遗物 | 继承一代 | 古神提供 Boss 遗物（`PN 2024_05_24`）→ 一周后撤掉，交给囤积者（`PN 2024_05_31`）→ Boss 专属掉落遗物（`PN 2025_01_16`）→ 弃用 Boss 遗物奖励（`PN 2025_01_30`） | 第 3 章 |
| 稀有度 | — | 传奇 Legendary 加入（`PN 2024_09_12`）→ Ancient 稀有度加入、传奇弃用（`PN 2025_02_06`）；卡面底部加星标表示稀有度（`PN 2024_05_04`） | 第 2 章 |
| 进阶 | 1～6 级（`PN 2024_10_17`）、7～9 级（`PN 2024_10_24`） | 按角色解锁（`PN 2025_01_09`）；A10 加入「Villainy」（`PN 2025_09_25`）→ 重做（`PN 2025_11_06`）→ 「Gatekeeper → 进阶者的蔑视」（`PN 2025_12_11`）→ 「双 Boss，一代回归」（`PN 2026_01_15`）；A6 从减少营火改成加价删卡（`PN 2026_04_02`） | 第 6 章 |
| 联机 | `PN 2025_01_30` | 联机进阶单独记录（`PN 2025_04_03`）；联机专属卡（`PN 2025_05_29`）、按角色分的联机卡（`PN 2025_11_13`）、大批联机卡（`PN 2026_07_02`） | 第 7 章 |
| 时间线 / 纪元 | `PN 2025_02_27` | 暂时下架（`PN 2025_06_05`）→ 回归，角色、模式、暗港都要靠纪元解锁（`PN 2025_07_17`）→ 改成按分数解锁（`PN 2026_01_01`） | 第 6 章 |
| 每日 / 自定义 | 每日回归（`PN 2025_05_22`） | 自定义爬塔（`PN 2025_05_29`）；排行榜只显示好友，分数改成按「胜负、徽章数、用时」排序（`PN 2026_04_09`） | 第 6 章 |
| 图鉴：怪物图鉴 Bestiary | `PN 2025_07_24`（内测） | 正式随大更新 2 进入主分支（`PN 2026_06_18`） | 第 6 章 |
| 徽章 | `PN 2026_04_02` | 新增 3 个（`PN 2026_04_26`） | 第 6 章 |
| 恐惧症模式 | `PN 2026_03_19` | 5 只怪有恐惧症 Spine 皮肤，另有 11 张替换图（见 7.3 怪物行） | — |
| RNG | — | 改用 xoshiro256**，因为玩家发现不同随机流之间相关，可以预测涅奥骨头给的诅咒（`PN 2026_06_18`） | 第 1、7 章 |
| Mod / 创意工坊 | 「从第一天起就内置了 Mod 加载器」（`PN 2026_06_18`） | 创意工坊（同上）；Mod 存档和无 Mod 存档分开（`PN 2026_07_02`） | 第 7 章 |
| 本地化 | 加入语言下拉（`PN 2023_08_25`） | 法语、简中（`PN 2026_01_29`）；西班牙语欧洲版和拉美版（`PN 2026_02_05`）；繁中（`PN 2026_07_16`）；印尼语（`PN 2026_08_13`） | 第 7 章 |

### 3.4 一代回归内容

补丁里明确标注「from StS1」的有 36 条（剔除合集）。按类型分：

- **遗物**：冰淇淋 Ice Cream、苦无 Kunai、蜥蜴尾巴 Lizard Tail、浑天仪 Orrery、算盘 The Abacus、工具箱 Toolbox（`PN 2024_05_17`）；古茶具套装 Ancient Tea Set、药水腰带 Potion Belt、白兽雕像 White Beast Statue（`PN 2024_05_24`）；准备背包 Bag of Preparation、皇家枕头 Regal Pillow、潘多拉魔盒 Pandora's Box、双节棍 Nunchaku（`PN 2024_07_05`）；硫磺 Brimstone、诅咒钥匙 Cursed Key、壶铃 Girya（`PN 2024_10_10`）；Sozu（`PN 2024_11_01`）；Emotion Chip、Gold Plated Cables（`PN 2025_05_08`）；铜鳞 Bronze Scales（`PN 2025_10_16`）；化学物 X Chemical X（`PN 2025_11_20`）；赤牛 Akabeko（降为罕见）和 Tough Bandages（`PN 2026_01_29`）
- **卡牌**：Secret Weapon、Secret Technique（`PN 2024_06_14`）；Evolve（`PN 2025_05_15`，原铁甲卡，现在给 Defect）；Power Through（`PN 2025_12_11`，原铁甲卡，现在给 Defect）；Barrage（`PN 2026_01_22`）；Chill（`PN 2026_01_29`）；Expertise（`PN 2026_02_05`）
- **规则**：开局直接见涅奥（`PN 2025_05_15`）；宝箱房生成规则（`PN 2024_11_14`）；首次见齐所有 Boss 前每幕 Boss 不重复（`PN 2025_07_31`）；第 6 层不刷精英（`PN 2026_03_26`）；A10 双 Boss（`PN 2026_01_15`）

**与一代对比（凭公开知识）**：二代的策略是**先做全新内容，再按需要把一代的经典件「请回来」**，而不是从一代内容出发做减法。一代遗物大多是在 2024-05 到 2025-11 之间陆续回归的。**推断**其中一部分是用来填新系统（比如时间线解锁池）留下的空位：`PN 2025_07_31` 导语写着「解锁机制暴露出我们需要更多内容」，那次一口气补了 17 个遗物和 4 瓶药水，但其中只有铜钹 Tingsha 一个是一代回归（上面的遗物清单也漏了它），其余都是新遗物。

---

## 4. 平衡改动统计

### 4.1 各阶段的动作分布（剔除合集，不含导语）

| 阶段 | 新增 | 删除 | 重做 | 改名 | 回退 | 加强 | 削弱 | 加强 / 削弱 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 Unity | 178 | 29 | 31 | 3 | 0 | – | – | – |
| P1 Godot 重启 | 201 | 31 | 120 | 9 | 0 | 41 | 39 | 1.05 |
| P2 结构化 | 137 | 39 | 82 | 8 | 1 | 99 | 72 | 1.38 |
| P3 联机→EA | 482 | 131 | 208 | 58 | 0 | 329 | 275 | 1.20 |
| P4 EA | 101 | 8 | 42 | 1 | 5 | 131 | 74 | 1.77 |

按年看加强 / 削弱：2024 年是 124/83，2025 年是 278/251，2026 年是 198/126。**EA 后明显偏向加强**：官方说过「基础难度现在相当高……我们在逐步让低进阶更容易，高进阶略难」（`PN 2026_04_26`）。上线后第一个大补丁以压制无限连为主（`PN 2026_03_19`，加强 37 条，削弱 25 条），加强仍多于削弱；EA 后唯一一份削弱多于加强的是 `PN 2026_04_09`（加强 2、削弱 4）。另外，EA 后以 Reverted 开头的「回退」条目有 5 次，比如幻象 Mirage 和创世之柱 Pillar of Creation「恢复到 0.109.0 之前的版本」（`PN 2026_07_30`）。但内测期也有回退：Entrench「reverted to its previous version」（`PN 2024_10_10`，即上表 P2 那 1 次）、Grand Finale 卡池「changed back」（`PN 2025_04_25`）、Blade of Ink 改名又改回（`PN 2026_01_01`）、Golden Pearl「changed back」（`PN 2026_01_22`）。EA 后回退更常见、写得更明，但不是「只在 EA 后出现」。

### 4.2 被提及最多的实体 Top 30

口径：剔除合集和导语；剔除关键词式实体，比如力量、易伤、灾厄 Doom、奥斯提 Osty、角色名、幕名，否则全被它们占满（奥斯提 186 次，力量 168 次，灾厄 126 次）。「平衡段」= BALANCE 加 CONTENT_BALANCE；「主语」= 该条目里第一个被提到的实体；完整表见 `ch08_patch_top_entities.csv`。

| # | 名称 | 类型 | 总提及 | 平衡段 | 作主语 | 修 Bug | 涉及补丁 | 首次 → 末次 |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | 涅奥 Neow | 古神 | 168 | 62 | 47 | 40 | 76 | 2023-05 → 2026-07 |
| 2 | 特兹卡塔拉 Tezcatara | 古神 | 52 | 19 | 19 | 13 | 34 | 2024-05 → 2026-08 |
| 3 | 仪式兽 Ceremonial Beast | Boss | 47 | 12 | 12 | 13 | 35 | 2023-04 → 2026-05 |
| 4 | 实验体 Test Subject | Boss | 45 | 6 | 6 | 25 | 33 | 2024-08 → 2026-07 |
| 5 | 佩尔 Pael | 古神 | 44 | 11 | 8 | 5 | 31 | 2024-05 → 2026-07 |
| 6 | 欧洛巴斯 Orobas | 古神 | 43 | 8 | 6 | 11 | 28 | 2024-09 → 2026-02 |
| 7 | 偷窃草蜢 Thieving Hopper | 怪物 | 41 | 16 | 16 | 17 | 31 | 2023-04 → 2026-05 |
| 8 | 知识恶魔 Knowledge Demon | Boss | 39 | 14 | 14 | 13 | 32 | 2024-08 → 2026-07 |
| 9 | 打击 Strike | 卡 | 38 | 13 | 7 | 8 | 28 | 2023-06 → 2026-05 |
| 10 | 坦克斯 Tanx | 古神 | 37 | 14 | 9 | 7 | 31 | 2024-09 → 2026-07 |
| 11 | 瓦库 Vakuu | 古神 | 35 | 8 | 6 | 13 | 14 | 2026-01 → 2026-08 |
| 12 | 诺奴佩普 Nonupeipe | 古神 | 32 | 16 | 12 | 5 | 23 | 2025-07 → 2026-08 |
| 13 | 女王 Queen | Boss | 30 | 13 | 11 | 6 | 24 | 2024-04 → 2026-04 |
| 14 | 君王之剑 Sovereign Blade | 卡 | 30 | 7 | 3 | 13 | 24 | 2024-06 → 2026-05 |
| 15 | 达弗 Darv | 古神 | 27 | 12 | 4 | 7 | 23 | 2024-11 → 2026-07 |
| 16 | 茂密的植被 Dense Vegetation | 事件 | 25 | 3 | 3 | 13 | 19 | 2023-05 → 2026-04 |
| 17 | 踩踏 Stomp | 卡 | 24 | 13 | 3 | 3 | 20 | 2024-06 → 2026-05 |
| 18 | 灵魂枢纽 Soul Nexus | 怪物 | 23 | 10 | 10 | 9 | 17 | 2023-06 → 2026-06 |
| 19 | 打造时间 Tinker Time | 事件 | 22 | 4 | 3 | 6 | 19 | 2023-08 → 2026-03 |
| 20 | 墨影幻灵 Vantom | Boss | 22 | 11 | 11 | 6 | 18 | 2024-08 → 2026-05 |
| 21 | 瀑布巨兽 Waterfall Giant | Boss | 22 | 12 | 12 | 5 | 15 | 2025-03 → 2026-05 |
| 22 | 残杀千足虫 Decimillipede | 精英 | 21 | 6 | 5 | 12 | 18 | 2023-05 → 2026-07 |
| 23 | 蜂群术士 Entomancer | 精英 | 20 | 9 | 9 | 3 | 17 | 2023-02 → 2026-04 |
| 24 | 重压 Flatten | 卡 | 20 | 12 | 10 | 1 | 19 | 2023-09 → 2026-02 |
| 25 | 魂缚 Bound | 苦难 | 20 | 7 | 1 | 10 | 16 | 2024-04 → 2026-04 |
| 26 | 唤起 Invoke | 卡 | 19 | 2 | 2 | 5 | 16 | 2025-02 → 2026-02 |
| 27 | 异蛙寄生虫 Phrog Parasite | 怪物 | 18 | 9 | 9 | 6 | 16 | 2023-04 → 2026-07 |
| 28 | 棘刺蟾蜍 Spiny Toad | 怪物 | 18 | 7 | 7 | 4 | 16 | 2023-05 → 2026-01 |
| 29 | 黑洞 Black Hole | 卡 | 18 | 9 | 9 | 4 | 17 | 2024-05 → 2026-02 |
| 30 | 历战假人 Battleworn Dummy | 事件战斗 | 17 | 6 | 6 | 8 | 15 | 2023-02 → 2026-07 |

分类型看平衡段（mentions_balance）的前几名：

- **卡**：打击 13、踩踏 13、重压 12、征服者 Conqueror 10（其中削弱 6 次）、黑洞 9、护卫 Bodyguard 9、纠缠 Haunt 9、战栗 Tremble 9、捕捉灵魂 Capture Spirit 8、守墓人 Grave Warden 8、余烬 Cinder 8、星尘 Stardust 8、星位序列 Alignment 8、天穹之力 Celestial Might 8。
- **怪物 / Boss**：偷窃草蜢 16、知识恶魔 14（其中重做 8 次）、女王 13、仪式兽 12、瀑布巨兽 12、墨影幻灵 11、灵魂枢纽 10、猎人杀手 Hunter Killer 10、旧日雕像 Bygone Effigy 10。
- **遗物**：坦克斯的哨子 5，历史课、臂甲、吃不完的糖、音叉、骇人头盔、君王矿石各 4。遗物的平衡改动**少而散**，大部分改动以重做或改名的形式出现。
- **事件**：共生体 Symbiote 7、历战假人 6，蘑菇饥渴、无尽传送带、重拳出击各 5。
- **已删除实体**（legacy）：完美反射 Perfect Reflection 7，Brainbug、Telepathic Spiders、Cursed Choice、Carve Ghost 各 6，Doormaker 在平衡段出现 4 次，但总共被提到 13 次。

### 4.3 解读

- **卡牌平衡是「广撒网、小步走」**。BALANCE 段 2,607 条（含 CONTENT_BALANCE）里有 1,039 条的第一个实体是卡，但单卡最多也只被调了 13 次。596 张卡（加上被删的约 155 张）几乎张张都动过，却没有哪张被反复折腾。和第 2 章的「数值曲线」对照看会更明白：这说明卡牌数值是**按曲线批量校准**的，单卡异常才单独处理。
- **怪物和古神是「重点反复打磨」**。偷窃草蜢一只普通怪就有 16 条平衡记录；最典型的一次是 `PN 2026_02_26` 给它定了一套偷牌优先级（「只偷你牌组里的牌……优先罕见牌，其次普通、稀有、事件牌，再次基础和任务牌」），这类机制细节在卡牌上很少见。涅奥的平衡提及数 62 远超所有对象，原因是开局祝福直接决定整局的走向（见第 5 章）。
- **修 Bug 提及高、平衡提及低的对象**（实验体修 Bug 25 次、平衡 6 次；君王之剑 13 / 7；茂密的植被 13 / 3）都是**实现复杂的多阶段机制**。设计复杂度会直接转化成测试成本。

---

## 5. 设计方向的变化（关键案例）

### 5.1 「复杂度阈值」：被删的 Boss

`PN 2026_05_07`：「Doormaker 的战斗虽然有有趣的微观决策，但**超出了我们想要的复杂度阈值**，而且有遗留问题。我们决定推倒重来。」在此之前，它在 7 个月里被重做了 4 次，理由依次是「战斗太随机」（`PN 2026_03_26`）、「Grasp 回合太弱，整场变成熬到第 4 回合」（`PN 2026_04_02`）、「保留麻烦的能力但降低压迫感」（`PN 2026_04_09`）。替代它的永世沙漏 Aeonglass 在主分支上线前又调了一轮招式（`PN 2026_05_21`）。

**可借鉴**：给 Boss 设一个明确的复杂度上限，比如「同时追踪的状态数」「每回合需要读的信息量」。改了 3～4 轮还收敛不了，就换一只，不要死磕。

### 5.2 机制从「新 Buff 词」退回到「已有词」

- 临时力量：「告别老朋友 Strength Down 能力。临时力量会在回合结束时以来源命名的独立能力显示」（`PN 2025_09_18`）。代码注释说得更直白：「以前叫 Strength Down……我们换成这个模型是为了让玩家体验更清楚：力量和临时力量都是增益」（`MegaCrit.Sts2.Core.Models.Powers/TemporaryStrengthPower.cs:20-21`）。敏捷和集中也跟着改了（`PN 2025_10_16`「为临时敏捷和临时集中加入专属能力」）。本地化里还留着 `DEXTERITY_DOWN_POWER`、`FOCUS_DOWN`、`RESTORE_DEXTERITY`、`RESTORE_FOCUS` 这些旧 key（见 6.2）。
- 亡灵契约师早期用过自造的「护盾 Shield」（`PN 2023_09_08`），后来全部回归格挡体系；储君的「引力」机制 2024-05 起被淘汰；包里零引用的 `GravityPower` 是引力井 Gravity Well 卡的增益能力，引力井在 `PN 2025_12_11` 弃用后它才成了死件（见 6.3）。
- 设计师对稀有度的表述（`PN 2026_03_26`，Anthony）：「普通遗物不一定更弱，但通常是对大多数牌组都有价值的简单效果；稀有度越高，越允许更复杂、对构筑和出牌决策影响更大的效果。」

### 5.3 数据驱动的平衡说明（EA 后）

| 改动 | 设计师给的理由（出处） |
|---|---|
| 杂技 Acrobatics 从普通升到罕见 | 「作为普通卡一直同时主导胜率和选取率；同类的 Skim、Parse、Glimmer、Burning Pact 都不是普通」（`PN 2026_04_09`） |
| 战鼓 Drum of Battle 重做 | 「此前是铁甲选取率最低的罕见卡」（`PN 2026_04_26`） |
| Conflagration 重做 | 「作为稀有卡，选取率低、胜率中等；而且关心出牌数的效果更像静默的东西」（同上） |
| 删掉擒抱 Grapple，巨像 Colossus 降为罕见 | 「专门提高铁甲生存能力」；罕见要腾位置，擒抱「影响太低，还和 Juggernaut 重复」（`PN 2026_04_09`） |
| A6 从减少营火（Gloom）改成删卡加价（Inflation） | 「通过进阶影响地图生成越来越像是失误：玩家很难分清是进阶造成的，还是地图运气差」（`PN 2026_04_02`） |
| 精英刷新层数修正 | 「涅奥现在算地图第一层，所以精英一直比设计早一层刷出来」（`PN 2026_03_26`） |
| Doormaker 不急着改 | 「看了数百万局，Doormaker 的整体难度和胜率处在合适位置，比其他第三幕 Boss 略弱」（`PN 2026_04_26`） |

对比 2025-09 的「现在每天大约 50 局」（`PN 2025_09_25`），EA 后的样本量涨了几个数量级，平衡方法也从「看反馈」变成了「看选取率、胜率和击杀率」。

**可借鉴**：卡牌按「同族对照」定稀有度（杂技和 Skim、Parse 等同族卡比较）；进阶效果必须让玩家**可感知、可归因**（A6 那条）。这两条可以直接写进我们的平衡准则。

### 5.4 改名潮与命名冻结

- 改名表：`ch08_patch_renames.csv` 一共 252 条（核查时补抓了原脚本漏掉的「Renamed the following …:」列表项，原为 174）。按月统计：2026-01 有 59 条，2025-08 有 42 条，2026-02 有 29 条，2025-12 有 27 条，2025-05 有 21 条，2025-09 有 18 条；EA 后只有 3 条。
- 节点：「很多卡更新了名字，因为我们在为翻译准备内容」（`PN 2025_12_18`）；「遗物大改名：第二部」（`PN 2026_01_15`，一份补丁里改了 42 个遗物）；法语和简中随后上线（`PN 2026_01_29`）。
- 早期的改名是把开发代号换成正式名：「小蟾蜍 → 小啃兽 nibbit、邪恶雕像 → 旧日雕像 bygone effigy、可怕食肉者 → mawler、byrdlett → byrdpip」（`PN 2023_05_05`，导语原话是「命名开始了」）。
- 典型连锁改名：Vlad → Zlatir（`PN 2024_06_29`）→ Vakuu（`PN 2026_01_01`）；Death's Visage → Fear，同一次补丁里原来的 Fear 改成 Defy（`PN 2025_12_18`）；Blade of Ink → Blackened Blade（`PN 2025_12_11`）→ 改回 Blade of Ink（`PN 2026_01_01`）。

**可借鉴**：本地化开工前设一个「命名冻结」节点，把改名集中在冻结前的一两个月做完。二代就是这样，改名在冻结前达到峰值，EA 后只剩零星几条。

### 5.5 被做出来又拿掉的东西

| 东西 | 做出来 | 拿掉 | 说明 |
|---|---|---|---|
| 古神提供 Boss 遗物 | `PN 2024_05_24` | `PN 2024_05_31` | 只存在了一周，改由囤积者提供 |
| Boss 专属遗物 | `PN 2025_01_16`（Blessed Antlers 等 5 个） | `PN 2025_01_30`（弃用 Boss 遗物奖励） | Blessed Antlers 后来成了诺奴佩普的祝福遗物（最晚见于 `PN 2025_08_21`「Nonupeipe's Blessed Antlers blessing」），`PN 2026_01_01` 又重做了一次 |
| 传奇卡稀有度 | `PN 2024_09_12` | `PN 2025_02_06` | 换成 Ancient 稀有度 |
| 进阶 Intruder Alert / Warden / Gatekeeper / Gloom | `PN 2024_10_24` / `PN 2025_01_30` / A10 / A8 | `PN 2024_12_12` / `PN 2025_12_11` / `PN 2025_12_11` / `PN 2026_04_02` | 进阶列表重排了 6 次以上，现行 10 级见第 6 章 |
| 亡灵契约师换位 | `PN 2023_09_08` | `PN 2024_05_04` | 「不再换位！」 |
| Scrap 充能球 | `PN 2025_04_25` | `PN 2025_07_03` | 换成 Glass 球 |
| 慢速模式 Slow Mode | — | `PN 2025_10_30` | 从设置里删掉 |
| 成就 | — | `PN 2026_01_22`（「EA 期间会禁用」）、`PN 2026_02_26`（EA 临时禁用） | 代码里成就系统仍在，见第 6 章 |
| 「Prismatic」修饰符 | — | `PN 2025_12_04` | 弃用 |

---

## 6. 代码里的遗迹：被砍了什么、什么还没上线

### 6.1 `Deprecated*` 类是墓碑，不是仓库

14 个 `Deprecated*` 类**都不装被删的内容**。它们是「找不到 id 时的替身」：存档或对局历史里引用了已删除的 id，读档时就用它顶上，避免崩溃。

| 类 | 内容 | 用途和出处 |
|---|---|---|
| `DeprecatedCard` | 0 费状态牌，消耗，「抽 1 张牌，并把这张牌从牌组移除」 | 「如果你正在进行的对局里有牌因为更新被删，会替换成已弃用卡」（`PN 2026_03_19`）；`MegaCrit.Sts2.Core.Models.Cards/DeprecatedCard.cs:14-34`；在出牌队列里也会兜底（`MegaCrit.Sts2.Core.Nodes.Combat/NCardPlayQueue.cs:171`） |
| `DeprecatedCardPool` | 只有 1 张 DeprecatedCard；Title 复用 `"token"` | `MegaCrit.Sts2.Core.Models.CardPools/DeprecatedCardPool.cs:8-20` |
| `DeprecatedRelic` / `DeprecatedRelicPool` | 稀有度 None，可叠加 | 对局历史显示用（`MegaCrit.Sts2.Core.Nodes.Screens.RunHistoryScreen/NRelicHistory.cs:152`） |
| `DeprecatedPotion` / `DeprecatedPotionPool` | 稀有度 None，仅战斗中可用 | 「主要用于对局历史」（`DeprecatedPotion.cs` 注释） |
| `DeprecatedMonster` | HP 0，单招式 `STUB`，隐藏意图 | `MegaCrit.Sts2.Core.Models.Monsters/DeprecatedMonster.cs:13-27` |
| `DeprecatedEncounter` | 无怪物 | 排除在随机池外（`MegaCrit.Sts2.Core.Rooms/RoomSet.cs:148-156`），Boss 位兜底（`MegaCrit.Sts2.Core.Models/ActModel.cs:405-409`） |
| `DeprecatedEvent` / `DeprecatedAncientEvent` | 无选项；古神版本的 `DefineDialogues` 直接抛 `NotImplementedException` | 对局历史（`NRunHistory.cs:678,765`） |
| `DeprecatedCharacter` | 不可玩；1000 HP、100 能量；临时卡池 `MockCardPool` | 图标借用铁甲战士（`MegaCrit.Sts2.Core.Models.Characters/DeprecatedCharacter.cs:14-40`） |
| `DeprecatedAct` | 0 房间，Index −1，没有 Boss 和事件 | 幕兜底 |
| `DeprecatedEnchantment` / `DeprecatedModifier` | 空类 | 兜底 |

统一入口在 `MegaCrit.Sts2.Core.Saves/SaveUtil.cs:23-113`，写法都是 `ModelDb.GetByIdOrNull<X>(id) ?? ModelDb.X<DeprecatedX>()`。

**设计观察**：「下架」分两种。**软下架**是把类保留、只从池里拿掉，比如遭遇 `TunnelerNormal` 的类还在，但已经没有任何幕引用它，对应 `PN 2026_04_09`「从巢穴弃用 Tunneling Twosome」。**硬删除**是把类删掉，靠墓碑兜底。玩家手上的旧档两种情况都能读。对一个持续更新的长线游戏来说，这套墓碑机制几乎是零成本的。

### 6.2 本地化残留 = 已删内容名单

本地化 key 还在、但代码里已经没有对应类的 id（对比 `localization/eng/*.json` 和 `data/csv/*.csv`，Mock 已排除）：

| 类别 | 残留 id 数 | 名单（括号里是补丁记录的删除日期） |
|---|---:|---|
| 卡 | 22 | Despair（`PN 2024_05_10`）、Ghost Eater（`PN 2024_11_01`）、Good Instincts、Swift Strike（`PN 2024_06_07`）、Pity、Warp Space（`PN 2024_05_24`）、Quick Slash（`PN 2024_08_16`）、Reserves（`PN 2024_05_04`）、Star Blast、Visions of Grandeur（`PN 2024_06_14`）、Star Shield（`PN 2024_06_07`）、Veteran（`PN 2025_01_30`）、Flame in the Dark、Tezcatara's Might、Immortality、Pael's Strike（古神卡，2024-05～06）、Sharp Edge（改名 Phantom Blades，`PN 2025_06_12`）、Off by One（`PN 2025_07_31`）、Chrysalis、Spiked、Impale、Training Strike |
| 遗物 | 7 | Ink Bottle（`PN 2025_12_18`）、Endless Appetite（`PN 2025_10_02`）、Red Vine Tea（`PN 2025_09_25`）、Vine Bracelet（`PN 2023_06_09` 有美术记录）、Glowing Orb、Cursed Kettle、Mysterious Cocoon |
| 怪物 | 8 | The Dreamer（被 Doormaker 取代，`PN 2025_10_16`）、Gem Eater（`PN 2025_05_22` 加入的遭遇）、Hatchling、Byrdonis Nest（现在是事件）、Cocoon、Gazing Moth、The Arm、The Bell |
| 能力 | 30 | 多数是被删卡留下的能力，比如 A Thousand Cuts、Adaptation、Read the Bones、Reflective Fortress、Winged Jump；还有一组是旧的「X Down / Restore X」体系（见 5.2） |
| 遭遇 / 修饰符 | 2 / 1 | FLYCONID_WEAK、OVERGROWTH_WILDLIFE / BINARY |

注意：**Doormaker 的本地化已经被清掉了**，`monsters.json`、`encounters.json`、`bestiary.json` 里都搜不到它。也就是说，主分支大更新 2 删它的时候是连 key 一起删的，上面这份名单只是「删得不干净」的那部分。

### 6.3 没有任何引用的类（代码里的死件）

在全部 `.cs` 中按标识符做交叉引用，排除自身文件和反射注册表 `AbstractModelSubtypes.cs`：

| 类 | 是什么 | 对应的历史 |
|---|---|---|
| `GravityPower` 引力 | 「本回合每打出一张牌，对所有敌人造成 2 点伤害」，玩家增益 | 引力井 Gravity Well 卡打出后给的能力（类注释提到 Gravity Well；`PN 2025_01_23`「wears off at the end of your turn」、`PN 2025_07_17`「Gravity now counts as a buff for the player」），引力井 2025-12 被删（`PN 2025_12_11`）后成为死件。和 2024-05 开始淘汰的那套引力机制（`PN 2024_05_04`）不是一回事 |
| `LeadershipPower` 领袖气质 | 「所有其他盟友额外造成 1 点伤害」 | 为 Lieutenant 敌人做的（`PN 2023_06_09`），Lieutenant Knight 战斗在 2025-01 被删（`PN 2025_01_16`） |
| `MagicBombPower` 魔法炸弹 | 「回合结束时受到 20 点伤害；魔法骑士死亡则移除」 | 魔法骑士 Magi Knight 的旧招式（`PN` 里有多条相关修复） |
| `NoEnergyGainPower` 无法获得能量 | 「本回合无法再获得能量」 | 推断是 Expect a Fight 旧版「本回合不能再获得能量」留下的（`PN 2026_03_19`）；这张卡在 `PN 2026_08_13` 被改成格挡卡 |
| `TunnelerNormal` 遭遇 | Tunneler + Chomper | 软下架（`PN 2026_04_09`） |
| `TheAdversaryMkOne/Two/Three` 对手 1～3 型 | HP 100/200/300，各 3 个招式，开场获得 0/1/2 层人工制品 | 补丁说明里出现过两次：`PN 2025_11_20`「Nerfed Adversary: Artifact decreased from 1/2/3 -> 0/1/2」（和当前代码一致，说明内测服上打得到过），`PN 2026_01_08`「Adjusted placeholder Adversary assets」；美术只有 `images/monsters/the_adversary_placeholder.png` 占位图；本地化里名字和招式名齐全（`localization/eng/monsters.json:397-408`；`bestiary.json` 只有通用界面文本，没有逐怪条目）。**推断**：内测服上出现过、当前没接入任何遭遇，是待上线还是已砍无法判断；「Mk 1→3」像是随进程升级的同一个对手 |
| `OneHpMonster` / `TenHpMonster` / `SingleAttackMoveMonster` / `MultiAttackMoveMonster` | 测试怪 | 单元测试用（见 6.4） |

其它没清干净的引用：

- `ModelDb.Orbs` 静态列表只有闪电、冰霜、黑暗、等离子 4 种球，没有 Glass，而且全代码零引用（`MegaCrit.Sts2.Core.Models/ModelDb.cs:286-292`）。这是 Glass 球加入（`PN 2025_07_03`）之前的旧清单。
- `AncientEventModel.cs:153` 仍然引用本地化 key `WAX_CHOKER.blockMessage`，但 `relics.json` 里已经没有这个 key 了。这个遗物在 `PN 2026_01_15` 改名「Wax Choker → Toy Box」，属于改名后遗留的悬空引用（第 3 章发现，本章复核）。不过触发这句提示的钩子 `Hook.ShouldAllowAncient`（`MegaCrit.Sts2.Core.Hooks/Hook.cs:2269`）目前没有任何模型覆写，所以这条路径实际上走不到，不会报错（第 5 章发现）。
- 「宝箱行换成精英」的地图参数 `ShouldReplaceTreasureWithElites`，注释写着「用于 Warden 进阶」（`MegaCrit.Sts2.Core.Map/StandardActMap.cs:71,83`），但正式流程永远传 `false`（`MegaCrit.Sts2.Core.Runs/RunManager.cs:828`）。对应的历史是 Warden 进阶在 `PN 2025_01_30` 加入，`PN 2025_12_11` 被换成 Tight Belt（第 5 章发现，本章复核）。

第 1 章还发现 3 个钩子接口在内容里**没有任何实现**：`ShouldPayExcessEnergyCostWithStars`（用星星支付超出的能量费用，`MegaCrit.Sts2.Core.Hooks/Hook.cs:2499`）、`ShouldEtherealTrigger`（`Hook.cs:2439`），以及从未被实例化的 `UnknownIntent`（`MegaCrit.Sts2.Core.MonsterMoves.Intents/UnknownIntent.cs:3`）。**推断**：「星星补能量」和储君早期「能量 + 星星」的双费用设计有关（`PN 2024_08_30`：Prophesize「0 能量 2 星 → 2 能量 0 星」），也可能是给 Mod 留的接口。

### 6.4 `*.Mocks`：可测试性是架构的一部分

| 目录 | 类数 | 例 |
|---|---:|---|
| `Models.Powers.Mocks` | 18 | `MockExtraTurnPower`、`MockScaleInMultiplayerPower`、`MockResetCombatOnShufflePower` |
| `Models.Cards.Mocks` | 8 | `MockAttackCard`、`MockTurnEndInHandRecorderCard` |
| `Models.Encounters.Mocks` | 8 | `MockBossEncounter`，用的是 `BigDummy` 怪 |
| `Models.Monsters.Mocks` | 6 | `MockReattachMonster`、`MockIntangibleMonster`（外观借 Defect 的场景，`MockAttackMonster.cs:15`） |
| `Afflictions/Orbs/Potions/Enchantments/Events.Mocks` | 3/2/1/1/1 | `MockDiscardAndAddShivsPotion` |
| `Saves.Test` | 2 | `MockGodotFileIo`、`MockCloudGodotFileIo` |

- `TestSupport/` 一共 9 个类。其中 `TestMode` 的注释说明测试由 `RiderTestRunner/` 下的 CiCoreRunner/NetCoreRunner 场景启动（`MegaCrit.Sts2.Core.TestSupport/TestMode.cs:17-27`）；`TestMode.IsOn/IsOff` 在游戏代码里被调用了 **386 次**。另有 `TestRngInjector`（注入随机数）和 `TestCardSelector`（模拟玩家选牌）。
- 测试角色：`Deprived` 的数值是 1000 HP、100 能量（`MegaCrit.Sts2.Core.Models.Characters/Deprived.cs:26,30`），卡池默认是 `DeprivedCardPool`，测试时可以换成 `MockCardPool`（`Deprived.cs:32-40`），池的 Title 是 `"test"`（`MegaCrit.Sts2.Core.Models.CardPools/DeprivedCardPool.cs:11`），和墓碑 `DeprecatedCharacter` 是同一套「无敌测试员」数值。
- Mock 的本地化 key 也一起打进了正式包（`MOCK_ATTACK_CARD` 等 31 个），图集加载器专门跳过 `mock_` 开头的缺图告警（`MegaCrit.Sts2.Core.Assets/AtlasResourceLoader.cs:207`）。
- 补丁里能看到测试文化：最早一份就有「修复不稳定的 0 费药水测试 #STS-4935」「Limit Break 测试报错」（`PN 2023_02_09`）；`PN 2023_04_21` 有「为 Flame Barrier 加简单测试」。

**可借鉴**：卡牌规则能在无界面的单元测试里跑通，是二代敢于周更、反复重做角色的底气。数百张卡的回归测试靠人肉是覆盖不了的。（架构细节见第 7 章。）

### 6.5 调试遗迹

| 位置 | 内容 | 要点 |
|---|---|---|
| `MegaCrit.Sts2.Core.Debug/`（19 个类） | `DebugSettings`（环境变量 `STS2_DEV_SKIP` 跳过片头和时间线，`STS2_DEV_WINDOWED` 强制窗口化，注释说「nix 开发 shell 会导出它」）、`DebugActMap`（按 `[` 键重生成密林地图）、`NCombatVfxSpawner`、`NBgLayerDebug`、`NTrailTest`、`ReleaseInfoManager`、`SentryService` | `DebugSettings.cs:9-26`；`DebugActMap.cs:44-60`；`IgnorePackedImages` 注释写着「提交前记得改回 false，否则测试会失败」 |
| `MegaCrit.Sts2.Core.Nodes.Debug/`（11 个类）+ `.Multiplayer`（2 个类） | 开发者控制台 `NDevConsole`（1,645 行）、FPS 可视化（「只在编辑器里显示」，`PN 2024_09_12`）、粒子计数、宽高比调试、充能球和特效测试台、场景引导器、联机测试 | 控制台约有 41 个命令类（`MegaCrit.Sts2.Core.DevConsole.ConsoleCommands/`），详见第 7 章 |
| `MegaCrit.Sts2.Core.Audio.Debug/` | `NDebugAudioManager`（直接播放 mp3 / wav 的旁路播放器）、`TmpSfx`（列出 29 个临时音效） | 见下 |
| PCK `scenes/debug/`（21 个文件） | `combat_vfx_playground.tscn`（492 KB，最大）、`whole_screen_vfx_playground`、`debug_act_map`、`dev_console`、`multiplayer_test`、`hitbox_visualizer`、`intent_positioner`、`speech_bubble_positioner`、`vfx/orb_tester` 等 | 这是给美术和特效用的「游乐场」场景 |
| PCK `images/debug/`（7 张） | `fps_happy/neutral/sad.png`、`placeholder_64.png`、`main_menu_bg_alt.png` | — |
| PCK `debug_audio/`（50 个 mp3 + 2 个 wav） | 回合横幅、出牌、消耗、获得遗物和药水、胜利、营火睡觉、挖掘、地图标记、各充能球的生成 / 被动 / 激发 | **仍在使用**：游戏代码里有 54 处 `NDebugAudioManager.Instance(?).Play(...)`（连同 Stop 和音量设置共 61 处引用，分布在 36 个文件），比如获得遗物 `MegaCrit.Sts2.Core.Commands/RelicCmd.cs:49`、消耗 `CardPileCmd.cs:182`、胜利 `NRewardsScreen.cs:396`、敌方回合横幅 `NEnemyTurnBanner.cs:83`、玩偶房事件环境音 `MegaCrit.Sts2.Core.Models.Events/DollRoom.cs:98` |
| PCK `addons/` | `dev_tools`、`megacontentcreator`（自研内容生成面板）、`atlas_generator`（图集生成、迁移场景 UID） | 编辑器插件也打进了包里 |

关于 `debug_audio`：`FmodSfx.cs:5` 的注释写着「任何临时音效或不走 FMOD 的音效都放进 TmpSfx.cs」。可见 EA 版的音频管线是「FMOD 正式 bank + mp3 临时音效」双轨运行；FMOD 里也有一个 `temp_sfx.bank`（1.8 MB）。`PN 2025_11_06` 也说过「给玩偶房、茂密的植被、丛林迷宫事件加了临时音效和特效」。音频管线见第 7 章。

### 6.6 还没上线 / 做了一半的内容

| 证据 | 位置 | 推断 |
|---|---|---|
| `ACT2_B_EPOCH`「Somewhere」、`ACT3_B_EPOCH`「Elsewhere」：「此地将在抢先体验期间揭晓」 | `localization/eng/epochs.json:2-11`；`MegaCrit.Sts2.Core.Timeline.Epochs/Act2BEpoch.cs`、`Act3BEpoch.cs` | 第 2、3 幕会各有一个 B 版本 |
| 5 个角色的 `*8_EPOCH`、`*9_EPOCH` 和 `EVENT4_EPOCH` 全是 `TODO`，也没有对应的类 | `epochs.json:67-249`（TODO 分散在 67-74、87-90、111-118、145-152、194-201、242-249） | 每个角色还有两档纪元没做 |
| 57 个纪元里只有 29 张正式插图，28 张是 `placeholder/` 占位图 | `images/timeline/epoch_portraits/`（见 `ch08_asset_paths_by_entity.csv`） | 纪元美术完成度约一半，补丁里一直在加纪元插图（`PN 2026_05_21`、`PN 2026_07_16`） |
| 古神只有占位立绘 `images/ancients/<名>_placeholder.png`，另有 `under_construction.png`（7 张） | PCK | 古神目前靠背景场景加 Spine 表现（见 7.4），这批是旧占位图 |
| 对手 1～3 型 The Adversary | 见 6.3 | 未接入任何遭遇 |
| 306 条遗物风味文本里有 304 条是「[red]这个遗物的细节将在未来揭晓……[/red]」，只有 Chemical X 和 Circlet 写了正式文案 | `localization/eng/relics.json` 的 `*.flavor`（第 3 章发现，本章复核） | 遗物的世界观文案留到 EA 后期再写 |
| 徽章 `FAVORITE_CARD` 只有本地化文本；`WHOMPER` 有类 `Whomper`，但注释写着「THIS BADGE IS CURRENTLY NOT IN USE」「DESIGN NOTE: Not a great badge because it overvalues a specific archetype」，`IsObtained()` 恒为 false，也不在 `BadgePool` 的 23 个徽章里 | `localization/eng/badges.json`；`MegaCrit.Sts2.Core.Models.Badges/Whomper.cs:5-28`、`BadgePool.cs:10-34` | Whomper 是设计上被否掉的徽章（死件），不是「还没做」；FAVORITE_CARD **推断**是待做的徽章 |
| 新角色和新模式 | `PN 2026_11_13` | 只在 beta 分支，本包没有 |
| 成就 | `PN 2026_02_26` | EA 期间禁用 |

---

## 7. 资源清单（只列路径与统计）

### 7.1 PCK 构成

PCK 一共 15,891 个文件、1,989.1 MB，全部未加密。按「源资源」归并后有 11,809 项：一个 `.import` 加上它在 `.godot/imported/` 下的导入物算 1 项。完整表见 `data/csv/ch08_asset_catalog.csv`。

| 类别 | 源资源数 | MB | 占 PCK | 路径规律 |
|---|---:|---:|---:|---|
| 字体 | 21 | 389.1 | 19.6% | `fonts/[<语言>/]<字体>.ttf\|otf` → `.fontdata` |
| 事件插图 | 80 | 326.8 | 16.4% | `images/events/<事件id>.png`、`<id>_phobia_mode.png` |
| FMOD 音频 bank | 12 | 316.2 | 15.9% | `banks/desktop/<bank>.bank` |
| 房间 / 战斗背景图层 | 243 | 219.5 | 11.0% | `images/rooms/<幕或Boss>/…` |
| 卡图原图 | 624 | 168.5 | 8.5% | `images/packed/card_portraits/<卡池>/<卡id>.png` |
| 背景 Spine（主菜单 / 商店 / 宝箱 / Boss 节点） | 86 | 146.9 | 7.4% | `animations/backgrounds/<场景>/…`、`animations/map/<boss>_boss/…` |
| 角色 Spine（战斗 / 选人 / 商店 / 营火） | 97 | 58.6 | 2.9% | `animations/{characters,character_select,merchant,rest_site}/<角色>/…` |
| 怪物 Spine | 442 | 45.4 | 2.3% | `animations/monsters/<目录>/<名>.skel/.atlas/.png + <名>_skel_data.tres` |
| 特效贴图 | 450 | 39.4 | 2.0% | `images/vfx/<类>/…`、`images/packed/vfx/…` |
| 地图 | 59 | 37.4 | 1.9% | `images/packed/map/map_bgs/<幕>/map_{top,middle,bottom}_<幕>.png` |
| UI 贴图 | 430 | 32.0 | 1.6% | `images/ui/…`、`images/packed/<界面>/…` |
| 卡图图集页 | 2 | 31.7 | 1.6% | `images/atlases/card_atlas_{0,1}.png` |
| 卡图 beta 占位 | 285 | 28.2 | 1.4% | `images/packed/card_portraits/<池>/beta/<id>.png` |
| 其它图集页 | 14 | 25.6 | 1.3% | `images/atlases/<图集>.png` |
| 遗物大图标 / beta | 324 / 52 | 21.0 / 3.4 | 1.2% | `images/relics/[beta/]<id>.png` |
| 能力大图标 | 272 | 17.2 | 0.9% | `images/powers/[beta/]<id>.png` |
| 纪元插图 | 61 | 14.7 | 0.7% | `images/timeline/epoch_portraits/[placeholder/]<纪元id>.png` |
| 古神占位立绘 | 7 | 13.4 | 0.7% | `images/ancients/<名>_placeholder.png` |
| 本地化 | 866 | 11.8 | 0.6% | `localization/<语言>/<表>.json` |
| 怪物静态图（beta / 恐惧症） | 17 | 6.9 | 0.3% | `images/monsters/{beta,phobia_mode}/…` |
| 临时音效 mp3 | 53 | 2.6 | 0.1% | `debug_audio/<名>.mp3`（mp3 原文件和 `.mp3str` 导入物都打进了包） |
| 场景 `.tscn`（生物外观 127 / 背景 204 / 遭遇 24 / 事件 23 / 特效 313 / UI 335 / 调试 21） | 1,047 | 8.9 | 0.4% | `scenes/<类>/…` |
| 着色器（`shaders/` 下 `.gdshader` 90 + `.gdshaderinc` 7 + `.tres` 20 + 1 个 `.gdc` 脚本；另有 10 个 `.gdshader` 在 `scenes/`、`materials/` 下，计入场景 / 材质类，所以 7.7 全包是 100 个）、材质 162、主题 34 | 314 | 0.5 | <0.1% | `shaders/…`、`materials/…`、`themes/…` |
| 图集子图 `.tres` 桩 | 1,891 | 0.5 | <0.1% | `images/atlases/<图集>.sprites/<子图>.tres` |
| 脚本占位（C# 已编译进 `sts2.dll`） | 3,469 | 0.06 | — | `src/Core/…/*.cs`（每个 0～1 字节）、`src/gdscript/*.gdc` |

读表：
- **体积大头不是卡图**。字体里，简中、繁中、日文的思源和 Noto CJK 一套就是 20～58 MB（比如 `NotoSansMonoCJKtc-Regular.otf` 导入后 58.3 MB）。事件插图 75 张用 BPTC 压缩，平均每张约 4.3 MB，属于高分辨率整幅画。
- **卡图存了两份**：图集页（BPTC，31.7 MB）加单张 PNG（无损，168.5 MB）。代码优先从图集取，PNG 只在图集缺图时作为回退（见 7.3）。**推断**：单张 PNG 是 TexturePacker 的输入源，打包时没有剔除，大约 1.7 亿字节是「保险」用的冗余。
- Spine 动画本身不大：怪物的 107 个 `.spskel` 导入物合计 17.7 MB，大头是贴图页。

### 7.2 Godot 导入物与原路径的映射

规则（3,970 个 `.import` 全部验证，`ch08_import_map.csv` 列 `name_rule_ok` 全为 True，没有孤儿导入物）：

```
源路径:      res://images/relics/akabeko.png
映射文件:    res://images/relics/akabeko.png.import     （文本，[remap] 段）
导入物:      res://.godot/imported/akabeko.png-<md5("res://images/relics/akabeko.png")>[.bptc|.s3tc].ctex
```

- `.import` 文本里记着 `importer=`、`type=`，以及 `path=` 或 `path.bptc=` / `path.s3tc=`。`metadata.imported_formats` 写的是 `["s3tc_bptc","etc2_astc"]`，但包里只有桌面格式。
- importer 分布：`texture` 3,555、`spine.atlas` 170、`spine.skel` 164、`mp3` 50、`font_data_dynamic` 20、`image` 7、`wav` 2、`svg` 1、`scene`（gltf）1。
- 贴图格式的取舍（`ch08_import_map.csv` 的 `format` 列）：
  - 卡图单张 PNG 和怪物 Spine 贴图都是 `default`（`vram_texture:false`，无损压缩）；
  - 遗物大图标、事件插图、图集页大多是 `bptc`；
  - 能力图标、地图底图大多是 `s3tc`。
  - **推断**：需要保真的 UI 和角色贴图走无损，大面积背景走 GPU 压缩。
- 外部工具能按这套规则从源路径直接算出导入物名，不必解析 `.import`。

### 7.3 由实体 id 推出资源路径

统一约定：`id` = 类名转 SNAKE_CASE 后取小写（`ModelId.Entry.ToLowerInvariant()`）；`ImageHelper.GetImagePath(x)` = `res://images/` + x（`MegaCrit.Sts2.Core.Helpers/ImageHelper.cs:14-22`）；`SceneHelper.GetScenePath(x)` = `res://scenes/` + x + `.tscn`（`SceneHelper.cs:12-20`）。`ImageHelper` 的文档注释里还举着 `images/cards/bash.png` 这个早已不存在的旧路径当例子，可见卡图后来才改成图集。

| 实体 | 规则（代码出处） | 覆盖情况（`ch08_asset_paths_by_entity.csv`） |
|---|---|---|
| **卡图** | `atlases/card_atlas.sprites/<卡池Title>/<id>.tres`（`MegaCrit.Sts2.Core.Models/CardModel.cs:143`）。卡池 Title：ironclad / silent / defect / regent / necrobinder / colorless / curse / status / event / quest / token；Deprecated 池复用 token（`DeprecatedCardPool.cs:8`）。回退链：图集子图 → `packed/card_portraits/<池>/<id>.png` → `…/<池>/beta/<id>.png` → `card_portraits/beta.png`（`MegaCrit.Sts2.Core.Assets/AtlasResourceLoader.cs:321-359`） | 596 张卡里 583 张命中图集，11 张只有 beta 图（Blaze、Clash、Distraction、Dual Wield、Entrench、Outmaneuver、Outrage、Rebound、Sidestep、Stack、Wither），2 张特殊（DeprecatedCard 本来就没图；疯狂科学 Mad Science 按 Attack/Skill/Power 用 3 张变体图，`MegaCrit.Sts2.Core.Models.Cards/MadScience.cs:69-78`）。另有 282 张卡**同时保留 beta 图**（28 MB） |
| **卡框等** | `atlases/ui_atlas.sprites/card/card_frame_<类型>_s.tres`、`card_portrait_border_<类型>_s.tres`；Ancient 卡用 `compressed_atlas.sprites/ancient_card_border.png.tres`（`CardModel.cs:182-243`） | — |
| **遗物** | 图集 `atlases/relic_atlas.sprites/<IconBaseName>.tres` 加描边图集 `relic_outline_atlas`；大图 `relics/<IconBaseName>.png`，beta 图 `relics/beta/`（`MegaCrit.Sts2.Core.Models/RelicModel.cs:128-138`）。IconBaseName 默认是 id，例外：Looming Fruit 没有丰饶角时用 `_2`（`LoomingFruit.cs:14-23`），Yummy Cookie 按角色切换（`YummyCookie.cs:21-`） | 296/300 命中图集；Forgotten Soul 走 PNG 回退；另有 38 个现役遗物还留着 beta 图 |
| **能力** | `atlases/power_atlas.sprites/<id>.tres`，大图 `powers/<id>.png`（`MegaCrit.Sts2.Core.Models/PowerModel.cs:104-112`）；缺图时用 `powers/missing_power.png` | 263/268（缺的是 3 个临时属性抽象基类、Hyperbeam 专用能力；Underworld 走 beta） |
| **药水** | `atlases/potion_atlas.sprites/<id>.tres` 加描边图集；大图 `potions/large/<id>.png`，缺图时用 `potions/missing_potion.png`（`MegaCrit.Sts2.Core.Models/PotionModel.cs:67-101`） | 64/65（缺的是 DeprecatedPotion） |
| **怪物** | `scenes/creature_visuals/<id>.tscn`（`MegaCrit.Sts2.Core.Models/MonsterModel.cs:217`），场景里引用 `animations/monsters/<目录>/<名>_skel_data.tres`，再串到 `.skel`、`.atlas` 和 `.png` 页；恐惧症皮肤切 Spine skin `phobia/normal`（`MonsterModel.cs:647-653`） | 114/121 有外观场景，其中 109 个用 Spine；缺的 7 个都是测试怪、墓碑或千足虫分段。恐惧症皮肤：Fossil Stalker、Haunted Ship、Skulking Colony、The Obscura、Twig Slime M（`HasPhobiaSpineSkin => true`）；另有 11 张 `images/monsters/phobia_mode/*` 静态替换图（千足虫分段、蜂群术士、异蛙寄生虫、恐怖鳗、无厌沙虫、蠕虫） |
| **角色** | 外观 `creature_visuals/<id>`；选人图标 `packed/character_select/char_select_<id>[_locked].png`；顶栏 `ui/top_panel/character_icon_<id>.png`；地图标记 `packed/map/icons/map_marker_<id>.png`；联机手势 `ui/hands/multiplayer_hand_<id>_{point,rock,paper,scissors}.png`（`MegaCrit.Sts2.Core.Models/CharacterModel.cs:117-173`） | 5 个可玩角色齐全 |
| **事件** | 立绘 `events/<id>.png`（另有恐惧症版 `_phobia_mode`）；背景场景 `scenes/events/background_scenes/<id>.tscn`；特效 `scenes/vfx/events/<id>_vfx.tscn`；布局 `default/combat_event_layout.tscn` 或 `events/custom/<id>`（`MegaCrit.Sts2.Core.Models/EventModel.cs:172-206`） | 68 个事件里 55 张立绘；缺立绘的 13 个基本是古神（改用 8 个背景场景）和墓碑。34 个事件有专属特效场景 |
| **古神地图节点** | `packed/map/ancients/ancient_node_<id>[_outline].png`（`MegaCrit.Sts2.Core.Models/AncientEventModel.cs:111-113`） | 8/8 |
| **幕** | 战斗背景 `scenes/backgrounds/<幕>/<幕>_background.tscn`（`ActModel.cs:249`）；地图三段 `packed/map/map_bgs/<幕>/map_{top,middle,bottom}_<幕>.png`（`ActModel.cs:55-63`）；宝箱 Spine `animations/backgrounds/treasure_room/chest_room_act_<幕>_skel_data.tres`（`ActModel.cs:176`）；音乐 bank 见 7.5 | 4 个正式幕齐全 |
| **遭遇** | 站位场景 `scenes/encounters/<id>.tscn`（`MegaCrit.Sts2.Core.Models/EncounterModel.cs:181`）；Boss 有自己的背景目录 `scenes/backgrounds/<boss>_boss/` | 91 个遭遇里 24 个有站位场景（**推断**：其余按默认排布）；13 个 Boss 和事件战斗有专属背景 |
| **附魔 / 充能球 / 修饰符 / 苦难 / 纪元** | `enchantments/[beta/]<id>.png`（`EnchantmentModel.cs:83-87`）；`orbs/<id>.png` 加 `scenes/orbs/orb_visuals/<id>.tscn`（`OrbModel.cs:112-114`）；`packed/modifiers/<id>.png`（`ModifierModel.cs:63`）；`scenes/cards/overlays/afflictions/<id>.tscn`（`AfflictionModel.cs:62`）；`timeline/epoch_portraits/[placeholder/]<id>.png`（`MegaCrit.Sts2.Core.Timeline/EpochModel.cs:185-187`） | 附魔 22/23、充能球 5/5、修饰符 16/17、苦难 7/7、纪元正式图 29 张 + 占位图 28 张 / 68 个 key |

### 7.4 图集（TexturePacker）

运行时由 `AtlasManager` 解析 `.tpsheet`（JSON）生成子图（`MegaCrit.Sts2.Core.Assets/AtlasManager.cs:12,30,96-142`），`AtlasResourceLoader` 拦截 `res://images/atlases/<图集>.sprites/<子图>.tres` 这类路径（`AtlasResourceLoader.cs:13-14,129`）。包里的 1,891 个 `.sprites/*.tres` 是编辑器用的 AtlasTexture 桩，**推断**由 `addons/atlas_generator` 生成。

| 图集 | 页尺寸 | 子图数 | 说明 |
|---|---|---:|---|
| card_atlas | 4032×4070 + 3780×4032 | 626 | 每张卡图区域 250×190（例：`card_atlas.sprites/ironclad/bash.tres`） |
| relic_atlas / relic_outline_atlas | 3404×780 / 2496×1200 | 346 / 346 | |
| power_atlas | 660×1768 | 271 | |
| intent_atlas | 932×932 | 310 | 意图图标（含帧动画） |
| controller_atlas | 555×555 | 112 | 手柄按键 |
| ui_atlas | 2048×2048 ×2 | 102 | 卡框、地图、顶栏 |
| potion_atlas / potion_outline_atlas | 1679×237 / 164×2615 | 64 / 64 | |
| epoch_atlas / era_atlas / stats_screen_atlas | 822×3236 / 256×256 / 802×256 | 57 / 27 / 16 | |
| compressed / compressed_atlas | 1936×2020 / 1484×1360 | 45 / 55 | Ancient 卡边框、卡面模板、地图元素 |

**图集里的孤儿子图 = 被砍内容的成品美术残留**（`ch08_asset_paths_by_entity.csv` 中 `entity_type=orphan_sprite`）：

- **卡图集**：34 张没有对应模型，另有 9 张是同卡变体。被删卡有 Limit Break、Corpse Explosion、Rabid、Scavenge、Reserves、Royal Corona、The Gambit；改名前的旧名有 Starlight Sword（今君王之剑）、Blackened Blade；**一代卡名**有 Bandage Up、Calm、Deep Breath、Forethought、Insight、J.A.X.、Safety、Smite、Through Violence、Transmutation、Trip、Violence、Wrath、Bite、Expunger、Ritual Dagger、Fame and Fortune、Golden Axe，以及 Defect 的 Consume、Fission、Lightning Mastery、Lock-On、Seek、Self Repair、Thunder Strike。**推断**：这些一代卡在内测期曾作为占位或回归候选画过新图，最后没进卡池。
- **遗物图集**：43 张没有模型，另有 7 张变体。包括补丁里记录过删除的 Collector's Deckbox、Inaccurate Ephemeris、Matryoshka（`PN 2024_11_14`）、Pointed Hat、Pael's Blob（`PN 2024_12_05`）、Bird Faced Urn（`PN 2025_05_01`）、Undulating Mass（`PN 2025_07_31`）、Fyshing Float（`PN 2025_09_25`）、Ink Bottle、Thread and Needle、Torii、Blue Candle、Turnip、Osty's Devotion、Neow's Lament；改名前旧名 Amphorae、Tezcatara's Candle、Vakuu's Cape；一代遗物名 Runic Cube、Singing Bowl、Medical Kit、Preserved Insect 等。
- **能力图集**：4 张没有模型（如 Outbreak 能力，对应 `PN 2026_07_30` 起变成技能卡），另有 4 个变体（`*_plus_power`、`missing_power`）。

### 7.5 音频

- **FMOD**（`banks/desktop/`，12 个，316.2 MB）：`Master.bank` 2.1、`Master.strings.bank` 0.03、`act1_a1` 35.5、`act1_a2` 34.9、`act1_b1` 39.4、`act2_a1` 41.8、`act2_a2` 41.9、`act3_a1` 29.9、`act3_a2` 30.9、`ambience` 15.3、`sfx` 42.5、`temp_sfx` 1.8（单位 MB）。每幕的 A 版本有两首可选 BGM，各打成一个 bank（`MegaCrit.Sts2.Core.Models.Acts/Overgrowth.cs:53-55`、`Hive.cs:53-55`、`Glory.cs:49-51`）；暗港只有 `act1_b1`（`Underdocks.cs:48-50`）。
- **旁路 mp3**（`debug_audio/`）：50 个 mp3 + 2 个 wav（`regent_intro.wav` 0.5 MB 最大），`TmpSfx.assetPaths` 只列了其中 29 个（`MegaCrit.Sts2.Core.Audio.Debug/TmpSfx.cs:9-15`），充能球的 `<球id>_channel/passive/evoke.mp3` 由 `MegaCrit.Sts2.Core.Models/OrbModel.cs:73-77` 按 id 拼名，用途见 6.5。注意 `glass_orb_*.mp3` 和 `frost_orb_*.mp3` 的字节数完全相同，但 md5 不同。**推断**：玻璃球的音效是从冰霜球复制改出来的占位。

### 7.6 字体

`fonts/` 下有 20 个字体：kreon_regular/bold、bitter_medium_italic、spectral_bold、source_code_pro_medium/semibold（拉丁）；俄文 FiraSansExtraCondensed ×3；日文 NotoSansCJKjp ×3；韩文 GyeonggiCheonnyeonBatangBold；泰文 CSChatThaiUI；**简中** NotoSansMonoCJKsc-Regular（57.6 MB）、SourceHanSerifSC-Bold/Medium（44.2/23.7 MB）；繁中同理（3 个，126.9 MB）。字体清单见 `fonts/preload_manifest.json`。最早的补丁就有「删掉过时的 Kreon 字体」（`PN 2023_02_09`），但 kreon 至今仍在包里。

### 7.7 着色器

一共 127 个文件：`.gdshader` 100 个、`.gdshaderinc` 7 个、着色器 `.tres` 20 个；类型上 `canvas_item` 116、`spatial` 2。全表见 `ch08_shaders.csv`，含引用次数。

- **引用最多**：`shaders/hsv.gdshader`（被 119 个场景或资源引用，**推断**是通用调色）、`shaders/vfx/vfx_stepped_shader_fire_add.tres`（45）、`vfx_water_reflection.gdshader`（39）、`common/vfx_flipbook_shader.gdshader`（36）、`vfx_stepped_shader_fire_flat.tres`（15）、`wind_sway.gdshader`（14）。
- **顶层 40 个**：通用效果有 `dissolve`、`fade_transition`、`texture_transition`、`radial_blur`、`Blur`、`dark_blur`、`canvas_group_mask_blur`、`overlay_blend`、`colorize_addblend`、`image_mask`、`alpha_from_grayscale`、`outline_texturerect`；玩法相关有 `doom_bar`、`doom_overlay`、`power`、`power_flash_vfx`、`relic`、`card_ripple`、`enchantment_tab_appear`、`scry_reveal`、`button_pulse`、`ftue_popup`；地图相关有 `boss_map_point[_placeholder]`、`normal_map_point`、`line_draw`、`line_erase`；场景相关有 `glory_bg_scrolling`、`neow_water_reflection`、`rest_site_light_shader`、`wind_sway`、`wiggle`、`oil`、`necrobinder_flame`、`the_insatiable_sand_fall`、`devoured`、`crystal_sphere_item`、`scrolling_smoke`。
- **`shaders/vfx/` 下 87 个**：`_util/` 7 个函数库（bloat、erosion、flipbook、hue_shift、polar、rotate、tiling）；`common/` 13 个通用粒子（flipbook、panning、poof、ray、ring_polar、round_smoke、chromatic_aberration…）；卡牌 UI 有 `ui/card/afflictions/{bound,entangled,galvanized,hexed,ringing,smog}/*`（6 种苦难的卡面效果）、消耗和移除的侵蚀；角色形态 `forms/{demon,echo,reaper,serpent}/*`（对应 `PN 2026_07_30`「角色形态特效」）；怪物专属 `monsters/{aeonglass_ray,amalgam_glare,decimillipede_suck,soul_fysh_soundwave,waterfall_giant_water}`；调试 `debug/` 7 个。

---

## 8. 设计观察与可借鉴

1. **内测期用周更换迭代速度，上线后用 beta 分支换稳定**。二代内测期两年多基本保持周更（P3 阶段平均每份 83 条），EA 一周后就拆成 beta 和主分支两条线（`PN 2026_03_12`），两个月后又改成双周更（`PN 2026_05_07`）。我们的测试服可以照搬：**测试服周更，正式服按季度合并大版本**；合并补丁要单独写成「合集说明」，避免老玩家重复阅读。
2. **大胆删、但删得体面**。约 155 张卡被删，一个 Boss 位换了 3 任，系统做了又拿掉。支撑这种做法的是三件基建：墓碑类（旧档不崩）、软下架（只拿出池、类保留）、上线后的「已弃用卡」占位（玩家手里的牌自动兑换成「抽 1 并自我移除」）。我们做卡牌或 Roguelike 长线运营时，应该在第一版就把这三件做进存档层。
3. **平衡资源向「体验锚点」倾斜**。涅奥的平衡段提及（62 次）约为现役卡均值（约 2.2 次）的 28 倍；Boss 多为 4～14 次（均值约 8），约为卡均值的 3～6 倍。卡牌按曲线批量校准，锚点则逐个手调。这和第 2 章的数值曲线、第 4 章的 Boss 设计是一致的。
4. **给复杂度设上限**。Doormaker 的教训是「有趣的微观决策」不等于好的 Boss：机制要可读、可归因（A6 的改法同理）。可以把「玩家能否说清楚自己为什么输」作为 Boss 和进阶的验收标准。
5. **命名冻结要早于本地化**。二代的改名有近一半集中在 EA 前 3 个月（2025-12～2026-02，115/252），另一波在 2025-05～09（约 80 条），导致短期内大量重名、连锁改名（Fear → Defy、Death's Visage → Fear）。如果能在内容量还小的时候就定一套命名规范（比如遗物按「物件名」、卡按「动作名」），这批工作量可以前移、摊薄。
6. **资源预算**：中日韩字体加上高分辨率事件插图就吃掉了 36% 的包体。如果我们要做小游戏或移动端，应该**按语言分包字体**、**事件插图降采样**；卡图「图集 + 原图」双份存储也值得在打包脚本里剔除原图。
7. **临时资源要有出口**。`debug_audio` 从内测一直用到 EA，而且跟正式 FMOD 并存。临时资源一旦接进正式代码路径就很难清理，建议给 `Tmp*` 类资源建清单，每个版本统计剩余数量。

---

## 附：本章产出文件

| 文件 | 内容 |
|---|---|
| `scripts/ch08_patch_notes.py` | 解析 128 份补丁说明 → 条目、时间线、按月统计、实体频次、改名 |
| `scripts/ch08_assets.py` | 只在内存里读取 `.import` 文本 → 资源分类汇总、实体到路径映射、导入映射、着色器表 |
| `data/csv/ch08_patch_notes_entries.csv` | 10,416 条（英文 10,332 + 简中 84）：日期、阶段、是否合集、类型、子类、动作、正文、实体 |
| `data/csv/ch08_patch_timeline.csv` | 127 行：每份补丁的类型和动作计数、提到的角色、导语首句 |
| `data/csv/ch08_patch_monthly.csv` | 36 个月 × 类型 / 动作 |
| `data/csv/ch08_patch_top_entities.csv` | 1,885 个实体的提及数、平衡段提及、作主语次数、加强 / 削弱 / 重做数、首末日期 |
| `data/csv/ch08_patch_renames.csv` | 252 条改名（旧名 → 新名，新名是否在当前本地化里；pattern=list/line 为核查时按原文补抓的） |
| `data/csv/ch08_asset_catalog.csv` | 45 类资源：数量、体积、占比、路径规律、代码出处 |
| `data/csv/ch08_asset_paths_by_entity.csv` | 4,318 行：卡、遗物、药水、能力、怪物、角色、事件、遭遇、幕、纪元……到资源路径，含是否存在和回退路径；另有被删内容残留和图集孤儿子图 |
| `data/csv/ch08_import_map.csv` | 3,970 行：源路径 → 导入物（importer、格式、字节、md5 规则校验） |
| `data/csv/ch08_shaders.csv` | 127 个着色器（类型、uniform 数、被引用次数） |
