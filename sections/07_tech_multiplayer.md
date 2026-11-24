# 第 07 章 技术架构与联机：分层、同步、存档、Mod、调试与遥测

> 版本 v0.111.1（commit cc1f9462）。出处路径相对 `csharp/sts2_src/`，PCK 解出物相对 `data/pck_text/`。
> 本章新表：`data/csv/ch07_dev_console_commands.csv`（40 条控制台命令）、`data/csv/ch07_multiplayer_messages.csv`（52 种联机消息 + 11 种玩家输入动作）、`data/csv/ch07_save_migrations.csv`（6 类存档 22 条迁移 + 版本汇总）、`data/csv/ch07_metrics_fields.csv`（遥测/反馈/Sentry 上下文 116 个字段）、`data/csv/ch07_project_settings.csv`（project.binary 171 项设置，凭据已打码）。
> 可重跑脚本：`scripts/ch07_extract.py`（前 4 张表）、`scripts/ch07_project_settings.py`（第 5 张）。
> 战斗结算规则、Hook 时点清单、随机数流见第 01 章；多人专属的遗物/药水/房间见第 03、05 章；怪物多人缩放见第 04 章；进度存档字段、成就、排行榜见第 06 章；开发史与 Deprecated 墓碑类见第 08 章。

## 0. 本章结论速览

| # | 结论 | 出处 |
|---|---|---|
| 1 | 代码分五层：**Model**（内容定义，canonical 单例 + 运行时可变副本）→ **ModelDb**（反射建库，类名即 ID）→ **Command**（所有改状态的异步操作）→ **Hook**（148 个派发入口，把事件广播给所有在场模型）→ **Node**（Godot 场景节点，只管表现）。另有一层 **GameAction**，只用来包装"玩家输入"，是联机同步的最小单位 | `MegaCrit.Sts2.Core.Models/AbstractModel.cs:122-178`、`MegaCrit.Sts2.Core.GameActions/GameAction.cs:13-33` |
| 2 | 内容全写成 C# 类、几乎没有数据表：PCK 里 741 个 JSON 有 737 个是本地化，剩下 4 个是字体清单和依赖锁文件。数值集中写在每个类顶部的 `CanonicalVars`，本地化文本按变量名取值，升级逻辑写在 `OnUpgrade()` | `data/pck_index.csv`；`MegaCrit.Sts2.Core.Models.Cards/Bash.cs:18-42` |
| 3 | 策划侧的补偿工具是编辑器插件 **MegaContentCreator**：一个 Godot 面板，输入名字就能生成卡/能力/遗物/怪物的类骨架，也有"deprecate（弃用）"按钮。"约定优于配置"贯穿全程：类名 → `Slugify` → ID → 本地化 key → 美术路径 | `data/pck_text/addons/megacontentcreator/content_creator_dock.tscn`；`MegaCrit.Sts2.Core.Models/ModelDb.cs:515-538`、`MegaCrit.Sts2.Core.Models/CardModel.cs:108,143` |
| 4 | 联机最多 **4 人**。正式版走 Steam（仅好友可见的大厅 + Steam P2P 套接字）；Steam 没初始化或带 `fastmp` 启动参数时改走 ENet 直连，端口 33771。拓扑是星型，所有消息都经过 host | `MegaCrit.Sts2.Core.Nodes.Screens.MainMenu/NMultiplayerHostSubmenu.cs:191-204`、`MegaCrit.Sts2.Core.Multiplayer.Transport.Steam/SteamHost.cs:53` |
| 5 | 同步模型是"**host 给输入定序 + 每台机器各自做确定性模拟**"，不是帧锁步，也不是状态同步：客户端的出牌请求先发给 host，host 排进队列后再广播"已入队"，各端按同一顺序执行同一段代码。单人模式也走这条队列，只是网络服务换成单机实现 | `MegaCrit.Sts2.Core.GameActions.Multiplayer/ActionQueueSynchronizer.cs:140-170,236-249`、`MegaCrit.Sts2.Core.Multiplayer.Game/NetGameType.cs` |
| 6 | 防不同步靠校验和：把整场战斗状态（生物 HP/格挡/能力、每人牌堆/能量/药水/遗物/充能球、随机数状态）序列化后算 XxHash32。战斗进行中每次玩家动作结束（结束回合、准备进入敌方回合两个动作除外）、每个回合阶段、离开事件房（仅确定性事件）和营火都算一次。客户端把校验和发给 host 比对，对不上就踢人（`StateDivergence`），把双方状态快照压缩后报到 Sentry，并写一份回放 | `MegaCrit.Sts2.Core.Multiplayer.Game/ChecksumTracker.cs:87-104,192-264,292-299` |
| 7 | 握手校验三样东西：游戏版本字符串、**全部模型 ID 加可存档属性名的哈希**、影响玩法的 Mod 列表。所以哪怕版本号相同，只要内容表不一致，也会被判为版本不符 | `MegaCrit.Sts2.Core.Multiplayer/PeerVersionInfo.cs:33-56`、`MegaCrit.Sts2.Core.Multiplayer.Connection/HandshakeManager.cs:114-138`、`MegaCrit.Sts2.Core.Multiplayer.Serialization/ModelIdSerializationCache.cs:68-125` |
| 8 | 支持断线重连，但只限原来就在这局里的玩家：host 把完整跑局存档和当前战斗快照发给重连者。局中途来的新玩家会被拒绝（`RunInProgress`） | `MegaCrit.Sts2.Core.Multiplayer.Game.Lobby/RunLobby.cs:102-132`、`MegaCrit.Sts2.Core.Runs/RunManager.cs:1753-1759` |
| 9 | 存档是带 `schema_version` 的缩进 JSON（snake_case），分 6 类，各有一条迁移链。正式版前做过一次"存档清空"：每条链的第一步都是空迁移，再把最低支持版本抬高。被删掉的内容由 Deprecated 墓碑类接住，旧档读入时降级成警告，不会让存档读不出来 | `MegaCrit.Sts2.Core.Saves.Migrations/MigrationManager.cs:43-54`、`MegaCrit.Sts2.Core.Saves/SaveUtil.cs:48-60` |
| 10 | Mod 是官方一等公民：`mods/` 目录加 Steam 创意工坊，清单是 JSON，DLL 加载后要么调用 `[ModInitializer]` 指定的入口，要么自动执行 `Harmony.PatchAll`。只要有 Mod 加载（加载失败也算），存档就切到独立的 `modded/` 目录，完整控制台解锁，每局记录停止上传（纪元、设置两类遥测不检查 Mod，照常上传），Sentry 关闭，报错弹窗里也不再显示"报告 Bug"按钮 | `MegaCrit.Sts2.Core.Modding/ModManager.cs:226-310,1011-1013,1224-1231`、`MegaCrit.Sts2.Core.Saves/UserDataPathProvider.cs:41-58` |
| 11 | AutoSlay 是内部冒烟测试机器人：开局给自己 999 层覆甲和 999 层再生，第 3 回合起每回合 +200 力量，出牌、选奖励、逛商店全靠随机，一局限时 25 分钟。启动它要求 `!IsReleaseGame()`，而正式包里这个函数写死返回 `true`，所以正式版跑不起来 | `MegaCrit.Sts2.Core.AutoSlay/AutoSlayConfig.cs`、`MegaCrit.Sts2.Core.AutoSlay.Handlers.Rooms/CombatRoomHandler.cs:44-62`、`MegaCrit.Sts2.Core.Nodes/NGame.cs:695,762-765` |
| 12 | 遥测只有 4 个上传接口：每局记录、纪元、成就、设置，都在 `sts2-metric-upload.megacrit.com`。玩家标识用的是存档里随机生成的 7 位 ID，不是 Steam ID。4 个接口共同的门槛是正式构建、上传开关打开、没开完整控制台、不在编辑器；每局记录另外排除 Mod 局、放弃的局、第一局、非标准模式、不足 5 个地图点（纪元、设置记录在 Mod 局照传）。本地化共有 **16 种语言**（简报写的 14 种不对），通过 Weblate 每周同步 | `MegaCrit.Sts2.Core.Runs.Metrics/MetricUtilities.cs:29-125`、`MegaCrit.Sts2.Core.Saves/SerializableProgress.cs:181-188`、`MegaCrit.Sts2.Core.Localization/LocManager.cs:101-119` |

---

## 1. 工程总览

### 1.1 技术栈与产物

| 层 | 组件 | 证据 |
|---|---|---|
| 引擎 | Godot 4.5（Mobile 渲染器，Windows 默认 D3D12，另附 vulkan/opengl 启动批处理），2D/3D 物理引擎都设成 Dummy（不用物理） | `data/csv/ch07_project_settings.csv`（`application/config/features`、`rendering/rendering_device/driver.windows`、`physics/*/physics_engine`）；游戏目录 `launch_*.bat` |
| 语言 | C#（.NET 9，`netcoreapp9.0`，LangVersion 11），主程序集 `sts2` | `sts2.csproj:5,9`；`dotnet/project/assembly_name` |
| 原生插件（GDExtension） | FMOD（`libGodotFmod`）、Spine（`libspine_godot`）、Sentry（`libsentry` + crashpad） | `addons/*/…gdextension`；游戏目录 dll |
| 托管库 | 0Harmony、SmartFormat、Sentry、Steamworks.NET、System.IO.Hashing（XxHash32）、Vortice.DXGI | `sts2.csproj:15-40` |
| 自动加载 | `SentryBootstrap`（C#）、`FmodManager`（GDScript） | `autoload/*`（project settings 表） |
| 用户目录 | `application/config/custom_user_dir_name = SlayTheSpire2`，即 `%AppData%/SlayTheSpire2/` | 同上 |

### 1.2 代码规模（按命名空间前缀统计 .cs）

| 层 | 文件 | 行数 | 说明 |
|---|---|---|---|
| Models（内容 + 基类） | 1,725 | 106k | `AbstractModelSubtypes` 源生成清单登记了 1,660 个模型子类（`MegaCrit.Sts2.Core.Models/AbstractModelSubtypes.cs`） |
| Nodes（Godot 节点/UI） | 711 | 307k | 行数虚高：大量是 Godot 源生成器产出的 `MethodName/PropertyName` 缓存和 `InvokeGodotClassMethod` 样板（推断）；全程序集 709 个类带 `[ScriptPath]` 与场景绑定（其中 704 个指向 `res://src/...cs`，Nodes 命名空间内 664 个） |
| Saves | 120 | 27k | 其中 `MegaCritSerializerContext.cs` 是 System.Text.Json 源生成的序列化器 |
| Multiplayer | 155 | 15k | 传输、消息、同步器、大厅、回放 |
| Commands / Hooks / GameActions | 22 / 3 / 39 | 7k / 2.8k / 4.3k | |
| DevConsole / AutoSlay / Modding / Localization | 49 / 31 / 16 / 59 | 4.2k / 3.2k / 2.3k / 4.0k | |

PCK 里的 3,441 个 `.cs` 都只有 1 字节，是 Godot 用来让 `res://` 路径存在的占位文件，真正的代码在 `sts2.dll` 里。

### 1.3 启动流水线（顺序有依赖，见源码注释"Beware of changing the order"）

| 阶段 | 做什么 | 出处 |
|---|---|---|
| VeryEarly | 读 settings.save → 初始化 ModManager（扫描并加载 Mod）→ 标记是否 modded（决定存档目录）→ modded 则关闭 Sentry | `MegaCrit.Sts2.Core.Helpers/OneTimeInitialization.cs:43-62` |
| NGame 启动 | 创建开发者控制台节点 → 迁移旧的用户目录结构（按账号/按档位）→ 云存档同步 | `MegaCrit.Sts2.Core.Nodes/NGame.cs:650-660` |
| Essential | 加载 UI 图集 → `LocManager.Initialize` → `ModelDb.Init`（反射实例化所有模型）→ `ModelIdSerializationCache.Init`（给 ID 编号并算哈希）→ `ModelDb.InitIds` → 消息类型表、动作类型表 | `OneTimeInitialization.cs:68-86` |
| Deferred（主菜单已显示后） | 加载全部图集 → `ModelDb.Preload`（预算卡池、图标路径）→ 预热所有 `Serialize/Deserialize` 方法的 JIT | `OneTimeInitialization.cs:92-115` |

**设计观察**：Mod 必须在 ModelDb 之前加载，Mod 里的新类才能被同一套反射扫描收进库。这也是 Mod 只能"启动时加载、改了要重启"的根本原因（`ModLoadState.AddedAtRuntime`，`MegaCrit.Sts2.Core.Modding/ModManager.cs:822-826`）。

---

## 2. 代码分层

### 2.1 各层分工

| 层 | 代表类型 | 职责 | 能不能碰 UI |
|---|---|---|---|
| Model | `CardModel`、`RelicModel`、`PowerModel`、`MonsterModel`、`EventModel`… 都继承 `AbstractModel` | 内容的数值、文本变量、规则（重写钩子虚方法） | 不直接碰；通过 Command 间接触发表现 |
| ModelDb | `static class ModelDb` | 启动时把每个模型子类实例化一份 canonical 单例，按 `ModelId` 存入字典；提供卡池、遭遇池等聚合视图 | 否 |
| Command | `CreatureCmd`、`PowerCmd`、`CardPileCmd`、`CardCmd`、`DamageCmd`（返回 `AttackCommand` 构建器）、`VfxCmd`、`SfxCmd`… 共 20 个静态类 | 所有改状态的操作都是 `async Task`：先跑 Hook 修正，再改数据，再记战斗历史，最后播表现 | 可以：在命令内部调 Node 播 VFX，测试/无交互模式下跳过 |
| Hook | `static class Hook`（148 个派发方法）+ `AbstractModel` 上 182 个钩子虚方法 | 按固定顺序遍历监听者，依次 `await` 每个模型的回调（顺序和守卫见第 01 章） | 否 |
| GameAction | `PlayCardAction`、`UsePotionAction`、`EndPlayerTurnAction`、`MoveToMapCoordAction`… | 只包装"玩家输入"，是联机定序和同步的单位 | 否 |
| Node | `NCard`、`NCreature`、`NCombatRoom`、`NGame`…（Godot `Control/Node` 子类） | 场景树、动画、输入；订阅模型上的 C# 事件来刷新显示 | 是 |

源码对 GameAction 的定位写得很直白：一代的 GameAction 是"造成伤害、获得格挡"这类小逻辑单元，二代把这些交给 Command，**GameAction 只包装玩家输入**（出牌、喝药、点结束回合）；怪物行动不需要等玩家输入，所以不用 GameAction（`MegaCrit.Sts2.Core.GameActions/GameAction.cs:13-33`）。这段注释还提到"原 Unity 版 STS2"，和第 08 章"前 8 个月在 Unity 上开发"的结论对得上。

### 2.2 Model：canonical 不可变 + `ToMutable()` 运行时副本

| 状态 | 是什么 | 谁持有 | 约束 |
|---|---|---|---|
| canonical（规范实例） | `ModelDb.Init` 时每个类型 `Activator.CreateInstance` 出来的唯一一份 | 卡池、遗物池、图鉴、商店候选 | `AssertCanonical()`：卡池只能放 canonical（`AbstractModel.cs:136-142`） |
| mutable（可变副本） | `ToMutable()` = `MemberwiseClone` → 标记 `IsMutable` → `DeepCloneFields()` → `AfterCloned()`（清掉事件订阅） | 牌组、手牌、战斗中的怪、身上的能力 | `AssertMutable()`：canonical 卡不能放进牌堆（`AbstractModel.cs:122-128`） |

要点：

- **构造函数自带防重**：同一个 `ModelId` 第二次构造会直接抛 `DuplicateModelException`，报错提示"你是不是 new 了一个模型？请改用 ModelDb"，并点名"可能是 Mod 内容重名"（`AbstractModel.cs:76-87`）。这样就从机制上杜绝了"有人随手 new 了一张卡"。
- **深拷贝要逐字段处理**：基类注释特别提醒，`MemberwiseClone` 会把事件委托也一起浅拷贝过去，子类必须在 `AfterCloned` 里把事件置空，否则副本会把事件发给原件的订阅者（`AbstractModel.cs:185-195`）。
- **出错时该在哪修**：`AssertMutable` 的注释明确要求别在报错的地方就地转成可变，要回到这个模型最初被创建的地方去转（`AbstractModel.cs:109-121`）。
- **钩子分"战斗内/战斗外"**：每个模型都要实现 `ShouldReceiveCombatHooks`。牌组里的卡不收 `AfterCardPlayed`，但会收 `AfterRoomEntered`、`AfterDamageReceived`，因为事件房里也会受伤（`AbstractModel.cs:59-68`）。
- **需要存档的运行时状态**用 `[SavedProperty]` 标注，比如遗物的计数器，全游戏共 59 处（遗物 47、卡牌 9、基类 2、修饰符 1）（`MegaCrit.Sts2.Core.Saves.Runs/SavedPropertyAttribute.cs`）。这些属性名同时参与联机 ID 哈希（§3.6）。

**设计观察**：这相当于把"配置表行"和"运行时实例"在同一个类里做了区分。canonical 对象就是只读配置，mutable 副本就是实例。优点是不用再维护"表 → 实例"的转换代码，代价是要靠断言，而不是类型系统，来防止两种对象混用。

### 2.3 ModelDb：约定优于配置

| 环节 | 规则 | 出处 |
|---|---|---|
| 发现 | `AbstractModelSubtypes.All`（源生成，1,660 个类型）加上 `ReflectionHelper.GetSubtypesInMods<AbstractModel>()` | `ModelDb.cs:68-88` |
| ID | `ModelId(Category, Entry)`：Category 取"直接继承 AbstractModel 的那一层基类名"的 SNAKE_CASE，去掉 `_MODEL` 后缀；Entry 取类名的 SNAKE_CASE。例：`Bash` → `CARD.BASH` | `ModelDb.cs:515-538`、`MegaCrit.Sts2.Core.Models/ModelId.cs` |
| 本地化 | 卡牌的标题和描述是 `cards.json` 里的 `BASH.title`、`BASH.description` | `CardModel.cs:108,127` |
| 美术 | `atlases/card_atlas.sprites/<卡池>/<entry>.tres`，找不到就依次退回单张 PNG、beta 图、缺图占位（细节见第 08 章） | `CardModel.cs:143-151` |
| 聚合 | 卡池、事件、遭遇、药水池、遗物池、幕、修饰符都是手写数组，比如 `AllSharedEvents` 18 个，`Acts` 4 个（DeprecatedAct 不在里面） | `ModelDb.cs:126-416` |
| 注入 | `Inject/Remove` 只给测试和 Mod 用 | `ModelDb.cs:434-456` |

所以新增一张卡的最小改动是：写一个类，加进角色卡池数组，在 `cards.json` 里补 key，放一张图。没有 ID 表要维护，也没有注册代码要写。

### 2.4 Command：异步命令

```csharp
// MegaCrit.Sts2.Core.Models.Cards/Bash.cs:29-36（痛击 Bash）
await DamageCmd.Attack(DynamicVars.Damage.BaseValue).FromCard(this, cardPlay).Targeting(cardPlay.Target)
    .WithHitFx("vfx/vfx_attack_blunt", null, "blunt_attack.mp3").Execute(choiceContext);
await PowerCmd.Apply<VulnerablePower>(choiceContext, cardPlay.Target, DynamicVars.Vulnerable.BaseValue, Owner.Creature, this);
```

- `DamageCmd.Attack` 只是创建一个 `AttackCommand` 构建器：链式设置来源、目标、多段、特效，最后 `Execute`（`MegaCrit.Sts2.Core.Commands/DamageCmd.cs`、`Commands.Builders/AttackCommand.cs`）。
- 一条命令内部的标准顺序（以 `PowerCmd.Apply` 为例）：`Hook.Before…` → `Hook.Modify…Given/Received`（纯计算）→ 改数值 → `CombatManager.History` 记账 → `Hook.AfterModifying…`（真正生效的修正者结算）→ `Hook.After…Changed` → 找到 `NCreature` 节点播表现（`MegaCrit.Sts2.Core.Commands/PowerCmd.cs:124-160,258`）。
- 等待统一用 `Cmd.Wait`，它走 Godot 计时器，所以会受时间缩放（顿帧）影响；快速模式为 Instant、测试模式、AutoSlay 时直接跳过等待（`MegaCrit.Sts2.Core.Commands/Cmd.cs:16-45`、`MegaCrit.Sts2.Core.Helpers/NonInteractiveMode.cs`）。

**设计观察**：所有改状态的操作都是 `async`，表现节奏（等待、动画）就能直接写进逻辑流程里，不需要再拆一套"逻辑帧 + 动画队列"。同一套代码在无头测试里把等待全部跳过就行。这是二代能做 AutoSlay 和回放、能在多台机器上跑出一致结果的前提。

### 2.5 Hook 与 GameAction 的衔接（只讲架构，时点清单见第 01 章）

- `AbstractModel` 上有 185 个 `public virtual`，其中 182 个是钩子：After 80、Before 21、Modify 39、Should 28、Try 14。另外 3 个是 `IsMock`、`PreviewOutsideOfCombat`、`CompareTo`。第 01 章写的 185 包含了这 3 个。
- `Hook.cs` 有 148 个 `public static` 派发方法，每个方法遍历监听者（战斗钩子多数经私有包装 `IterateCombatHookListeners`，战斗已在结束时整次派发为空）；其中 81 个返回 `Task` 的（After/Before 等）逐个 `await` 回调，67 个 Modify/Should 类是同步计算。Mod 可以通过 `ModHelper.SubscribeForCombatStateHooks` 把自己的模型挂进遍历序列（`MegaCrit.Sts2.Core.Modding/ModHelper.cs:465-525`）。
- 钩子里如果要"产生一个需要排队的动作"（比如回合末某能力让玩家选牌），会生成 `GenericHookGameAction`，用一个自增的 HookId 标识。因为每台机器执行钩子的次数和顺序都一样，各端生成的 HookId 也天然一致（`ActionQueueSynchronizer.cs:179-206`）。

### 2.6 Node：表现层

- Node 通过 `[ScriptPath]` 绑定到 `.tscn` 场景，并订阅模型事件来刷新显示。例如 `NCard.Model` 赋值时会订阅 `AfflictionChanged/EnchantmentChanged`（`MegaCrit.Sts2.Core.Nodes.Cards/NCard.cs:642-754`）。卡牌节点走对象池，预建 30 个（`NCard.cs:769`）。
- 逻辑不依赖 Node：命令里取节点都写成 `NCombatRoom.Instance?.…`，节点不存在就跳过，所以测试和 AutoSlay 可以无头运行。

### 2.7 一张牌从点击到结算（跨层时序）

```
玩家拖牌 (NCard/NHand, Node)
  └─ new PlayCardAction(...)  ── ActionQueueSynchronizer.RequestEnqueue
        ├─ 单机/host：直接入本人队列；host 另发 ActionEnqueuedMessage 给客户端
        └─ 客户端：发 RequestEnqueueActionMessage 给 host，等 host 回 ActionEnqueuedMessage 才入队
  └─ ActionExecutor 取所有玩家队头中 ID 最小者执行
        └─ CardModel.OnPlay()  (Model)
              ├─ DamageCmd / PowerCmd ... (Command)
              │     └─ Hook.ModifyDamage... / Hook.AfterDamageGiven ... (Hook → 所有在场 Model)
              │     └─ NCreature 播受击、飘字 (Node)
              └─ 需要玩家选牌？→ PlayerChoiceSynchronizer：所有端生成同一 choiceId，只有出牌者弹 UI，选完广播结果
  └─ 动作结束 → ChecksumTracker.GenerateChecksum("finished action execution …")
```

（`MegaCrit.Sts2.Core.GameActions.Multiplayer/ActionQueueSet.cs:172-178`、`PlayerChoiceSynchronizer.cs:13-24`、`MegaCrit.Sts2.Core.Runs/RunManager.cs:576-582`）

### 2.8 内容为什么写成 C# 类而不是数据表

| 原因 | 证据 |
|---|---|
| **行为是主体，数值是参数**：一张卡的核心是 `OnPlay` 里的命令组合，遗物/能力的核心是重写哪几个钩子（182 个可选）。用表格写"触发时点 × 条件 × 效果"会退化成一门脚本语言 | `Bash.cs`、`MegaCrit.Sts2.Core.Models.Relics/BurningBlood.cs:16-23`（燃烧之血只重写 `AfterCombatVictory`） |
| **数值和文本仍然是"半数据化"的**：`CanonicalVars` 在类顶部声明 `DamageVar(8)`、`PowerVar<VulnerablePower>(2)`；本地化写成 `造成{Damage:diff()}点伤害`，按变量名取值。改数值只改一处，卡面文本自动跟着变，升级后的数值用绿色高亮 | `Bash.cs:18-22`、`localization/zhs/cards.json`（`BASH.description`）、`MegaCrit.Sts2.Core.Localization.Formatters/HighlightDifferencesFormatter.cs` |
| **确定性与联机**：所有内容都在同一个程序集里，ID 集合和可存档属性名一起算哈希，两端只要哈希相同，就保证跑的是同一份规则 | `ModelIdSerializationCache.cs:68-125` |
| **Mod 和官方内容走同一条路**：Mod 写 C# 类，被同一套反射收进 ModelDb，再用 `ModHelper.AddModelToPool` 加进池子 | `ModHelper.cs:408-458` |
| **测试**：48 个 Mock 模型（卡 8、能力 18、遭遇 8、怪物 6 等），配合 `TestMode`，可以单独测一个机制 | `MegaCrit.Sts2.Core.Models.*.Mocks/` |
| 与一代对比（凭公开知识） | 一代（Java/libGDX）的卡牌同样是"一类一卡"（如 `cards.red.Bash`），二代延续了这条路，又补上了 canonical/mutable 分离、DynamicVar 绑定文本、源生成登记 |

**对策划工作流意味着什么**

1. **策划要能读写 C#，至少要读得懂**。好在单卡代码很短，`Bash.cs` 只有 43 行，数值都集中在 `CanonicalVars` 和 `OnUpgrade`；怪物进阶值统一写成 `AscensionHelper.GetValueIfAscension(级别, 进阶值, 普通值)`（见第 04 章）。调数值本质上是改常量再编译。
2. **脚手架工具替代了"填表"**：MegaContentCreator 面板有 cards/powers/relics/monsters 四个页签，填名字就能生成骨架。卡牌页签可以勾选"needs power"连带生成配套能力，怪物页签可以输入逗号分隔的招式名，每类都有 deprecate 按钮（`addons/megacontentcreator/content_creator_dock.tscn`）。生成逻辑在编译过的 `mega_content_creator.gdc` 里，本机缺 zstd 解压，没有解开（见文末"没解决"）。
3. **文本由 Weblate 平台管**，和代码解耦（§9）。改描述不用碰代码，但变量名必须和 `CanonicalVars` 对得上，CI 会校验。
4. **删内容不能直接删**：要走"deprecate → 墓碑类 → 迁移链改名"这条路（§4.4，详见第 08 章），否则老存档会读不出来。

**可借鉴**：对卡牌/遗物这种"行为差异远大于数值差异"的内容，"一类一内容 + 数值声明块 + 文本按变量名插值 + 脚手架面板"比纯数据表更稳。数据表适合怪物血量、掉落权重这种结构整齐的数据。二代的做法是把这类数值也写进代码常量，再靠第 01、04 章提到的统一辅助函数保持写法一致。

---

## 3. 联机

### 3.1 规格速览

| 项 | 值 | 出处 |
|---|---|---|
| 最大人数 | 4（标准、自定义、每日都是；加入每日房间的一方构造大厅时人数参数传 -1，以 host 为准） | `NMultiplayerHostSubmenu.cs:199-226`；`MegaCrit.Sts2.Core.Nodes.Screens.DailyRun/NDailyRunScreen.cs:326,389` |
| 传输（正式） | Steam：`SteamMatchmaking.CreateLobby(FriendsOnly, 4)` + `SteamNetworkingSockets.CreateListenSocketP2P`，客户端 `ConnectP2P` 连房主。房间关闭（开局）时大厅改为 Private | `SteamHost.cs:50-100`、`Transport.Steam/SteamClient.cs:92-95` |
| 传输（开发/局域网） | Godot `ENetConnection`，绑定 `0.0.0.0:33771`。条件是 Steam 没初始化，或者带了 `fastmp` 参数 | `Transport.ENet/ENetHost.cs:53-56`；`NMultiplayerHostSubmenu.cs:191` |
| 超时 | 20,000 ms：Steam host 监听套接字的初始连接超时和已连接超时（`SteamHost` 里写死的字面量；`NetConst.timeoutMsec` 也是 20000，但全程序集没有任何引用）。另外 ENet 客户端连接超时 10 秒，大厅等新玩家首条消息 10 秒 | `SteamHost.cs:62-80`、`Transport.ENet/ENetClient.cs:54-60`、`Game.Lobby/StartRunLobby.cs:102` |
| 拓扑 | 星型：客户端只连 host；消息标了 `ShouldBroadcast` 的，由 host 转发给所有客户端 | `MegaCrit.Sts2.Core.Multiplayer.Serialization/INetMessage.cs:10-13` |
| 报文头 | 1 字节消息类型号 + 8 字节发送者 ID，之后是按位压缩的正文。模型 ID 按"类别号 + 条目号"写，位宽取 ⌈log2(总数)⌉ | `MegaCrit.Sts2.Core.Multiplayer/NetMessageBus.cs:43-50`、`ModelIdSerializationCache.cs:119-122` |
| 可靠性 | 每条消息自己声明 `Reliable/Unreliable`：玩法消息走可靠，鼠标、反应、地图涂鸦走不可靠 | `ch07_multiplayer_messages.csv` 的 `transfer_mode` 列 |
| 连接质量 | 心跳回显估算 RTT 和丢包，用来显示"连接不佳"提示 | `MegaCrit.Sts2.Core.Multiplayer.Quality/NetQualityTracker.cs:10-21` |
| 人数对玩法的影响 | 怪物血量按 人数 × 幕系数 放大，怪物的攻击打所有玩家（见第 04 章）；每张地图每幕少 1 行，商店每人一份货架（见第 05 章） | `MegaCrit.Sts2.Core.Models.Singleton/MultiplayerScalingModel.cs` |

### 3.2 同步模型：host 定序的输入同步

网络服务有 4 种实现：`Singleplayer / Host / Client / Replay`（`MegaCrit.Sts2.Core.Multiplayer.Game/NetGameType.cs`）。上层逻辑只调 `RequestEnqueue`，具体走哪条路由当前的服务类型决定：

| 角色 | `RequestEnqueue(action)` 的行为 |
|---|---|
| Singleplayer | 直接入队执行 |
| Host | 直接入队，同时广播 `ActionEnqueuedMessage(playerId, location, action)` |
| Client | **不入队**，发 `RequestEnqueueActionMessage` 给 host；等 host 回 `ActionEnqueuedMessage` 才入队 |
| Replay | `RequestEnqueue` 不处理（switch 里没有 Replay 分支，本地输入直接丢弃）；动作由调试场景 `NMultiplayerTest` 从回放文件读出，直接 `ActionQueueSet.EnqueueWithoutSynchronizing` 按原顺序喂进队列（`MegaCrit.Sts2.Core.Nodes.Debug.Multiplayer/NMultiplayerTest.cs:562-592`） |

（`ActionQueueSynchronizer.cs:140-170,236-305`）

客户端的出牌要"绕 host 一圈"才执行，代价是一次往返延迟，换来的是所有端看到同一个全局顺序。为了掩盖这段延迟，PeerInput 会把对方的鼠标、悬停、瞄准实时同步过来（§3.8），让玩家觉得"队友正在操作"。

**确定性的三个支点**

1. 所有随机数都从种子派生，按玩家槽位号而不是网络 ID 分流，所以每日挑战在不同机器上结果一致；表现用的混沌流不参与玩法（见第 01 章）。
2. 每场战斗开始前，每个人广播 `SyncPlayerDataMessage`（牌组、HP、药水栏），host 再广播 `SyncRngMessage`（随机数状态和共享遗物袋）。全员对齐后才开打（`MegaCrit.Sts2.Core.Multiplayer/CombatStateSynchronizer.cs`；消息注释里还留着一条 TODO，开发者自己也不确定"回滚随机数状态"是不是对的）。
3. 排序用 `DeterministicModelComparer`，按类别号和条目号的整数比较，不用字符串或哈希码（`AbstractModel.cs:37-49`）。

### 3.3 动作队列

- **每个玩家一条队列**。如果某人第 2 张牌在等他选牌，他自己的第 3 张牌会排在后面等，但其他人的牌照常执行（`ActionQueueSet.cs:13-19`）。
- 执行时跳过"正在等选择"的队列，在其余队列的队头里取 ID 最小的那个，也就是 host 最早排进去的（`ActionQueueSet.cs:172-178`）。
- 动作类型决定什么时候能执行、什么时候被取消（`MegaCrit.Sts2.Core.Entities.Multiplayer/GameActionType.cs`）：

| 类型 | 规则 | 例 |
|---|---|---|
| Combat | 战斗结束时还在队列里就取消；不在战斗中时入队就取消 | |
| CombatPlayPhaseOnly | 同上；如果在敌方回合或抽牌阶段请求，会先暂存，等本人出牌阶段开始再统一发出 | 出牌、喝药 |
| NonCombat | 战斗结束不取消；战斗中排到队头也要等到战斗结束才执行 | 地图移动 |
| Any | 随时可以执行 | 地图投票（`VoteForMapCoordAction`）；控制台命令只在战斗外是 Any，战斗内是 CombatPlayPhaseOnly |

- 战斗阶段状态机（`ActionSynchronizerCombatState`）：`NotInCombat → PreCombatSetup → PlayPhase ⇄ EndTurnPhaseOne → NotPlayPhase`。进入 EndTurnPhaseOne 后，取消所有手动操作，只放行钩子生成的动作（比如回合末的"选牌保留"），防止玩家操作和回合末结算交错执行（`MegaCrit.Sts2.Core.Entities.Multiplayer/ActionSynchronizerCombatState.cs`、`ActionQueueSynchronizer.cs:80-138`）。
- 多人可以**撤销结束回合**（`UndoEndPlayerTurnAction`）；已经结束回合的人可以发 `EndTurnPingMessage` 催队友，源码注释原话是"to annoy other players"。

### 3.4 哪些操作要广播（`data/csv/ch07_multiplayer_messages.csv`）

| 类别 | 内容 | 数量 |
|---|---|---|
| 玩家输入动作（INetAction） | 出牌、喝药、丢药、结束回合/撤销、准备进入敌方回合、地图移动/投票、投票进下一幕、选遗物、控制台命令 | 11 种 |
| 队列控制 | 请求入队/已入队、钩子动作请求入队/已入队、选择后恢复（请求/确认） | 6 |
| 战中选择 | `PlayerChoiceMessage`：所有端生成同一个 choiceId，只有当事人弹出界面，选完后广播结果 | 1 |
| 开战对齐 | `SyncPlayerDataMessage`、`SyncRngMessage` | 2 |
| 房间外同步 | 事件选项（共享事件投票 → host 定结果）、营火选项/跳过、奖励选取/跳过、宝箱开启、商店删卡、丢金币、水晶球奖励 | 12 |
| 校验 | `ChecksumDataMessage`（客户端→host）、`StateDivergenceMessage` | 2 |
| 纯表现（Flavor） | 反应轮（8 种表情：感叹号、骷髅、踩、悲伤史莱姆、问号、爱心、赞、开心邪教徒）、地图涂鸦/清除/画笔模式、地图 ping、结束回合 ping、营火选项悬停 | 7 |
| 大厅 | 加入/读档加入/重连的请求和应答、选角、准备、进阶/种子/修饰符变更、开局、玩家进出/重连 | 18 |
| 会话与其他 | `RunAbandonedMessage`、心跳请求/应答、`PeerInputMessage` | 4 |

合计 52 种 `INetMessage`（与源生成清单 `INetMessageSubtypes` 一致），其中 9 种走不可靠通道。

- 19 条玩法消息带 `RunLocation`，经 `RunLocationTargetedMessageBuffer` 缓冲：如果消息比本机先到下一个房间，就先存着，等本机也进了那个房间再按到达顺序处理（`MegaCrit.Sts2.Core.Multiplayer.Game/RunLocationTargetedMessageBuffer.cs:10-16`）。
- 共享事件收齐全员投票后，host 从所有人的票里**随机抽一张**作为结果（`_multiplayerOptionSelectionRng.NextItem(_playerVotes)`），等于按票数加权抽签，不是“多数决 + 平票才随机”（字段注释虽写“票数相同时用”，代码并没有先比票数）。这个随机数用跑局种子初始化，但只在 host 上推进，注释要求别指望各端一致；结果广播给其他人（`EventSynchronizer.cs:53-57,170-190`）。这是少数"不靠确定性，靠 host 说了算"的地方。宝箱遗物冲突用猜拳决定，见第 05 章。

### 3.5 校验和 Checksums

| 项 | 内容 | 出处 |
|---|---|---|
| 内容 | `NetFullCombatState`：每个生物的怪物 ID 或玩家 ID、HP/最大 HP、格挡、能力列表；每个玩家的角色、回合数、回合阶段、能量、星辰、药水栏上限、金币、各牌堆（卡牌及其苦难、费用、关键词）、药水、遗物、充能球、玩家随机数、遗物袋；跑局随机数；下一个 choiceId/rewardId；最后执行的动作 ID 和钩子 ID | `MegaCrit.Sts2.Core.Entities.Multiplayer/NetFullCombatState.cs:21-200` |
| 算法 | 用 PacketWriter 序列化，补齐末字节，再算 `XxHash32` | `ChecksumTracker.cs:292-299` |
| 触发点 | 战斗进行中每个玩家动作执行完（结束回合和准备进入敌方回合这两个动作除外；战斗外的地图移动、选遗物等不算）；玩家回合开始后、敌方回合开始后、敌方回合结束后、玩家回合结束第一段和第二段；离开事件房（仅 `IsDeterministic` 的事件）；离开营火 | `RunManager.cs:576-582`；`MegaCrit.Sts2.Core.Combat/CombatManager.cs:799,846,1438,1594,1781`；`MegaCrit.Sts2.Core.Rooms/EventRoom.cs:96`、`RestSiteRoom.cs:46` |
| 比对 | 各端按调用次序给校验和编自增 ID。客户端发给 host，host 按 ID 找本地的那一份比对；本地还没算到的先排队。本地只保留最近 20 份 | `ChecksumTracker.cs:41,87-130,159-190` |
| 不一致时 | host 把自己那份状态发给客户端，客户端回发自己的，双方都把对方状态打进日志并上报 Sentry（按动作类型归类，附 local/remote/previous 三份 gz 压缩状态和大厅 ID），host 以 `StateDivergence` 踢掉客户端，客户端写回放后返回主菜单 | `ChecksumTracker.cs:137-264`、`RunManager.cs:1545-1564` |

**设计观察**：这套设计放弃了"不同步后自动纠正"，改为"及早发现，把现场打包带回去"。卡牌游戏的状态小，回合也离散，在每个动作后算一次哈希几乎没有成本，而且能精确定位到"哪一张牌之后开始不同步"。校验和不同步的 Sentry 分组键就是动作类型名（`SetFingerprint("StateDivergence", fingerprintContext)`），线上统计能直接看出"哪张牌、哪种动作最容易不同步"。

### 3.6 握手：版本、内容哈希、Mod

`PeerVersionInfo` 的注释说明这是唯一一个"格式只能追加、不能改"的结构，保证跨版本也能读出版本号来判断是否不匹配（`PeerVersionInfo.cs:13-17`）。

| 检查顺序 | 不通过的结果 |
|---|---|
| 1 版本字符串不同 | `VersionMismatch` |
| 2 双方"影响玩法"的 Mod 列表互有缺失 | `ModMismatch` |
| 3 `idDatabaseHash` 不同，即全部模型 ID、Epoch ID 和 `[SavedProperty]` 属性名的 XxHash32（`affects_gameplay=false` 的 Mod 内容不计入） | `VersionMismatch` |
| 4 不影响玩法的 Mod 不一致 | 只记警告，照常放行，并提示"由 Mod 作者自己保证兼容" |

（`HandshakeManager.cs:114-138`、`ModelIdSerializationCache.cs:68-125`）Steam 分支名只用于诊断，不参与比较，因为同一版本可能同时出现在多个分支上（`PeerVersionInfo.cs:24-29`）。断线原因 `NetError` 按百位分段：0 段是正常退出，100 段是加入失败（满员、局已开始、不在存档里、版本、Mod、不同步、超时），200 段是网络问题，枚举值要求跨版本保持稳定（`MegaCrit.Sts2.Core.Entities.Multiplayer/NetError.cs`）。

### 3.7 大厅 Lobby

| 类 | 阶段 | 要点 |
|---|---|---|
| `StartRunLobby` | 新开一局前 | 选角、准备、进阶、种子、修饰符；可选的**最高进阶取全员"多人进阶解锁"的最小值**（`StartRunLobby.cs:294-303`）；有一个"临时"接口让 host 手动指定第 1 幕用哪个（`StartRunLobby.cs:105-107`） |
| `LoadRunLobby` | 读多人存档 | 只放行存档里的玩家（其他人收到 `NotInSaveGame`）；多人存档单独存为 `current_run_mp.save` |
| `RunLobby` | 局内 | 接管断线和重连；`Players` 只记录当前在线的人，而 `RunState.Players` 记录所有曾经在场的人（`RunLobby.cs:12-35`） |

其余细节：每日挑战用 MegaCrit 自己的时间服务器（`https://time.megacrit.com`，`MegaCrit.Sts2.Core.Daily/TimeServer.cs:14`）；Steam 邀请通过 `+connect_lobby` 启动参数直接进房（`CommandLineHelper.TryGetValue("+connect_lobby")`）。

### 3.8 断线重连与 PeerInput

- **重连**：客户端发 `ClientRejoinRequestMessage`，host 先确认这人在 `RunState` 里，再回 `ClientRejoinResponseMessage`（完整的 `SerializableRun` + `NetFullCombatState`），然后通知其他人 `PlayerRejoined`（`RunLobby.cs:102-132`、`RunManager.cs:1753-1759`）。重连走"快照"，不是"回放动作补齐"。
- 断线的玩家在战斗里怎么处理（他的回合是否自动结束、能力是否继续结算），这次没找到明确代码，列为未解决。
- **host 是单点**：host 放弃对局会广播 `RunAbandonedMessage`，所有人一起退出（`RunLobby.cs:178-196`）。没有找到 host 迁移的代码。
- **PeerInput**：每 50 ms 最多同步一次鼠标位置（按宽高比归一化，再量化成 16 位）、按下状态、是否在瞄准、所在界面、悬停的模型、手柄焦点。走不可靠通道，不进缓冲（`PeerInputSynchronizer.cs:51`、`Messages.Game.Sync/PeerInputMessage.cs`、`Game.PeerInput/NetCursorHelper.cs`）。项目设置里专门给这些表现配了调试热键：隐藏多人光标、瞄准线、手牌、意图、血条（`input/debug_hide_mp_*`）。

### 3.9 回放 Replay

| 项 | 内容 | 出处 |
|---|---|---|
| 格式 | `.mcr`，二进制（PacketWriter）：版本号、git commit、模型 ID 哈希、choiceId/rewardId 序列、下一个动作/校验和/钩子 ID、**进房时的完整 `SerializableRun`**、事件流（GameAction / HookAction / ResumeAction / PlayerChoice 四种）、每个校验和点的完整状态。写盘前做匿名化 | `MegaCrit.Sts2.Core.Multiplayer.Replay/CombatReplay.cs:8-30`、`CombatReplayEventType.cs`、`CombatReplayWriter.cs:163-180` |
| 范围 | 每次进房记录初始状态（`RecordInitialState`），战斗结束、清理跑局、客户端不同步时写到 `<档位>/replays/latest.mcr`，只保留最新一份 | `RunManager.cs:913,1154,1566-1570`、`CombatManager.cs:1323-1326` |
| 播放 | `NetReplayGameService` 把动作重新喂进队列，每个校验和点和录制时的状态比对，不一致就报"Replay state divergence" | `RunManager.cs:415-430`、`ChecksumTracker.cs:266-290` |
| 用途 | **调试取证，不是给玩家看的录像**：`getlogs` 命令和游戏内反馈都会把 `latest.mcr` 一起打包；播放入口在调试场景 `NMultiplayerTest`，文件选择框过滤 `*.mcr` | `MegaCrit.Sts2.Core.DevConsole.ConsoleCommands/GetLogsConsoleCmd.cs:411`、`MegaCrit.Sts2.Core.Nodes.Debug.Multiplayer/NMultiplayerTest.cs:491` |

**设计观察 / 可借鉴（联机）**

1. **单机就是只有一个人的多人局**：同一条队列、同一套校验点，单机测试就等于在测联机代码，多人特有的 bug 会少很多。
2. **"输入定序 + 确定性 + 校验和 + 回放"是一套组合**：有确定性才能做回放，有回放才能复现不同步，校验和负责把不同步精确定位到具体动作。回合制卡牌游戏做联机，这是最省带宽、也最好调试的方案。
3. **内容层要保持"联机无感"**：卡牌代码里看不到网络调用，只有选择 UI 和"是否为本地玩家"（`LocalContext.IsMe`）的判断。多人专属内容（巨型卷轴、愈合、可以扔给队友的药水等）见第 03、05 章。

---

## 4. 存档

### 4.1 位置与文件

根目录：`%AppData%/SlayTheSpire2/<平台>/<SteamID64>/`。平台目录是 `steam`；非 Steam 时用 `default`，编辑器里用 `editor`（`MegaCrit.Sts2.Core.Saves/UserDataPathProvider.cs:12-71`）。本机实际结构已核对，ID 已隐去。

| 文件 | 层级 | 内容 | 出处 |
|---|---|---|---|
| `profile.save` | 账号 | 当前档位等 | `Saves.Managers/ProfileSaveManager.cs:10,26` |
| `settings.save` | 账号 | 画面、键位、语言、Mod 列表与同意状态、`full_console` | `Saves.Managers/SettingsSaveManager.cs:10`、`Saves/SettingsSave.cs:112-114` |
| `profile{1..3}/saves/progress.save` | 档位（最多 3 个） | 解锁、纪元、统计（字段见第 06 章） | `ProfileSaveManager.cs:8`、`ProgressSaveManager.cs:35,62` |
| `profile{n}/saves/prefs.save` | 档位 | 快速模式、震屏、上传数据开关等偏好 | `PrefsSaveManager.cs:8,38` |
| `profile{n}/saves/current_run.save` / `current_run_mp.save` | 档位 | 单人 / 多人进行中的跑局 | `RunSaveManager.cs:17-19` |
| `profile{n}/saves/history/` | 档位 | 跑局历史 | `RunHistorySaveManager.cs:17,50` |
| `profile{n}/replays/latest.mcr` | 档位 | 最近一场战斗回放 | `RunManager.cs:1568` |
| `modded/…` | 账号下 | 运行 Mod 时整套档位换到这里；第一次以 modded 启动时会复制一份原版存档过来 | `UserDataPathProvider.cs:41-58`、`ModManager.cs:304-308,1261` |
| `console_history.log` | 账号 | 控制台最近 40 条命令 | `MegaCrit.Sts2.Core.DevConsole/DevConsole.cs:30-31` |
| `../localization_override/` | 全局 | 翻译测试用的覆盖文件 | `LocManager.cs:97` |

### 4.2 格式与写入安全

- **格式**：System.Text.Json 源生成序列化，`WriteIndented`，允许注释，字段名用 snake_case，枚举也转成 snake_case（`MegaCrit.Sts2.Core.Saves/MegaCritSerializerContext.cs:35`、`SnakeCaseJsonStringEnumConverter.cs`）。跑局存档的顶层字段：`schema_version, acts, modifiers, current_act_index, events_seen, pre_finished_room, odds, shared_relic_grab_bag, players, rng, visited_map_coords, map_point_history, save_time, start_time, run_time, win_time, ascension, num_reloads, platform_type, map_drawings, extra_fields, game_mode`，外加一个驼峰命名的例外 `dailyTime`（`MegaCrit.Sts2.Core.Saves/SerializableRun.cs:21-115`）。注意 `num_reloads`（SL 次数）会进遥测（§8）。
- **写入**：先写 `.tmp` 再 rename；旧文件另存一份 `.backup`。读取时主文件缺失或损坏就回退到 `.backup`，坏文件改名成 `.corrupt` 留作取证；写失败有重试（`FileWriteRetry`），专门应对杀毒软件、云同步扫描文件导致的偶发失败（`MegaCrit.Sts2.Core.Saves/GodotFileIo.cs:308-320`、`MigrationManager.cs:383-410`、`CorruptFileHandler.cs`）。
- **云存档**：Steam Remote Storage，"尽力而为"策略：云端失败不能影响本地保存和游戏启动。读文件永远读本地，启动时先把云端同步到本地（`MegaCrit.Sts2.Core.Saves/CloudSaveStore.cs:13-25`）。

### 4.3 迁移链（`data/csv/ch07_save_migrations.csv`）

| 存档类型 | 迁移 | 最低支持 | 当前 | 值得注意的迁移 |
|---|---|---|---|---|
| SerializableRun（跑局） | V12→V20，8 条 | 13 | 20 | 13→14 奖励卡池字段从单数改复数；14→15 补 GameMode；15→16 和 19→20 改 ID（`PREPARE→PREPARED`、`TOADPOLES_NORMAL→SEAPUNK_NORMAL`、`MONSTER.DOOR→DEPRECATED_MONSTER`、`SCARE→SIDESTEP`）；16→17 改长效糖果的计数字段；17→18 把木桩事件遭遇拆成 V1/V2/V3；18→19 把计数式随机数改成新的状态存法 |
| SerializableProgress（进度） | V20→V24，4 条 | 21 | 24 | 21→22 从敌人统计里删掉 Osty、Byrdpip、Pael's Legion（它们其实不是敌人）；23→24 修 PRG-7234：分数条推进计数却没给纪元，导致纪元丢失，迁移时按顺序把缺的纪元补上 |
| SettingsSave | V3→V8，5 条 | 4 | 8 | 4→5 删掉旧字段 `disabled_mods`（Mod 开关改存 `mod_settings`）；其余是手柄和键盘绑定的增补与改名 |
| RunHistory | V7→V10，3 条 | 8 | 10 | 复用跑局存档的同一张改名表 |
| PrefsSave / ProfileSave | V1→V2，各 1 条 | 2 | 2 | 只有"正式版前存档清空"的空迁移 |

机制要点：

- 每条迁移写成一个类，用 `[Migration(typeof(存档类型), from, to)]` 声明。启动时按最大 ToVersion 推出当前版本，并校验迁移链有没有断档、有没有一个版本被迁两次（`MigrationAttribute.cs`、`MigrationManager.cs:43-185`）。
- **"存档清空"做法**：每类存档的第一条迁移都是 "No-op migration for release save wipe"，再把最低支持版本抬到它的 to 版本。低于最低支持版本的存档直接作废，不用为测试期的格式写兼容代码。
- **改名表共享**：`SharedMigrationHelper.v100Renames` 用于跑局存档（V15→16）和跑局历史（V8→9），`v110Renames` 用于跑局存档（V19→20）、跑局历史（V9→10）和进度存档（V22→23）（`MegaCrit.Sts2.Core.Saves.Migrations.Shared/SharedMigrationHelper.cs:10-22`）。

### 4.4 校验 Validation

- 迁移完成后，还会把存档实际实例化一遍做深度校验，能拦住"JSON 能解析但内容非法"的情况，比如引用了已删除的修饰符、无效的卡牌 ID（`RunManager.cs:590-600` 的注释）。
- `DeserializationContext` 带路径栈（如 `Players[0].Deck[3].Id`）收集错误，分两级：**Warning**（数据降级，比如删掉的内容换成墓碑类，存档照常读）和 **Fatal**（读不了）（`MegaCrit.Sts2.Core.Saves.Validation/ValidationSeverity.cs`、`DeserializationContext.cs`）。
- 找不到的卡、遗物、附魔、修饰符一律退回 `DeprecatedCard/DeprecatedRelic/…`（`SaveUtil.cs:48-60`；墓碑类清单见第 08 章）。

**可借鉴**：①"空迁移 + 抬高最低支持版本"是 EA 转正式时清理历史包袱的干净办法；② 内容删除走墓碑类，存档里的 ID 永远能解析出来；③ 迁移链启动自检，缺环直接抛异常，有问题在开发期就会暴露。

---

## 5. Mod 支持

### 5.1 加载流程

| 步骤 | 行为 | 出处 |
|---|---|---|
| 0 | 带 `nomods` 启动参数就整体跳过 | `ModManager.cs:235-240` |
| 1 | 递归扫描游戏目录下的 `mods/`（来源记为 ModsDirectory）、`mods_STEAMTEST/`（按创意工坊来源处理，测试用）和已订阅的工坊条目，找所有 `.json` 清单。字段全空的 JSON 视为"不是清单"跳过 | `ModManager.cs:247-262,545-590` |
| 2 | 检查工坊 Mod 是否支持当前 Steam 分支（批量查询），只报错不阻止加载 | `ModManager.cs:685-690` |
| 3 | 剔除 settings 里禁用的 Mod；同一 Mod 本地和工坊各有一份时，加载版本号高的那份；版本相同或版本号解析不了时保留本地 `mods/` 那份、停用工坊版（`DisabledDuplicate`） | `ModManager.cs:471-520` |
| 4 | 按依赖做拓扑排序（Kahn 算法）；没有依赖关系的按玩家手动排的顺序 | `ModManager.cs:330-344` |
| 5 | 逐个 `TryLoadMod`：玩家没同意加载就标 Disabled；检查 ID 重复、循环依赖、`min_game_version`、依赖的最低版本 | `ModManager.cs:800-945` |
| 6 | `has_dll`：从 `<id>.dll` 加载进主 `AssemblyLoadContext`；`has_pck`：用 `ProjectSettings.LoadResourcePack(<id>.pck)` 挂载资源包（按 Godot 默认行为，可以覆盖同名 `res://` 资源，推断） | `ModManager.cs:948-990` |
| 7 | 有 `[ModInitializer("方法名")]` 就调用它，没有就 `new Harmony(作者.id).PatchAll(程序集)` | `ModManager.cs:995-1020`、`MegaCrit.Sts2.Core.Modding/ModInitializerAttribute.cs` |
| 8 | Mod 引用的 0Harmony 或 sts2 版本对不上时，`AssemblyResolve` 强制解析到游戏自带的版本 | `ModManager.cs:1158-1178` |

### 5.2 清单字段（`ModManifest`）

| 字段 | 含义 | 默认 |
|---|---|---|
| `id` | 唯一 ID，同时是 dll/pck 的文件名 | 必填 |
| `name / author / description / version` | 展示信息；`version` 按语义化版本解析，供依赖比较用 | |
| `has_pck` | 是否加载同名 `.pck`（Godot 资源包：场景、图片、本地化 JSON 等） | false |
| `has_dll` | 是否加载同名 `.dll`（C# 程序集） | false |
| `dependencies` | `[{id, min_version}]`；旧写法（纯字符串数组）还能用，但会报"需要迁移" | |
| `affects_gameplay` | **是否影响玩法**。true：Mod 内容计入联机 ID 哈希，双方必须都装；false：不计入哈希，联机时双方装的不一样也放行，只记警告，Mod 内容的 ID 排在 ID 表末尾 | **true** |
| `min_game_version` | 最低游戏版本，高于当前版本就不加载 | |

（`MegaCrit.Sts2.Core.Modding/ModManifest.cs`、`ModDependency.cs`；补丁说明 2026-11-13 的 MODDING 段也提到"affectsGameplay=false 的内容排到 ID 表末尾"）

`affects_gameplay` 是 Mod **自己声明**的，游戏不验证。一个声明为 false 的 Mod，照样可以往动作队列里塞出牌动作（见 §5.5 的例子）。

### 5.3 Mod 可用的官方接口（`ModHelper`）

- `AddModelToPool<卡池, 模型>()`：把新内容加进现有的卡池、遗物池；必须在卡池第一次合并 Mod 内容之前调用（`ModHelper.cs:408-458`）。
- `SubscribeForRunStateHooks / SubscribeForCombatStateHooks`：让 Mod 自己的模型收到钩子（`ModHelper.cs:460-525`）。
- 新的 `INetMessage`、`AbstractConsoleCmd`、`AbstractModel` 子类都会被反射自动发现（`MessageTypes.cs:13-18`、`DevConsole.cs:33-39`、`ModelDb.cs:81`）；Mod 本地化通过同名 loc 表合并（`ModManager.cs:1114-1128`）。
- `OnMetricsUpload` 委托：Mod 局本该上传遥测时调用它，方便 Mod 作者自己收数据（`ModManager.cs:214-218,1180-1186`）。

### 5.4 ModdingScreen 与 Mod 的连锁影响

- 第一次检测到 Mod 时弹窗"是否要加载模组？"，正文警告"模组是可能会损坏你的电脑的"。选"加载模组"会写入 `PlayerAgreedToModLoading=true` 并**退出游戏**，下次启动才生效（`MegaCrit.Sts2.Core.Nodes.Screens.ModdingScreen/NConfirmModLoadingPopup.cs:95-112`；`localization/zhs/main_menu_ui.json` 的 `MODDING_POPUP.*`）。
- Mod 菜单可以逐个启用/禁用，改了会显示"需要重启"；"获取模组"按钮打开 Steam 创意工坊，"制作模组"按钮打开社区模板仓库 `Alchyr/ModTemplate-StS2`（`NModdingScreen.cs:181-189`）。官方把社区模板当作 Mod 开发入口。
- 加载错误有 14 个 `MOD_ERROR.*` 本地化条目（含 `NONE`，实际报错 13 种）（重复 ID、循环依赖、版本过低、缺前置、程序集初始化失败……，`MOD_ERROR.*`）。

**"只要在跑 Mod"会改变什么**（`IsRunningModded` = 至少一个 Mod 处于 Loaded **或 Failed**，`ModManager.cs:1224-1231`）

| 方面 | 变化 | 出处 |
|---|---|---|
| 存档 | 整套档位切到 `modded/` 目录，第一次切换时复制原版存档 | `UserDataPathProvider.cs:41-58`、`ModManager.cs:304-308` |
| 开发者控制台 | 调试命令全部解锁（等同 `full_console`） | `MegaCrit.Sts2.Core.Nodes.Debug/NDevConsole.cs:359` |
| 遥测 | 跑局记录不上传，改为调用 Mod 的指标回调 | `MetricUtilities.cs:104-108` |
| Sentry | 启动阶段就关掉事件捕获，初始化结束后关闭 SDK，原生崩溃也不发 | `MegaCrit.Sts2.Core.Debug/SentryService.cs:59-76,147-172,633-680` |
| 报错弹窗 | 会话里任何一人带 Mod，就不显示"报告 Bug"按钮 | `MegaCrit.Sts2.Core.Nodes.CommonUi/NErrorPopup.cs:191-203` |
| 联机 | 见 §3.6；不同步、断线的报错信息会带上 modded 标记 | `NetErrorInfo.cs:161` |
| 调试拖放 | 允许把文件拖进窗口触发调试加载 | `MegaCrit.Sts2.Core.Debug/FileDropHandler.cs:18` |
| 角标 | 界面角落显示"modded"提示 | `NDebugInfoLabelManager.cs:148` |
| 成就 | 当前版本成就整体没开放（`AchievementsUtil.Unlock` 是空函数，平台策略用的是 Null 实现，补丁说明也说成就界面"还不存在"），所以谈不上 Mod 影响成就 | `MegaCrit.Sts2.Core.Platform/AchievementsUtil.cs:16,30-32` |
| 每日排行榜 | **客户端代码里没找到对 Mod 的拦截**：上传只检查"这局有没有人已经传过"。服务端会不会过滤无从得知 | `MegaCrit.Sts2.Core.Daily/DailyRunUtility.cs:22-37` |

### 5.5 社区 Mod 怎么接入：以本机的 STS2_Bridge 为例

`mods/STS2_Bridge/` 只有 `STS2_Bridge.dll` 和 `STS2_Bridge.json`（作者 kunology，0.3.0，`has_dll=true`、`has_pck=false`、`affects_gameplay=false`）。用 ilspycmd 反编译（输出在 `tmp/ch07_sts2_bridge_decomp/`，不在仓库内）看到：

- 用 `[ModInitializer("Initialize")]` 作入口，没有 Harmony 补丁。启动时挂到 Godot 的 `ProcessFrame` 信号上，在主线程跑一个任务队列，再开一个后台线程跑 `HttpListener`，只监听 `localhost/127.0.0.1:15526`。
- 提供 `/api/v1/singleplayer`、`/api/v1/multiplayer` 两个接口：GET 读状态，POST 执行 21 种动作（`play_card / use_potion / end_turn / choose_map_node / choose_event_option / shop_purchase / select_card_reward …`）。出牌、结束回合直接调官方的 `RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(new PlayCardAction(...))`。

这是一个"把游戏变成可编程环境"的外部控制桥，适合 AI 代理或自动化脚本。它说明官方的 GameAction 队列本身就是一个干净的外部输入接口：Mod 不用模拟鼠标，构造动作塞进队列就行，联机下也会自动经过 host 定序。它声明了 `affects_gameplay=false`，但实际上会改变玩家输入，这正是 §5.2 说的"自报字段不做验证"。

**设计观察 / 可借鉴（Mod）**：① Mod 内容和官方内容走同一套反射、同一套池子接口，没有第二套"Mod API"需要维护；② 用"存档隔离 + 每局遥测和崩溃上报一键全关"把 Mod 带来的数据污染挡在门外，比逐项判断"这个 Mod 合不合法"成本低得多；③ 联机靠内容哈希判断兼容，比比对 Mod 名单更可靠。

---

## 6. AutoSlay 自动跑局机器人

**用途**：冒烟测试。注释原话是"Runs the game automatically for smoke testing"（`MegaCrit.Sts2.Core.AutoSlay/AutoSlayer.cs:39-41`）。它从主菜单开始，一路打到第 49 层（最终 Boss），过程中检测卡死、记录内存快照找泄漏，失败时进程返回码为 1，方便 CI 判定。Sentry 会给这类事件打 `autoslay` 标签，便于过滤（`SentryService.cs:190-212`）。

| 项 | 值 | 出处 |
|---|---|---|
| 启动 | `--autoslay [--seed=…] [--log-file=…]`，前提 `!IsReleaseGame()`；正式包里 `IsReleaseGame()` 写死返回 `true`，**所以正式版启动不了** | `NGame.cs:695-702,762-765` |
| 准备 | 快速模式设为 Fast，关闭新手引导，强制揭示 4 个角色的解锁纪元，选牌器换成 `AutoSlayCardSelector`（随机选） | `AutoSlayer.cs:166-185` |
| 限时 | 整局 25 分钟；房间按类型各自限时（战斗 5 分钟、事件 3 分钟、商店 2 分钟，营火/宝箱/胜利房 30 秒）；界面多数 30 秒（水晶球、结算界面 2 分钟）；看门狗 30 秒没有进展就转储状态并判失败。`AutoSlayConfig` 里“房间 2 分钟 / 界面 30 秒”的默认值没有被任何代码引用 | `AutoSlayConfig.cs`；`AutoSlay.Handlers.Rooms/*.cs`、`Handlers.Screens/*.cs` 的 `Timeout` 属性；`AutoSlayer.cs:266,347` |
| 战斗 | 开局给自己 **999 层覆甲 + 999 层再生**；第 3 回合起每回合 **+200 力量**，用来快速结束拖长的战斗（比如"贪食者"的流沙计数会直接秒杀玩家）；每回合把能打的牌随机打完再结束回合 | `CombatRoomHandler.cs:22-62`（999、200、第 3 回合都是这里写死的字面量；`AutoSlayConfig.cs:48-61` 的同值常量 `combatStrengthRampStartTurn/PerTurn` 没被引用） |
| 其他房间 | 事件随机选，并处理事件里突然开打的战斗；营火随机选；商店把买得起的全买下；宝箱打开就拿；13 个界面处理器分别负责选卡、选遗物、变化、升级、附魔、水晶球小游戏、地图、结算界面 | `AutoSlay.Handlers.Rooms/*`、`Handlers.Screens/*` |
| 驱动方式 | 战斗用逻辑接口（`CardCmd.AutoPlay`、`PlayerCmd.EndTurn`），菜单和界面用 `UiHelper.Click → ForceClick` 直接点 UI 节点，所以 UI 流程也一并测到了 | `AutoSlay.Helpers/UiHelper.cs:17-19` |

**可借鉴**：AutoSlay 不追求"打得好"，只追求"把每种房间、每种界面都走一遍"，再配上"无敌 + 递增力量"保证一定能走到底。关注点是流程覆盖率和稳定性（卡死、泄漏、异常），不是平衡性。做平衡性需要单独的模拟器（这方面可以参考本机的离线战斗模拟方案）。

---

## 7. 开发者控制台 DevConsole（`data/csv/ch07_dev_console_commands.csv`）

| 项 | 内容 | 出处 |
|---|---|---|
| 打开 | 反引号 `` ` ``、单引号、`*`、`^`、Shift+8；F11 切换全屏；↑ 调历史命令；Tab 补全 | `NDevConsole.cs:357,375-395` |
| 权限 | 默认只有 5 条命令：`help / getlogs / log / open / cloud`。满足任一条件就解锁全部 40 条：编辑器、测试模式、**正在跑 Mod**、`settings.save` 里 `full_console=true` | `NDevConsole.cs:359`、`DevConsole.cs:28-39` |
| 联机 | 标了 `IsNetworked` 的命令在多人局里会包装成 `ConsoleCmdGameAction` 走动作队列，所有人一起执行，保证确定性 | `DevConsole.cs:276-290`、`MegaCrit.Sts2.Core.DevConsole/ConsoleCmdGameAction.cs` |
| 代价 | 开了 `full_console`：遥测不上传，Sentry 关闭，游戏内反馈会带上 `is_full_console` 标记 | `MetricUtilities.cs:77-81`、`SentryService.cs:653`、`FeedbackScreen/FeedbackData.cs:31` |

命令按用途分组（全量见 CSV）：

| 分组 | 命令 |
|---|---|
| 战斗作弊 | `damage, block, heal, kill, win, die, godmode, energy, stars, draw, power, afflict, enchant, upgrade` |
| 内容生成 | `card, remove_card, relic, potion, gold` |
| 跳转 | `act, room, event, ancient, fight, travel`（地图任意跳） |
| 进度 | `unlock`（标记全部已发现或全部解锁）、`achievement`（解锁/撤销） |
| 调试与运营 | `getlogs`（打包日志、截图、存档、回放成 BugReport zip）、`log`（按类型设日志级别）、`open`（打开 logs/saves/root/build-logs/loc-override 目录）、`dump`（导出模型 ID 库）、`sentry`（测试上报）、`cloud delete`（清空 Steam 云存档）、`leaderboard`（往排行榜灌测试分数）、`multiplayer`（打开多人菜单或测试场景） |
| 美术与宣传 | `art`（列出缺美术的内容）、`trailer`（用 0–9 和 +- 键显示/隐藏 UI 元素，拍预告片用）、`instant`（开启即时模式）、`bestiary`（打开图鉴，WIP） |

另外项目设置里还有一批调试按键（`input/debug_hide_*` 共 18 个（另有 `debug_speed_up/down`、`debug_unlock_characters`、`debug_slow_rewards`，`input/debug_*` 合计 22 个），比如隐藏意图、手牌、血条、休息点界面），以及一个叫 `input/banana` 的输入动作，用途不明（`data/csv/ch07_project_settings.csv`）。

---

## 8. 遥测、GameInfo 与崩溃上报

### 8.1 渠道总表（字段见 `data/csv/ch07_metrics_fields.csv`）

| 渠道 | 端点 | 触发 | 门槛 |
|---|---|---|---|
| 跑局记录 | `https://sts2-metric-upload.megacrit.com/record_data/`（PUT，JSON，15 秒超时） | 每局结束（多人局每人各传自己的） | 必须是正式构建（有 ReleaseInfo）、`prefs.upload_data` 开启、没开完整控制台、不在编辑器、不是放弃的局、不是第一局、没跑 Mod、标准模式、至少走过 5 个地图点 |
| 设置 | `…/record_settings/` | **第 5 局**结束时只传一次 | 同上前 4 条 |
| 纪元 | `…/record_epoch/` | 揭示纪元时 | 同上 |
| 成就 | `…/record_achievement/` | 解锁成就时（当前成就没开放，实际不会触发） | 同上 |
| 反馈 | `https://feedback.sts2.megacrit.com/feedback`（可以用环境变量 `STS2_FEEDBACK_URL` 改地址） | 玩家主动提交：描述、分类、表情、截图、日志 zip | 不受遥测开关限制 |
| 崩溃/异常 | Sentry（DSN 存在 `project.binary` 的 `sentry/config/dsn`，**已打码不列**） | 异常、原生崩溃、联机不同步、音频 bank 加载重试 | 见 §8.4 |

（`MetricUtilities.cs:29-125,180-250`、`MegaCrit.Sts2.Core.Nodes.Screens.FeedbackScreen/NSendFeedbackScreen.cs:279-281,721-745`）

### 8.2 跑局记录 RunMetrics 收集什么（26 个字段 + 5 个子结构）

| 类别 | 字段 |
|---|---|
| 身份与构建 | `buildId`（版本号）、`buildType`（Steam 分支）、`playerId`（**存档里随机生成的 7 位大写字母数字，不是 Steam ID**，`SerializableProgress.cs:181-188`） |
| 局面 | `character, team, numPlayers, ascension, win, floorReached, killedByEncounter, runPlaytime, numReloads` |
| 玩家画像 | `totalPlaytime, totalWinRate`（存档累计） |
| 决策 | `cardChoices[{picked[],skipped[]}]`、`eventChoices[{id,act,picked}]`、`ancientChoices[{picked,skipped[]}]`、`campfireUpgrades`、`relicBuys/potionBuys/colorlessBuys`、`potionDiscards` |
| 战斗 | `encounters[{id, damage（按 0–100 截断）, turns}]`、`actWins[{act,win}]` |
| 终局构筑 | `deck`、`relics`（只传 Entry，比如 `BASH`） |

上传前会临时把语言切成英文（`StartOverridingLanguageAsEnglish`），保证事件选项的 key 在所有语言下一致（`MetricUtilities.cs:118-123`）。

**策划视角**：这份字段表就是官方的"平衡性仪表盘"数据源。**选/跳记录**能算每张卡的选取率，**每场战斗的掉血和回合数**能算遭遇难度，`killedByEncounter` 能算死因分布，`numReloads` 能看 SL 行为，Ancient 选项的 picked/skipped 能看祝福受欢迎程度。没收集的东西也值得注意：**没有**逐回合的出牌记录，**没有**战斗内的具体决策，**没有**设备指纹（设备信息只在设置记录里有一次：OS、内存 GB、显示器数量、分辨率）。这是在数据价值和隐私、带宽之间做的取舍。

### 8.3 GameInfo 上传器

`NGameInfoUploader` 在正式包里是个**空壳**：类里只剩 Godot 样板代码，对应场景 `src/GameInfo/GameInfoUploader.tscn` 只有一个写着"Uploading "的文本框（`MegaCrit.Sts2.GameInfo/NGameInfoUploader.cs`）。数据结构还在：`CardInfo / RelicInfo / PotionInfo / EventInfo / EncounterInfo / AncientChoiceInfo / NeowBonusInfo / EnchantmentInfo / DailyMods / Keywords`，共同字段是 `name / bot_keyword / bot_text`，卡牌还有 `color, rarity, type, base_damage, energy, star_cost, text, has_art, has_joke_art`（`MegaCrit.Sts2.GameInfo.Objects/*.cs`）。`EventModel.GameInfoOptions` 的注释说它"upload info about the game for lookup elsewhere"（`MegaCrit.Sts2.Core.Models/EventModel.cs:140-143`）。

推断：这是内部工具，负责把全部内容的文本导出到一个外部查询库。从 `bot_keyword/bot_text` 的命名看，很可能是给聊天机器人用的（社区里常见的"输入卡名弹出卡面"机器人）。上传逻辑在正式构建里被裁掉了，端点不可考。

### 8.4 Sentry 配置

| 项 | 值 | 出处 |
|---|---|---|
| 初始化 | `[ModuleInitializer]` 调 `SentryGodotInitializer.AutoInit()`，再由 `SentryBootstrap` 自动加载完成配置；编辑器里默认不启用，`force-sentry` 参数可以强制开启 | `SentryAutoInit.cs`、`SentryService.cs:78-140` |
| DSN | 从 `ProjectSettings["sentry/config/dsn"]` 读取（**已打码**） | `SentryService.cs:33,466` |
| 采样率 | 按 Steam 分支：public 10%，public-beta 20%，private-beta 100%，其他已知分支 10%；非 Steam 构建直接关闭；启动早期的原生错误按 10% 采样 | `SentryService.cs:37,278-308` |
| 隐私 | `SendDefaultPii=false`；截图、日志附件都关（`attach_screenshot/attach_log=false`）；面包屑上限 100 条 | `SentryService.cs:117`；project settings 表 |
| 关闭条件 | 初始化后直接关 SDK：Steam 没初始化（非 Steam 构建）、开了完整控制台、跑 Mod（带 `force-sentry` 时都不关）；`prefs.upload_data=false` 不关 SDK，而是逐条事件丢弃 | `SentryService.cs:59-76,147-172,612-680` |
| 附带上下文 | 场景名、是否在局内、种子、进阶、幕/层、模式、房间类型、事件、角色、人数、遭遇、轮数、敌人列表、玩家 HP、语言，以及构建 commit 和程序集哈希 | `SentryService.cs:466-520` |

### 8.5 游戏内反馈与 getlogs

反馈界面提交的字段有：描述、分类、版本、`unique_id`（就是上面那个 7 位 ID）、commit、分支、会话 ID、`is_modded`、`is_full_console`、语言，外加截图和日志 zip（`FeedbackData.cs`、`NSendFeedbackScreen.cs:721-745`）。`getlogs` 生成的 `BugReport<名字>-<时间>.zip` 包含 profile/settings/progress/当前跑局（单人和多人）/prefs 存档、`latest.mcr`、最近一份跑局历史、最近 1 天内产生的 `.corrupt` 文件、日志和截图（`GetLogsConsoleCmd.cs:395-430`）。**QA 闭环**是：玩家一键提交 → 开发拿到存档和回放 → 回放复现。

---

## 9. 本地化管线

| 项 | 内容 | 出处 |
|---|---|---|
| 语言 | **16 种**：eng、zhs、zht、deu、esp（拉美西语 es-419）、fra、ind、ita、jpn、kor、pol、ptb、rus、spa（西班牙西语 es-ES）、tha、tur。PCK 自带的 README 只列了 14 个，漏了 fra 和 spa | `LocManager.cs:101-119`；`localization/README.md` |
| 完成度 | `completion.json` 记录每种语言的 key 数：eng 7,027，多数语言 6,930–6,937，德语 6,899，**泰语 5,063**（约 72%） | `localization/completion.json` |
| 文件 | 每种语言 46 个 JSON 表；`patch_notes/` 只有 eng（127 份）和 zhs（1 份）有；key 规则是"类名 SNAKE_CASE + `.title/.description/…`" | `localization/zhs/` |
| 工作流 | Weblate 托管翻译（项目名 slaythespire2），每周 CI 拉取翻译 → 只锁定有改动的组件 → 开合并请求 → CI 校验（BBCode 标签必须和英文一致、占位符保留、SmartFormat 语法合法、特定数字保留）→ 人工合并 → 回传并解锁。修改英文会自动上传到 Weblate 作为源文 | `localization/README.md`、`LocManager.cs:50-75` |
| 插值 | SmartFormat 3，在内置的复数、条件、选择、列表等格式器之外，**自定义 9 个**：`diff`（和基础值比较后高亮：升级或增益为绿、减益为红）、`inverseDiff`、`abs`、`n`（按地区格式化数字）、`energyIcons`（1–3 点画对应个数的能量图标，4 点以上写"数字 + 图标"，图标随角色变化）、`starIcons`、`percentMore`、`percentLess`、`show`（只在升级后显示） | `LocManager.cs:234-238`、`MegaCrit.Sts2.Core.Localization.Formatters/*.cs`、`EnergyIconsFormatter.cs:74-87` |
| 动态变量 | 24 个 `DynamicVar` 子类（目录里 26 个文件，另 2 个是基类 `DynamicVar` 和容器 `DynamicVarSet`）：Damage/Block/Heal/MaxHp/HpLoss/Gold/Energy/Stars/Forge/Summon/Repeat/Cards/Power/IfUpgraded/Calculated*… 卡牌数值显示的就是这些变量的"预览值"，所以力量、易伤等加成会实时反映到卡面上 | `MegaCrit.Sts2.Core.Localization.DynamicVars/` |
| 字体 | 拉丁语系默认用 Kreon、Spectral、Bitter，控制台用 Source Code Pro；以下语言替换字体：zhs（思源黑体 Mono CJK SC 常规 / 思源宋体 SC 粗、中）、zht（TC 版）、jpn（Noto Sans CJK JP）、kor（京畿千年明朝体粗）、tha（CS Chat Thai UI）、**rus 和 pol 共用 Fira Sans Extra Condensed**（推断是 Kreon 缺这两种语言的字形） | `MegaCrit.Sts2.Core.Localization.Fonts/FontManager.cs:19-28`、`FontPathSets/ZhsFontPathSet.cs`；`data/pck_index.csv` 的 `fonts/` |
| 测试 | 翻译人员把 JSON 放进 `%AppData%/SlayTheSpire2/localization_override/` 就能在游戏里直接预览，不用重新打包；加载时会校验 SmartFormat 语法，有错的条目跳过 | `LocManager.cs:85-97` |
| 遥测一致性 | 上传遥测时强制切到英文 | §8.2 |

**可借鉴**：①"变量名插值 + `diff` 高亮"让数值修改不用动文本，卡面"变强/变弱"的视觉反馈也统一由格式器负责；② Weblate 的"只锁有改动的组件"兼顾了翻译人员的并行工作和合并的安全性；③ 提供本地覆盖目录让翻译人员自测，比来回发包效率高得多。

---

## 10. 音频与动画管线

### 10.1 FMOD

| 项 | 内容 | 出处 |
|---|---|---|
| Bank | `banks/desktop/` 下 12 个：Master、Master.strings、sfx（42.5 MB）、ambience、temp_sfx，以及按幕拆分的音乐 bank：act1_a1/a2/b1、act2_a1/a2、act3_a1/a2（每个 30–42 MB）。只列路径，不导出 | `data/pck_index.csv`；`Fmod/General/banks_path` |
| 事件 | 代码里写死的 FMOD 事件路径有 369 条（`event:/sfx/...` 350 条，music 18 条，temp 1 条），动态拼接的路径不在这个数里 | `grep "event:/"` 统计 |
| 调用 | C# 的 `NAudioManager` 通过 Godot `Call` 调 GDScript 代理 `audio_manager_proxy.gd`，代理再调 FMOD GDExtension。接口有 PlayOneShot、PlayLoop/StopLoop、SetParam、PlayMusic、UpdateMusicParameter；音乐由 `NRunMusicController` 和 `music_controller_proxy.gd` 驱动 | `MegaCrit.Sts2.Core.Nodes.Audio/NAudioManager.cs:143-253`；`scenes/game.tscn:64-71`、`scenes/run.tscn:44-48` |
| 音量曲线 | 滑条值**平方**后再交给 FMOD（`Mathf.Pow(volume, 2)`），近似人耳的感知曲线 | `NAudioManager.cs:225-253` |
| 稳定性 | 幕音乐 bank 偶尔加载失败（推测是杀毒、云同步占用文件），失败后 bank 一直没加载，"Progress"参数设不进去，战斗音乐就卡在最后一个状态（源码称"music inertia"）。现在会自动重试，每次非一次成功的情况都上报 Sentry，用来评估重试窗口够不够 | `MegaCrit.Sts2.Core.Nodes.Audio/ActBankLoadRetry.cs:9-30` |
| 旁路 | `TmpSfx` 里引用的 33 个临时音效 mp3（预加载清单 `assetPaths` 里是 23 个 mp3 + 1 个 tres；PCK 的 `debug_audio/` 共 50 个 mp3）（比如 `blunt_attack.mp3`、`card_exhaust.mp3`）由 `NDebugAudioManager` 的 10 个 `AudioStreamPlayer` 直接播放，不经过 FMOD（详见第 08 章） | `MegaCrit.Sts2.Core.Audio.Debug/TmpSfx.cs`、`scenes/game.tscn:73-95` |

### 10.2 Spine 动画绑定

spine-godot 只提供 GDScript/GDExtension 接口，没有 C# 封装。MegaCrit 在 `MegaCrit.Sts2.Core.Bindings.MegaSpine/` 下写了 14 个薄包装类（`MegaSprite / MegaSkeleton / MegaAnimationState / MegaTrackEntry / MegaBone / MegaSkin / MegaEvent…`），内部全是 `Call("set_animation", name, loop, track)` 这种字符串方法调用（`MegaAnimationState.cs:28-124`）。`MegaSprite` 专门处理了一个时序坑：Godot 的 `_Ready` 是子节点先于父节点执行，子节点就绪时父节点的 SpineSprite 骨骼还没建好，所以提供了 `TryGetAnimationState` 和带明确报错的 `GetAnimationState`（`MegaSprite.cs:125-151`）。PCK 里有 164 个 `.spskel` 骨骼和 170 个 `.spatlas` 图集（只统计，不导出）。

---

## 11. PCK 里的 GDScript 与 addons

PCK 里一共 56 个 `.gdc`（GDScript 编译产物，文件头是 `GDSC`，正文是压缩过的二进制 token，本机缺 zstd 没有解开），对应的 `.gd.remap` 把 `res://…gd` 重定向到 `.gdc`。玩法逻辑**全在 C#**，GDScript 只做下面这些：

| 位置 | 内容 | 作用 |
|---|---|---|
| `src/gdscript/` 4 个 | `audio_manager_proxy`、`music_controller_proxy` | C# 到 FMOD 插件的桥（§10.1） |
| | `play_vfx_on_key_press`、`play_vfx_tool` | 按键触发特效的调试工具 |
| `src/gdscript/testing/` 26 个 | `big_slash_impact_tester`、`hyperbeam_tester`、`card_exhaust_tester`、`spine_sprite_auto_player`… | 美术和特效的单项测试场景 |
| `src/gdscript/tools/` 2 个 | `gen_font_preload`、`profile_font_cost` | 生成字体预加载清单（对应 `fonts/preload_manifest.json`），测字体开销 |
| `addons/fmod/` | FMOD 官方 Godot 插件：`FmodManager` 自动加载、bank 浏览器、事件和参数面板、Android 导出插件 | 编辑器工具，运行时只用到 `FmodManager` |
| `addons/sentry/` | `SentryBootstrap.cs`（自动加载）、`user_feedback/` 反馈表单（GDScript） | 崩溃上报 |
| `addons/spine/` | `spine_godot_extension.gdextension` | Spine 运行时 |
| `addons/megacontentcreator/` | 内容脚手架面板（§2.8） | 编辑器工具 |
| `addons/atlas_generator/` | `atlas_generator`、`migrate_scene_uids` | 打图集，迁移场景 UID（运行时由 `AtlasResourceLoader` 读图集） |
| `addons/dev_tools/` | `dev_tools.gdc` | 编辑器开发工具（具体功能没解开） |
| `addons/mega_text/` | `MegaLabel / MegaRichTextLabel / ThemeConstants`（C#）+ `plugin.gd` | 自研文本控件，配合本地化字体替换和富文本效果（`[jitter]`、`[sine]` 等） |
| 其他 | `scenes/backgrounds/little_light_script.gdc`、`shaders/blur/ShaderGenerator.gdc` | 背景小光点、模糊着色器生成 |

`editor_plugins/enabled` 里启用了 atlas_generator、dev_tools、fmod、mega_text、megacontentcreator 5 个编辑器插件（project settings 表）。PCK 里还能看到大量编辑器侧的内容（内容生成面板、bank 浏览器、测试场景），说明导出时没做裁剪。这对拆解者是好事，也说明官方不在意 PCK 是否暴露工具链。

---

## 12. 给策划的可借鉴清单

1. **内容 = 类 + 数值声明块 + 按变量名插值的文本**，再加脚手架面板。行为差异大的内容不要硬塞进数据表。（§2.8）
2. **canonical/mutable 分离**：配置对象只读，运行时一律克隆，用断言守住边界，"改了配置导致所有实例一起变"的 bug 就被系统性消除了。（§2.2）
3. **所有改状态的操作都是异步命令**：表现节奏可以写在逻辑里，测试和机器人跑的时候跳过等待即可。（§2.4）
4. **单机即一人联机**：同一队列、同一校验点，从第一天起就在测联机路径。（§3.2）
5. **"输入定序 + 确定性 + 每动作校验和 + 回放"**：回合制联机最省带宽、最好调试的组合；不同步时不自动纠正，而是把现场完整上报。（§3.5、§3.9）
6. **握手比内容哈希，不比版本号**：内容表有任何不一致都能拦下，Mod 兼容也走同一套机制。（§3.6）
7. **存档：空迁移清理历史 + 墓碑类兜底 + 迁移链自检 + .backup/.corrupt 留证**。（§4）
8. **Mod 一刀切隔离**：存档分目录，每局遥测和崩溃上报全关（纪元/设置遥测仍照传），不在报错里给 Mod 玩家显示"报告 Bug"。（§5.4）
9. **遥测只收"决策和结果"**：选/跳、每场战斗的掉血和回合数、死因、构筑，用匿名的随机 ID，最低门槛 5 层；设备信息只在第 5 局传一次。（§8.2）
10. **AutoSlay 式冒烟机器人**：用"无敌 + 递增力量"换流程覆盖率，再配上看门狗和内存快照。（§6）

---

### 本章没解决 / 拿不准

- `mega_content_creator.gdc`、`dev_tools.gdc` 等 GDScript 是压缩的二进制 token，本机 Python 没有 zstd 解压，没能看到脚手架的生成模板和弃用流程的具体操作。
- 断线玩家在战斗中的处理（回合是否自动结束、谁替他做选择）没找到明确代码；也没有找到 host 迁移的代码。
- `NGameInfoUploader` 在正式包里被裁空，"bot_keyword/bot_text 是给聊天机器人用的"属于推断，端点不明。
- 每日排行榜在客户端没有 Mod 拦截，服务端会不会过滤无从得知。
- `affects_gameplay=false` 的 Mod 如果改了玩法（比如 STS2_Bridge 往队列塞动作），联机时可能引发不同步，这一点只是代码推断，没有实测。
