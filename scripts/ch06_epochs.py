# -*- coding: utf-8 -*-
"""第 06 章：从反编译源码抽 57 个纪元（Epoch）→ data/csv/ch06_epochs.csv

用法：python -I -X utf8 scripts/ch06_epochs.py
解锁条件来自 ProgressSaveManager.cs / EpochModel.AgnosticUnlocks 的人工对照（见 TRIGGERS）。
"""
import csv, json, os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'csharp', 'sts2_src')
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization', 'zhs')
CSV = os.path.join(ROOT, 'data', 'csv')

def load_json(name):
    with open(os.path.join(LOC, name), encoding='utf-8') as f:
        return json.load(f)

def load_names(fn):
    out = {}
    with open(os.path.join(CSV, fn), encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            out[r['cls']] = r['name_zh']
    return out

ep_loc = load_json('epochs.json')
era_loc = load_json('eras.json')
cards = load_names('cards.csv'); relics = load_names('relics.csv')
potions = load_names('potions.csv'); events = load_names('events.csv')

# EpochEra 枚举值
era_vals = {}
for m in re.finditer(r'(\w+) = (-?\d+)', open(os.path.join(SRC, 'MegaCrit.Sts2.Core.Timeline', 'EpochEra.cs'), encoding='utf-8').read()):
    era_vals[m.group(1)] = int(m.group(2))

# Story 章节顺序
story_of = {}
for p in glob.glob(os.path.join(SRC, 'MegaCrit.Sts2.Core.Timeline.Stories', '*.cs')):
    t = open(p, encoding='utf-8').read()
    sid = re.search(r'Id => "(\w+)"', t).group(1)
    for i, cls in enumerate(re.findall(r'EpochModel\.Get<(\w+)>\(\)', t)):
        story_of[cls] = (sid, i + 1)

# 积分条 18 个通用解锁
em = open(os.path.join(SRC, 'MegaCrit.Sts2.Core.Timeline', 'EpochModel.cs'), encoding='utf-8').read()
score = {}
for i, m in enumerate(re.finditer(r'new AgnosticUnlock\(GetId<(\w+)>\(\), (\d+)\)', em)):
    score[m.group(1)] = (i + 1, int(m.group(2)))

PSM = 'MegaCrit.Sts2.Core.Saves.Managers/ProgressSaveManager.cs'
CHARS = ['Ironclad', 'Silent', 'Regent', 'Defect', 'Necrobinder']
TRIG = {}
TRIG['NeowEpoch'] = ('局后', '任意一局结束（胜/负/放弃，仅标准模式）；或首次打开时间线界面时直接补给', PSM + ':343；MegaCrit.Sts2.Core.Nodes.Screens.Timeline/NTimelineScreen.cs:450')
TRIG['Silent1Epoch'] = ('连锁', '揭示「涅奥」纪元时直接置为已获得（ObtainedNoSlot）', 'MegaCrit.Sts2.Core.Timeline.Epochs/NeowEpoch.cs:QueueUnlocks')
TRIG['Regent1Epoch'] = ('局后', '用静默猎手打完一局（任意结局）', PSM + ':368')
TRIG['Necrobinder1Epoch'] = ('局后', '用储君打完一局（任意结局）', PSM + ':368')
TRIG['Defect1Epoch'] = ('局后', '用亡灵契约师打完一局（任意结局）', PSM + ':368')
for c in CHARS:
    TRIG[c + '2Epoch'] = ('局中', f'用该角色首次击败第 1 幕 Boss', PSM + ':564-597（act=0）')
    TRIG[c + '3Epoch'] = ('局中', f'用该角色首次击败第 2 幕 Boss', PSM + ':564-597（act=1）')
    TRIG[c + '4Epoch'] = ('局中', f'用该角色首次击败第 3 幕 Boss', PSM + ':564-597（act=2）')
    TRIG[c + '5Epoch'] = ('局中', f'该角色累计击败精英 15 次（跨局累计）', PSM + ':411-482')
    TRIG[c + '6Epoch'] = ('局中', f'该角色累计击败 Boss 15 次（跨局累计）', PSM + ':488-558')
    TRIG[c + '7Epoch'] = ('局后', f'用该角色在进阶 1 获胜', PSM + ':393-405')
TRIG['CustomAndSeedsEpoch'] = ('局后', '本局获胜且全角色累计胜场 ≥3', PSM + ':376-387')
TRIG['DailyRunEpoch'] = ('局后', '本局获胜，且 CharacterStats 条目数 ≥5（文案是「所有角色都玩过」；条目在单人选角切换角色时就会创建，StartRunLobby.cs:519）', PSM + ':346-350')
TRIG['OrobasEpoch'] = ('局后', '任意一局结束时 CharacterStats 条目数 ≥5（文案是「以所有角色完成一局」；条目在单人选角切换角色时就会创建，StartRunLobby.cs:519）', PSM + ':351-354')
TRIG['DarvEpoch'] = ('局后', '遇见过除达弗以外的全部先古之民（AncientStats 有记录）', PSM + ':355-358')
for cls, (idx, th) in score.items():
    TRIG[cls] = ('积分条', f'积分条第 {idx} 档：累计分数 ≥{th}', 'MegaCrit.Sts2.Core.Timeline/EpochModel.cs:AgnosticUnlocks')

GATE = {
    'NeowEpoch': '密林/暗港的先古之民池加入涅奥（开局祝福）',
    'OrobasEpoch': '巢穴（第 2 幕）先古之民池加入欧洛巴斯',
    'DarvEpoch': '共享先古之民池加入达弗',
    'UnderdocksEpoch': '第 1 幕可选暗港（Underdocks.IsUnlocked）',
    'CustomAndSeedsEpoch': '主菜单「自定义」按钮可用（含种子）',
    'DailyRunEpoch': '主菜单「每日挑战」按钮可用',
    'Act2BEpoch': '无（占位：抢先体验期间揭晓的第 2 幕 B 面）',
    'Act3BEpoch': '无（占位：抢先体验期间揭晓的第 3 幕 B 面）',
}
for c in CHARS:
    GATE[c + '1Epoch'] = '角色可选（UnlockState.Characters）'
    GATE[c + '4Epoch'] = '该角色专属药水 3 瓶进池；同时开放该角色单人进阶选择（StartRunLobby.cs:520-545 IsAscensionEpochRevealed）'

rows = []
parent = {}
info = {}
for p in sorted(glob.glob(os.path.join(SRC, 'MegaCrit.Sts2.Core.Timeline.Epochs', '*.cs'))):
    cls = os.path.basename(p)[:-3]
    t = open(p, encoding='utf-8').read()
    eid = re.search(r'Id => "(\w+)"', t).group(1)
    era = re.search(r'EpochEra\.(\w+)', t).group(1)
    pos = int(re.search(r'EraPosition => (\d+)', t).group(1))
    sid = re.search(r'StoryId => "(\w+)"', t)
    exp_m = re.search(r'GetTimelineExpansion\(\)\s*\{\s*return new EpochModel\[\d+\]\s*\{(.*?)\};', t, re.S)
    exp = re.findall(r'GetId<(\w+)>', exp_m.group(1)) if exp_m else []
    for ch in exp:
        parent.setdefault(ch, []).append(cls)
    kinds, content, content_cls = [], [], []
    for kind, pat, names in (('卡牌', r'ModelDb\.Card<(\w+)>', cards), ('遗物', r'ModelDb\.Relic<(\w+)>', relics),
                             ('药水', r'ModelDb\.Potion<(\w+)>', potions), ('事件', r'ModelDb\.Event<(\w+)>', events)):
        found = re.findall(pat, t)
        if found:
            kinds.append(kind)
            content.append(kind + '：' + '、'.join(names.get(x, x) for x in found))
            content_cls.append(' '.join(found))
    m = re.search(r'QueueCharacterUnlock<(\w+)>', t)
    if m:
        kinds.append('角色'); content.append('角色：' + m.group(1)); content_cls.append(m.group(1))
    if 'QueueMiscUnlock' in t and not content:
        kinds.append('其他')
        txt = ep_loc.get(eid + '.unlock') or ep_loc.get(eid + '.unlockText', '')
        content.append(re.sub(r'\[/?\w+\]', '', txt))
    ov = re.findall(r'ObtainEpochOverride\(EpochModel\.GetId<(\w+)>\(\), EpochState\.(\w+)\)', t)
    if ov:
        content.append('连带获得：' + '、'.join(f'{a}({b})' for a, b in ov))
    info[cls] = dict(eid=eid, era=era, pos=pos, sid=sid.group(1) if sid else '', exp=exp,
                     kinds='+'.join(kinds), content='；'.join(content), content_cls=' | '.join(content_cls))

def strip(s):
    return re.sub(r'\[/?\w+\]', '', s or '').replace('\n', ' ')

def unlock_info(eid):
    s = ep_loc.get(eid + '.unlockInfo', '')
    s = re.sub(r'\{IsRevealed:([^|}]*)\|([^}]*)\}', r'\2', s)
    return strip(s)

for cls, d in info.items():
    era_key = re.sub(r'\d+$', '', d['era']).upper() + '0'
    st = story_of.get(cls, ('', ''))
    tr = TRIG.get(cls, ('?', '?', '?'))
    rows.append({
        'epoch_id': d['eid'], 'cls': cls,
        'title_zh': strip(ep_loc.get(d['eid'] + '.title', '')),
        'story': st[0], 'story_zh': ep_loc.get('STORY_' + st[0], '') if st[0] else '', 'chapter': st[1],
        'era': d['era'], 'era_name_zh': era_loc.get(era_key + '.name', ''), 'era_year_zh': era_loc.get(era_key + '.year', ''),
        'era_value': era_vals.get(d['era'], ''), 'era_row': d['pos'],
        'trigger_type': tr[0], 'trigger_condition': tr[1], 'trigger_source': tr[2],
        'unlock_info_zh': unlock_info(d['eid']),
        'slot_opened_by': '、'.join(parent.get(cls, [])) or ('（时间线初始）' if cls == 'NeowEpoch' else ''),
        'expands_slots': '、'.join(d['exp']),
        'unlock_kind': d['kinds'], 'unlock_content': d['content'], 'unlock_content_cls': d['content_cls'],
        'gate_effect': GATE.get(cls, ''),
        'score_order': score.get(cls, ('', ''))[0], 'score_threshold': score.get(cls, ('', ''))[1],
    })

rows.sort(key=lambda r: (r['era_value'], r['era_row']))
out = os.path.join(CSV, 'ch06_epochs.csv')
with open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print('wrote', out, len(rows))
from collections import Counter
print(Counter(r['trigger_type'] for r in rows))
print(Counter(r['unlock_kind'] for r in rows))
missing = [r['cls'] for r in rows if not r['slot_opened_by']]
print('no parent:', missing)
