# 杀戮尖塔2 静态拆包记录

## 目标

| 项 | 值 |
|---|---|
| 游戏 | Slay the Spire 2（Mega Crit），Steam appid 2868840，build 26655341 |
| 版本 | v0.111.1，commit cc1f9462，构建时间 2026-11-13T12:26:17-08:00（`release_info.json`） |
| 安装目录 | `C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\`（2.8 GB） |
| 引擎 | Godot 4.5.1（PCK 头）+ .NET 9.0.7（`sts2.runtimeconfig.json`） |

## 安装目录结构

| 文件 | 大小 | 说明 |
|---|---|---|
| `SlayTheSpire2.exe` | 895 MB | Godot 导出模板（Windows x86_64） |
| `SlayTheSpire2.pck` | 1.99 GB | 全部资源，PCK v3，未加密 |
| `data_sts2_windows_x86_64/sts2.dll` | 9.7 MB | 游戏逻辑主程序集，未混淆 |
| `data_sts2_windows_x86_64/sts2.xml` | 5.6 MB | 随包发布的 XML 文档注释 |
| `data_sts2_windows_x86_64/0Harmony.dll` 等 | — | Harmony 2.4.2 + MonoMod（Mod 运行时补丁），SmartFormat、Sentry、Steamworks.NET、Vortice |
| `fmod*.dll`、`libGodotFmod*.dll` | — | FMOD Studio 音频 |
| `libspine_godot*.dll` | — | Spine 骨骼动画 |
| `libsentry*.dll`、`crashpad_*` | — | 崩溃上报 |
| `launch_d3d12/opengl/vulkan.bat` | — | 渲染后端切换 |
| `mods/STS2_Bridge/` | — | 用户自装的第三方 Mod（kunology 0.3.0），非官方内容 |

## 有没有加密

**没有。** 三层都是明文：

1. **C# 程序集**：标准 .NET IL，无混淆器痕迹，类名 / 方法名 / 私有字段全保留，还带官方 XML 文档注释。ILSpy 直接出可读源码。
2. **PCK 目录**：头部 `pack_flags = 2`（只有 `PACK_REL_FILEBASE`，没有 `PACK_DIR_ENCRYPTED`）。
3. **PCK 文件**：15,891 个条目的 `flags` 全为 0，没有一个带 `PACK_FILE_ENCRYPTED`；解出后 MD5 全部与目录记录一致。

与一代对比（凭公开知识）：一代是 Java/libGDX 的 `desktop-1.0.jar`，同样不加密不混淆。Mega Crit 两代都默认对 Mod 社区开放，二代更进一步，直接随包带了 Harmony 和 `mods/` 加载器。

## PCK 格式（v3）

```
0x00  "GDPC"
0x04  u32 pack_format_version = 3
0x08  u32 godot major/minor/patch = 4 / 5 / 1
0x14  u32 pack_flags = 2 (REL_FILEBASE)
0x18  u64 file_base = 0x70
0x20  u64 dir_offset = 0x7690F100   ← v3 把目录挪到文件末尾
0x28  16 × u32 reserved
dir:  u32 count = 15891
      { u32 path_len; path (4 字节对齐, 0 填充); u64 offset(+file_base); u64 size; md5[16]; u32 flags } × count
```

## 重跑命令

工作目录 `<仓库根>\`。

```bash
G="/c/Program Files (x86)/Steam/steamapps/common/Slay the Spire 2"
# 1. 反编译（ILSpy 8.2，约 46 秒，3,538 个 .cs / 28 MB）
ilspycmd -p -o csharp/sts2_src -r "$G/data_sts2_windows_x86_64" "$G/data_sts2_windows_x86_64/sts2.dll"
# 2. PCK 目录
python -I scripts/pck_list.py "$G/SlayTheSpire2.pck" list data/pck_index.csv
# 3. 只解非美术文件（8,055 个 / 40 MB）
python -I scripts/pck_list.py "$G/SlayTheSpire2.pck" extract data/pck_text '\.(json|md|cfg|tres|tscn|gdshader|gdshaderinc|remap|gdc|binary|bin|dat|cs|gdextension|tpsheet|spatlas)$'
# 4. 内容模型 → data/csv/*.csv
python -I -X utf8 scripts/s1_extract_models.py
```

## PCK 内容构成

| 扩展名 | 个数 | 体积 | 说明 |
|---|---:|---:|---|
| `.ctex` | 3,555 | 1,229 MB | Godot 压缩纹理（`.godot/imported/` 下，原图路径看同名 `.import`） |
| `.fontdata` | 20 | 389 MB | 字体（CJK 字体占大头） |
| `.bank` | 12 | 316 MB | FMOD 音频 bank |
| `.spskel` / `.spatlas` | 164 / 170 | 21 MB | Spine 骨架 / 图集 |
| `.json` | 741 | 10.9 MB | 本地化（16 语言 × ~46 表）等 |
| `.tscn` / `.tres` | 1,037 / 2,296 | 8.6 MB | Godot 文本场景 / 资源 |
| `.cs` | 3,441 | ≈0 | 每个只有 1 字节的占位（脚本路径引用，真代码在 sts2.dll） |
| `.md` | 129 | 0.9 MB | 127 份英文补丁说明 + 1 份简中 + 本地化 README |
| `.gdc` | 56 | 0.1 MB | 编译后的 GDScript |

## 内容是代码不是表

卡牌、遗物、怪物、遭遇、事件、幕全部是 `sts2.dll` 里的 C# 类。数值写在构造函数和属性里，比如：

```csharp
public sealed class Bash : CardModel {
    CanonicalVars => [ new DamageVar(8m, ValueProp.Move), new PowerVar<VulnerablePower>(2m) ];
    public Bash() : base(2, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy) {}
    OnUpgrade() { Damage.UpgradeValueBy(2m); Vulnerable.UpgradeValueBy(1m); }
}
```

怪物数值随进阶变化的写法是 `AscensionHelper.GetValueIfAscension(AscensionLevel.X, 进阶值, 普通值)`，注意第二个参数才是进阶值。文本 key 由类名转 SNAKE_CASE 得到（`StrikeIronclad` → `STRIKE_IRONCLAD.title`），见 `MegaCrit.Sts2.Core.Helpers/StringHelper.cs:34`。

`scripts/s1_extract_models.py` 用正则从源码抽数值，配上本地化 JSON，生成 `data/csv/` 下 14 张基础表。正则有覆盖边界：条件分支招式、自定义升级逻辑这类复杂写法，要回源码确认。
