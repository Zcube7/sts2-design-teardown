# -*- coding: utf-8 -*-
"""第 07 章（技术架构与联机）抽表脚本。
从 ILSpy 反编译源码里抽出 4 张表：
  data/csv/ch07_dev_console_commands.csv   开发者控制台命令
  data/csv/ch07_multiplayer_messages.csv   联机消息（INetMessage）+ 玩家输入动作（INetAction）
  data/csv/ch07_save_migrations.csv        存档迁移链
  data/csv/ch07_metrics_fields.csv         遥测字段（metrics / feedback / sentry 上下文）
用法: python -I -X utf8 scripts/ch07_extract.py
正则抽取，复杂写法可能漏，表里每行都带源码出处方便回查。
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "csharp" / "sts2_src"
OUT = ROOT / "data" / "csv"


def rel(p: Path) -> str:
    return p.relative_to(SRC).as_posix()


def line_of(text: str, pattern: str) -> int:
    m = re.search(pattern, text, re.M)
    return text[: m.start()].count("\n") + 1 if m else 0


def summary_of(text: str, before_pattern: str) -> str:
    """取紧挨在 before_pattern 之前的 /// <summary> 文档注释，压成一行。"""
    m = re.search(before_pattern, text, re.M)
    if not m:
        return ""
    head = text[: m.start()]
    blocks = re.findall(r"((?:[ \t]*///.*\n)+)\s*(?:\[[^\n]*\]\s*)*$", head)
    if not blocks:
        return ""
    raw = blocks[-1]
    raw = re.sub(r"^[ \t]*/// ?", "", raw, flags=re.M)
    raw = re.sub(r"<see cref=\"[A-Z]:[\w\.`]*\.(\w+)[^\"]*\"\s*/>", r"\1", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    return re.sub(r"\s+", " ", raw).strip()


def prop_value(text: str, name: str, default: str = "") -> str:
    m = re.search(r"\b%s\s*=>\s*([^;]+);" % name, text)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b%s\s*\{\s*get\s*\{\s*return\s+([^;]+);" % name, text, re.S)
    if m:
        return m.group(1).strip()
    return default


def unquote(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


# ---------------------------------------------------------------- 1. 控制台命令
def dev_console():
    d = SRC / "MegaCrit.Sts2.Core.DevConsole.ConsoleCommands"
    rows = []
    for f in sorted(d.glob("*ConsoleCmd.cs")):
        if f.name == "AbstractConsoleCmd.cs":
            continue
        t = f.read_text(encoding="utf-8")
        name = unquote(prop_value(t, "CmdName"))
        if not name:
            continue
        debug_only = prop_value(t, "DebugOnly", "true（基类默认）")
        rows.append({
            "cmd": name,
            "args": unquote(prop_value(t, "Args")),
            "description_en": unquote(prop_value(t, "Description")),
            "is_networked": prop_value(t, "IsNetworked"),
            "debug_only": debug_only,
            "class": f.stem,
            "source": "%s:%d" % (rel(f), line_of(t, r"CmdName\s*=>")),
        })
    rows.append({
        "cmd": "help", "args": "[cmd]", "description_en": "Built-in: lists all registered commands or shows one command's args/description.",
        "is_networked": "false", "debug_only": "false（内建）", "class": "DevConsole.HelpCmd",
        "source": "MegaCrit.Sts2.Core.DevConsole/DevConsole.cs:318",
    })
    write("ch07_dev_console_commands.csv", rows)
    return rows


# ---------------------------------------------------------------- 2. 联机消息
DIRECTION_HINTS = [
    (re.compile(r"\bfrom clients? to (the )?host|to host|Sent from clients", re.I), "client→host"),
    (re.compile(r"from (the )?host to (all )?clients|host to all|to all clients from host|Sent to all clients", re.I), "host→clients"),
    (re.compile(r"Broadcast to all peers|to all peers|to all other players", re.I), "广播"),
]


def guess_direction(name: str, summary: str, broadcast: str) -> str:
    if name.endswith("ResponseMessage"):
        return "host→client（应答，按命名）"
    # 双向消息：注释写明先 host→client、再 client→host（如 StateDivergenceMessage），不能被下面的 "to host" 规则吃掉
    if re.search(r"from host to client, then .*from client to host", summary, re.I):
        return "双向：host→client 先发（附 host 状态），client→host 回发（附自己状态）"
    if re.search(r"from the host to|by a host to|by the host|Sent by the host", summary, re.I):
        return "host→clients"
    for rx, label in DIRECTION_HINTS:
        if rx.search(summary):
            return label
    if name.startswith("Request") or name.startswith("Client"):
        return "client→host（按命名推断）"
    if broadcast == "true":
        return "发给 host 后由 host 回显给全体（ShouldBroadcast）"
    return ""


def messages():
    rows = []
    for d in sorted(SRC.glob("MegaCrit.Sts2.Core.Multiplayer.Messages*")):
        group = d.name.replace("MegaCrit.Sts2.Core.Multiplayer.Messages", "").lstrip(".") or "(root)"
        for f in sorted(d.glob("*.cs")):
            t = f.read_text(encoding="utf-8")
            m = re.search(r"public ((?:record )?struct|class) (\w+)\s*:\s*([^\n{]+)", t)
            if not m or "INetMessage" not in m.group(3):
                continue
            kind, name, bases = m.group(1), m.group(2), m.group(3)
            summ = summary_of(t, r"public (?:record )?(struct|class) %s\b" % name)
            fields = re.findall(r"^\t(?:public|private) (?!static|const|readonly static)([\w<>\[\]\?, \.]+?) (\w+)(?: = [^;]+)?;", t, re.M)
            fields = [n for (ty, n) in fields if not n.startswith("_")]
            bc = prop_value(t, "ShouldBroadcast")
            rows.append({
                "group": group,
                "message": name,
                "kind": kind,
                "should_broadcast": bc,
                "transfer_mode": prop_value(t, "Mode").replace("NetTransferMode.", ""),
                "should_buffer": prop_value(t, "ShouldBuffer"),
                "run_location_targeted": "true" if "IRunLocationTargetedMessage" in bases else "false",
                "log_level": prop_value(t, "LogLevel").replace("LogLevel.", ""),
                "fields": " ".join(fields),
                "direction": guess_direction(name, summ, bc),
                "summary_en": summ,
                "source": "%s:%d" % (rel(f), line_of(t, r"public (?:record )?(struct|class) %s\b" % name)),
            })
    d = SRC / "MegaCrit.Sts2.Core.GameActions"
    for f in sorted(list(d.glob("Net*.cs")) + [SRC / "MegaCrit.Sts2.Core.DevConsole" / "NetConsoleCmdGameAction.cs"]):
        t = f.read_text(encoding="utf-8")
        m = re.search(r"public (struct|class) (\w+)\s*:\s*([^\n{]+)", t)
        if not m or "INetAction" not in m.group(3):
            continue
        name = m.group(2)
        to = re.search(r"return new (\w+)\(", t)
        fields = re.findall(r"^\tpublic (?!static|const)([\w<>\[\]\?, \.]+?) (\w+);", t, re.M)
        rows.append({
            "group": "INetAction（玩家输入，装在 RequestEnqueueAction/ActionEnqueued 里传）",
            "message": name,
            "kind": m.group(1),
            "should_broadcast": "", "transfer_mode": "Reliable（随外层消息）", "should_buffer": "",
            "run_location_targeted": "true（随外层消息）", "log_level": "",
            "fields": " ".join(n for _, n in fields),
            "direction": "client→host 请求，host 定序后广播",
            "summary_en": "-> %s" % (to.group(1) if to else ""),
            "source": "%s:%d" % (rel(f), line_of(t, r"public (struct|class) %s\b" % name)),
        })
    write("ch07_multiplayer_messages.csv", rows)
    return rows


# ---------------------------------------------------------------- 3. 存档迁移
# 没有文档注释的迁移，按 ApplyMigration 方法体人工概括（中文）
MIGRATION_NOTES = {
    "SettingsSaveV4ToV5": "（人工概括）删除旧字段 disabled_mods（Mod 开关改存 mod_settings）",
    "SettingsSaveV5ToV6": "（人工概括）controller_mapping 补 ui_alt_up/down/left/right 默认绑定到右摇杆",
    "SettingsSaveV6ToV7": "（人工概括）controller_mapping 删 ui_accept，补 ui_confirm（北键）与 ui_end_turn 默认绑定",
    "SettingsSaveV7ToV8": "（人工概括）keyboard_mapping 里把 confirm 键设成与 end_turn 相同",
}


def migrations():
    rows = []
    for d in sorted(SRC.glob("MegaCrit.Sts2.Core.Saves.Migrations.*")):
        for f in sorted(d.glob("*.cs")):
            t = f.read_text(encoding="utf-8")
            m = re.search(r"\[Migration\(typeof\((\w+)\),\s*(\d+),\s*(\d+)\)\]", t)
            if not m:
                continue
            cls = re.search(r"public class (\w+)", t).group(1)
            logs = re.findall(r'Log\.Info\(\$?"([^"]+)"', t)
            renames = re.findall(r"SharedMigrationHelper\.(v\d+Renames)", t)
            rows.append({
                "save_type": m.group(1),
                "from_version": int(m.group(2)),
                "to_version": int(m.group(3)),
                "class": cls,
                "summary_en": summary_of(t, r"\[Migration\(") or MIGRATION_NOTES.get(cls, ""),
                "first_log": logs[0] if logs else "",
                "uses_shared_renames": ",".join(renames),
                "source": "%s:%d" % (rel(f), line_of(t, r"\[Migration\(")),
            })
    mm = (SRC / "MegaCrit.Sts2.Core.Saves.Migrations" / "MigrationManager.cs").read_text(encoding="utf-8")
    mins = dict(re.findall(r"SetMinimumSupportedVersion<(\w+)>\((\d+)\)", mm))
    for st in sorted({r["save_type"] for r in rows}):
        latest = max(r["to_version"] for r in rows if r["save_type"] == st)
        rows.append({
            "save_type": st, "from_version": "", "to_version": latest, "class": "(汇总)",
            "summary_en": "minimum supported version = %s; latest = %d (derived from max ToVersion)" % (mins.get(st, "?"), latest),
            "first_log": "", "uses_shared_renames": "",
            "source": "MegaCrit.Sts2.Core.Saves.Migrations/MigrationManager.cs:%d" % line_of(mm, r"SetMinimumSupportedVersion<%s>" % st),
        })
    rows.sort(key=lambda r: (r["save_type"], r["class"] == "(汇总)", r["from_version"] if r["from_version"] != "" else 0))
    write("ch07_save_migrations.csv", rows)
    return rows


# ---------------------------------------------------------------- 4. 遥测字段
RUN_NOTES = {
    "BuildId": "ReleaseInfo.Version，如 v0.111.1",
    "PlayerId": "progress.save 里的 UniqueId：7 位随机大写字母数字，不是 Steam ID",
    "Character": "本机玩家角色（只写 Entry，不带 CHARACTER. 前缀）",
    "Win": "是否胜利",
    "NumPlayers": "本局人数",
    "Team": "多人时全队角色列表；单人为空",
    "BuildType": "Steam 分支名（PlatformBranch）",
    "Ascension": "进阶等级",
    "TotalPlaytime": "存档累计游戏时长",
    "TotalWinRate": "存档总胜场/总局数",
    "NumReloads": "本局读档（SL）次数",
    "RunPlaytime": "胜利用 WinTime，否则 RunTime",
    "FloorReached": "经过的地图点数",
    "KilledByEncounter": "失败且最后一个房间是战斗时记录遭遇 ID",
    "CardChoices": "每次选卡：picked/skipped（卡牌 Entry）",
    "CampfireUpgrades": "营火升级的卡",
    "EventChoices": "普通事件选项（id/act/picked，picked 取本地化 key 的选项段）",
    "AncientChoices": "Ancient 事件的 picked/skipped",
    "RelicBuys": "商店买的遗物",
    "PotionBuys": "商店买的药水",
    "ColorlessBuys": "商店买的无色卡",
    "PotionDiscards": "丢弃的药水",
    "Encounters": "每场战斗 id/damage(0-100 钳制)/turns",
    "ActWins": "每幕 act/win",
    "Deck": "终局牌组（卡牌 Entry 列表）",
    "Relics": "终局遗物（Entry 列表）",
}


def camel(s: str) -> str:
    return s[:1].lower() + s[1:]


def metrics():
    rows = []
    base = SRC / "MegaCrit.Sts2.Core.Runs.Metrics"
    mu = (base / "MetricUtilities.cs").read_text(encoding="utf-8")
    eps = dict(re.findall(r'private const string _metrics(\w+)DataEndpoint = "([^"]+)"', mu))
    t = (base / "RunMetrics.cs").read_text(encoding="utf-8")
    for ty, name in re.findall(r"public (?:required )?([\w<>\?]+) (\w+) \{ get; init; \}", t):
        rows.append(dict(channel="run_metrics（每局结束 PUT）", endpoint=eps.get("Run", ""), record="RunMetrics",
                         field=name, json_name=camel(name), type=ty, note=RUN_NOTES.get(name, ""),
                         source="%s:%d" % (rel(base / "RunMetrics.cs"), line_of(t, r" %s \{ get" % name))))
    for sub in ["CardChoiceMetric", "EncounterMetric", "EventChoiceMetric", "AncientMetric", "ActWinMetric"]:
        p = base / (sub + ".cs")
        st = p.read_text(encoding="utf-8")
        for ty, name in re.findall(r"public readonly ([\w<>\?]+) (\w+);", st):
            rows.append(dict(channel="run_metrics 子结构", endpoint=eps.get("Run", ""), record=sub, field=name, json_name=name,
                             type=ty, note="", source="%s:%d" % (rel(p), line_of(st, r"public readonly [\w<>\?]+ %s;" % name))))
    for rec, p, ch, ep in [
        ("SettingsDataMetric", base / "SettingsDataMetric.cs", "settings（第 5 局结束时只传一次）", eps.get("Settings", "")),
        ("EpochMetric", SRC / "MegaCrit.Sts2.Core.Timeline" / "EpochMetric.cs", "epoch（揭示纪元时）", eps.get("Epoch", "")),
        ("AchievementMetric", SRC / "MegaCrit.Sts2.Core.Achievements" / "AchievementMetric.cs", "achievement（解锁成就时；当前成就未开放）", eps.get("Achievement", "")),
        ("FeedbackData", SRC / "MegaCrit.Sts2.Core.Nodes.Screens.FeedbackScreen" / "FeedbackData.cs", "feedback（玩家主动提交反馈，multipart 附截图+日志 zip）", "https://feedback.sts2.megacrit.com/feedback"),
    ]:
        st = p.read_text(encoding="utf-8")
        for jn, ty, name in re.findall(r'\[JsonPropertyName\("(\w+)"\)\]\s*(?:\[[^\]]+\]\s*)*public (?:required )?([\w<>\?]+) (\w+)', st):
            rows.append(dict(channel=ch, endpoint=ep, record=rec, field=name, json_name=jn, type=ty, note="",
                             source="%s:%d" % (rel(p), line_of(st, r'JsonPropertyName\("%s"\)' % jn))))
    sp = SRC / "MegaCrit.Sts2.Core.Debug" / "SentryService.cs"
    st = sp.read_text(encoding="utf-8")
    seen = set()
    for kind, key in re.findall(r'scope\.Set(Tag|Extra)\("([\w\.]+)"', st):
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(channel="sentry 上下文（崩溃/异常时附带；DSN 已打码不列）", endpoint="<Sentry DSN，见 project.binary sentry/config/dsn，已打码>",
                         record="Scope." + kind, field=key, json_name=key, type=kind.lower(), note="",
                         source="%s:%d" % (rel(sp), line_of(st, r'scope\.Set%s\("%s"' % (kind, re.escape(key))))))
    cp = SRC / "MegaCrit.Sts2.Core.Multiplayer.Game" / "ChecksumTracker.cs"
    ct = cp.read_text(encoding="utf-8")
    for kind, key in re.findall(r'scope\.Set(Tag|Extra)\("([\w\.]+)"', ct):
        rows.append(dict(channel="sentry 联机不同步上报（附 local/remote/previous state 的 gz 文本）", endpoint="<Sentry DSN，已打码>",
                         record="Scope." + kind, field=key, json_name=key, type=kind.lower(), note="",
                         source="%s:%d" % (rel(cp), line_of(ct, r'scope\.Set%s\("%s"' % (kind, re.escape(key))))))
    write("ch07_metrics_fields.csv", rows)
    return rows


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("%-36s %4d rows" % (name, len(rows)))


if __name__ == "__main__":
    dev_console()
    messages()
    migrations()
    metrics()
