# 杀戮尖塔2 拆解 · 目录地图

对象：Steam 版《Slay the Spire 2》v0.111.1（2026-11-13 构建，抢先体验版）。从游戏设计（策划）视角做的静态拆解，个人研究学习用途。整理：Claude。

> **非官方。** 本仓库与 Mega Crit 无关，也未获其认可。仓库里**没有**游戏代码、反编译源码、美术、音频或原始游戏文件；表格里的卡牌、遗物等名称与描述文字版权归 Mega Crit 所有，仅为评论分析引用。

## 先读哪里

1. **`report.md`** —— 总报告：36 条一页结论、给策划的可借鉴清单、主笔抽查记录、已知局限
2. **`sections/`** —— 八个分章（共 4,835 行），按需要跳读：

| 章 | 文件 | 内容 | 行数 |
|---|---|---|---:|
| 01 | `01_combat_core.md` | 回合时序、能量抽牌、伤害格挡结算管线、148 个 Hook、意图、268 个能力分类、关键词（奇巧/永恒）、费用修饰、随机数分流 | 648 |
| 02 | `02_characters_cards.md` | 五个角色与起始配置、储君辉星/铸造、亡灵契约师奥斯提/灾厄、充能球、卡池对称结构、每能量效率与升级模式、先古卡 | 614 |
| 03 | `03_relics_potions.md` | 299 个遗物 11 类分布、102 个 Ancient 遗物、遗物袋与价格、65 瓶药水、附魔 23、苦难 7 | 510 |
| 04 | `04_monsters_acts.md` | 四幕结构、遭遇名单生成、Boss 发现顺序、121 个怪物 HP 与伤害预算、招式状态机、联机缩放、双 Boss | 635 |
| 05 | `05_map_economy_events.md` | 地图生成与剪枝、房间配比、未知房概率、稀有保底、药水金币、商店定价、休息处、59 个事件、8 位先古之民、水晶球 | 606 |
| 06 | `06_meta_progression.md` | 时间线 57 纪元与解锁链、积分条、进阶 10 级实现、成就/徽章、每日与自定义、建筑师伤害、新手引导、图鉴 | 662 |
| 07 | `07_tech_multiplayer.md` | 代码分层、联机（传输/同步/校验和/重连/回放）、存档与迁移、Mod 支持、AutoSlay、开发者控制台、遥测、本地化与音频动画管线 | 607 |
| 08 | `08_devhistory_assets.md` | 127 份补丁说明梳理的开发史（Unity → Godot）、平衡改动统计、被砍与未上线内容、资源路径清单 | 553 |

3. **`docs/rea_static_analysis.md`** —— 怎么拆的：安装目录结构、加密情况、PCK v3 格式、重跑命令

## 目录

| 路径 | 规模 | 说明 |
|---|---|---|
| `report.md` | 1 份 | 总报告 |
| `sections/` | 8 份 | 分章正文 |
| `data/csv/` | 52 张 | 14 张基础表（`cards` / `relics` / `potions` / `powers` / `monsters` / `monster_moves` / `encounters` / `acts` / `events` / `enchantments` / `afflictions` / `modifiers` / `orbs` / `characters`）+ 38 张分章表（`chNN_*`） |
| `scripts/` | 18 个 | `pck_list.py`（PCK 列目录/解包）、`s1_extract_models.py`（基础表）、`chNN_*.py`（各章派生表）、`apply_verify_fixes.py`（套核查修正） |
| `csharp/sts2_src/` | **未入库** | ILSpy 全量反编译的 `sts2.dll`（3,538 个 .cs），需自行用正版游戏重建，见下文「重跑」 |
| `data/pck_index.csv` | 15,891 行 | PCK 全量目录（路径/扩展名/大小/偏移/MD5），查美术与音频路径用它 |
| `data/pck_text/` | **未入库** | 从 PCK 解出的非美术文件（8,055 个：本地化 JSON、补丁说明、场景、资源、Shader 等），需自行重建 |
| `docs/notes/agent_brief.md` | — | 分章作者共用简报（已按各章反馈勘误） |
| `logs/` | — | ILSpy 日志、第 03 章的遗物通读稿、`verify/` 逐章核查的修正 JSON 与套用记录 |

## 重跑

正文里的源码出处（如 `MegaCrit.Sts2.Core.Models.Cards/Bash.cs:25`）指向反编译目录 `csharp/sts2_src/`，本仓库不带这部分。手上有正版游戏的话，可以按 `docs/rea_static_analysis.md` 的命令在本地重建 `csharp/sts2_src/` 和 `data/pck_text/`（两者已在 `.gitignore` 里），之后在仓库根目录（Git Bash）：

```bash
python -I -X utf8 scripts/s1_extract_models.py      # 基础表
python -I -X utf8 scripts/ch02_card_stats.py        # 各章脚本同理，ch01–ch08
```

反编译和解 PCK 的命令见 `docs/rea_static_analysis.md`。游戏更新后按「反编译 → 列目录 → 解非美术 → 基础表 → 各章脚本」的顺序重跑。

## 读数据的几条规则

- **内容是 C# 类，不是数据表。** 查某张卡/某个怪的真实数值，回 `csharp/sts2_src/MegaCrit.Sts2.Core.Models.<类别>/<类名>.cs`；CSV 是正则抽的，复杂写法（条件分支招式、行为型升级）要回源码确认。
- **怪物进阶写法** `AscensionHelper.GetValueIfAscension(AscensionLevel.X, 进阶值, 普通值)`：第二个参数是进阶值。
- **本地化 key = 类名转 SNAKE_CASE**（`StrikeIronclad` → `STRIKE_IRONCLAD.title`），简中在 `data/pck_text/localization/zhs/`。
- **数量口径**：遗物 299（`VakuuCardSelector` 不是遗物）；Ancient 事件 8 个 + 1 个弃用占位；普通事件 59 个类 = 57 个可进池 + 尾声建筑师 + 弃用占位；本地化 16 种语言。

## 注意

- 本报告只对 v0.111.1 成立；抢先体验期间游戏平均两周一更。
- 本地重建的 `data/pck_text/project.binary` 里有游戏的 Sentry DSN 原文（报告和 CSV 里已打码），重建后也别把这个目录公开。
- 没有运行游戏，少数结论是读代码的推断，各章已标注；已知局限见 `report.md` 末尾。

## 版权与许可

- `scripts/` 下的脚本以 MIT 许可发布（见 `LICENSE`）。
- 报告与分章正文为原创分析；其中引用的游戏名称、文本、数值与短代码片段版权归 Mega Crit，仅用于评论与研究。
- 如权利方认为有不妥，请开 issue，会及时处理。

## 时间线

- 2026-11-23：主笔完成定位、反编译、解 PCK、14 张基础表；8 个分章作者并行写作；主笔逐章抽查、跨章勘误、汇总总报告。
- 2026-11-23：8 名核查员逐章对抗式核查，255 条修正（错误 49 / 夸大 58 / 出处 15 / 小问题 133）全部唯一匹配套用；明细见 `report.md`「逐章对抗式核查」与 `logs/verify/`（`chNN_fixes.json` 原始修正、`apply_log.csv` 套用结果）。重套修正用 `python -I -X utf8 scripts/apply_verify_fixes.py`（不带 `--apply` 为预演）。
