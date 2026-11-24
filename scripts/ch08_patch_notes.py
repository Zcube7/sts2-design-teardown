"""第 08 章：补丁说明结构化 + 统计。

读 data/pck_text/localization/eng/patch_notes/*.md（127 份）与 zhs/patch_notes/*.md，
把每条补丁条目拆成一行，识别类型 / 子类 / 动作 / 提到的实体，输出：

  data/csv/ch08_patch_notes_entries.csv   每条条目一行
  data/csv/ch08_patch_timeline.csv        每份补丁一行（阶段、各类型计数、增删改计数、导语）
  data/csv/ch08_patch_monthly.csv         按月 x 类型计数
  data/csv/ch08_patch_top_entities.csv    实体被提及次数（全部 / BALANCE 段 / 增删改）

用法:  python -I -X utf8 scripts/ch08_patch_notes.py
实体词典来自 eng 本地化（cards/relics/potions/powers/monsters/encounters/events/ancients/
enchantments/afflictions/modifiers/orbs/characters/acts 的 title/name），另用「Xxx card/relic/...」
句式补抓已删除内容的旧名（entity_type 记作 legacy_<类>）。
"""
import csv, json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC = os.path.join(ROOT, 'data', 'pck_text', 'localization')
OUT = os.path.join(ROOT, 'data', 'csv')

# ---------------------------------------------------------------- 阶段划分（依据见正文 08 章 1 节）
PHASES = [
    ('2023-02-09', '2023-09-15', 'P0_unity_playtest', 'Unity 版内测'),
    ('2024-04-12', '2024-09-06', 'P1_godot_restart', 'Godot 重启内测'),
    ('2024-09-12', '2025-01-23', 'P2_structured', '结构化周更（游戏内补丁页上线）'),
    ('2025-01-30', '2026-02-26', 'P3_multiplayer_to_ea', '联机上线 → EA 前最后一周'),
    ('2026-03-12', '2026-11-13', 'P4_early_access', '抢先体验（EA）后：beta 分支 + 主分支大更新'),
]


def phase_of(date):
    for a, b, k, _ in PHASES:
        if a <= date <= b:
            return k
    return 'unknown'


# ---------------------------------------------------------------- 段落标题 → 规范类型
SECTION_RULES = [
    (r'KNOWN ISSUES', 'KNOWN_ISSUE'),
    (r'BUG ?FIX|LATEST BETA FIXES|^FIXES', 'BUGFIX'),
    (r'CONTENT ?(&|AND) ?BALANCE', 'CONTENT_BALANCE'),
    (r'^CONTENT', 'CONTENT'),
    (r'BALANCE|^GAMEPLAY|ENEMY CHANGES', 'BALANCE'),
    (r'^ART|ANIMATION|VISUAL', 'ART'),
    (r'USER INTER|USER EXPER|^UX|^UI|QUALITY OF LIFE|EFFECTS', 'UI_UX'),
    (r'WORDING|WRITING', 'WORDING'),
    (r'AUDIO|SOUND|MUSIC', 'AUDIO'),
    (r'PERF', 'PERFORMANCE'),
    (r'MODDING|WORKSHOP', 'MODDING'),
    (r'LOCALI[SZ]ATION|TRANSLATION', 'LOCALIZATION'),
    (r'FEATURE|BESTIARY|RNG REWORK', 'FEATURE'),
    (r'^DEBUG', 'DEBUG'),
    (r'^PATCH NOTES$', 'GENERAL'),
]
ZH_SECTION_RULES = [
    (r'已知问题', 'KNOWN_ISSUE'), (r'修复|漏洞', 'BUGFIX'), (r'内容.*平衡', 'CONTENT_BALANCE'),
    (r'^内容', 'CONTENT'), (r'平衡', 'BALANCE'), (r'美术|动画', 'ART'), (r'界面|体验', 'UI_UX'),
    (r'文本|措辞', 'WORDING'), (r'音频|音效', 'AUDIO'), (r'性能', 'PERFORMANCE'), (r'模组|Mod', 'MODDING'),
    (r'本地化', 'LOCALIZATION'),
]
# 2023-02 两份用「TYPE: 正文」行内前缀
INLINE_PREFIX = re.compile(r'^\s*-?\s*(BALANCE|BUG ?FIX|GAMEPLAY|UX|WORDING|DEBUG|PERF|CONTENT|ART|WIP)\s*:\s+(.*)$')
INLINE_MAP = {'BALANCE': 'BALANCE', 'BUGFIX': 'BUGFIX', 'BUG FIX': 'BUGFIX', 'GAMEPLAY': 'BALANCE', 'UX': 'UI_UX',
              'WORDING': 'WORDING', 'DEBUG': 'DEBUG', 'PERF': 'PERFORMANCE', 'CONTENT': 'CONTENT', 'ART': 'ART',
              'WIP': 'GENERAL'}

MARKUP = re.compile(r'\[/?(?:blue|b|i|gold|red|green|purple|orange|sine|jitter|s|u|center)\]|\*\*|~~|__')


def strip_markup(s):
    return MARKUP.sub('', s).strip()


def classify_section(text, lang):
    t = strip_markup(text).strip().rstrip(':').strip().rstrip(':').strip()
    t = re.sub(r'^#+\s*', '', t)
    if lang == 'zhs':
        t = t.rstrip('：')
        for rx, typ in ZH_SECTION_RULES:
            if re.search(rx, t):
                return typ
        return None
    up = t.upper()
    for rx, typ in SECTION_RULES:
        if re.search(rx, up):
            return typ
    return None


SKIP_LINE = re.compile(r'(REDACTED|^\s*\*\*Build links?:?\*\*|^\s*Build( link)?s?:|^\s*Link:|<@&\d+>|^\s*-?\s*\[(Windows|Linux|Mac)\])', re.I)
BULLET = re.compile(r'^(\s*)[-*•]\s+(.*)$')

# ---------------------------------------------------------------- 动作分类（条目开头动词）
ACTIONS = [
    ('REVERT', r'^(reverted|revert|rolled back|undid)\b|\brevert(ed)? (back )?to\b'),
    ('DEPRECATE', r'^(deprecated|temporarily deprecated|removed|remove|cut|deleted|retired|saying goodbye)\b'),
    ('ADD', r'^(added|add|implemented|implement|introduced|introducing|new\b|re-?added|reintroduced|brought back|bring back|returning)'),
    ('RENAME', r'^renamed\b|\brenamed to\b'),
    ('REWORK', r'^(reworked|rework|redesigned|overhauled|revamped|completely reworked)\b|\b(reworked|completely reworked|redesigned)\b'),
    ('BUFF', r'^buffed\b'),
    ('NERF', r'^nerfed\b'),
    ('FIX', r'^(fixed|fix|fixes|resolved)\b'),
    ('CHANGE', r'^(changed|change|updated|update|adjusted|tweaked|lowered|raised|increased|decreased|reduced|swapped|moved|now\b|made\b)'),
]
ZH_ACTIONS = [('REVERT', r'回调|还原|恢复至'), ('DEPRECATE', r'^(删除|移除|弃用)'), ('ADD', r'^(新增|添加|加入)'),
              ('REWORK', r'重做'), ('BUFF', r'加强'), ('NERF', r'削弱'), ('FIX', r'^修复'), ('CHANGE', r'^(调整|修改|改动)')]


def classify_action(text, lang):
    t = strip_markup(text).lstrip('-* ').strip()
    rules = ZH_ACTIONS if lang == 'zhs' else ACTIONS
    flags = 0 if lang == 'zhs' else re.I
    for name, rx in rules:
        if re.search(rx, t, flags):
            return name
    return 'OTHER'


# ---------------------------------------------------------------- 实体词典
def load_entities():
    """name -> set of (etype, id)"""
    d = collections.defaultdict(set)
    spec = [('cards', 'title', 'card'), ('relics', 'title', 'relic'), ('potions', 'title', 'potion'),
            ('powers', 'title', 'power'), ('monsters', 'name', 'monster'), ('encounters', 'title', 'encounter'),
            ('events', 'title', 'event'), ('ancients', 'title', 'ancient'), ('enchantments', 'title', 'enchantment'),
            ('afflictions', 'title', 'affliction'), ('modifiers', 'title', 'modifier'), ('orbs', 'title', 'orb'),
            ('characters', 'title', 'character'), ('acts', 'title', 'act'), ('ascension', 'title', 'ascension')]
    for fn, suf, et in spec:
        js = json.load(open(os.path.join(LOC, 'eng', fn + '.json'), encoding='utf-8'))
        for k, v in js.items():
            parts = k.split('.')
            if len(parts) != 2 or parts[1] != suf:
                continue
            ident = parts[0]
            if ident.startswith('MOCK_') or ident in ('ERROR', 'PROCEED', 'DEPRECATED_ACT', 'EMPTY_SLOT'):
                continue
            name = strip_markup(re.sub(r'\{[^}]*\}', '', v)).strip()
            if len(name) < 3 or name in ENTITY_STOP:
                continue
            d[name].add((et, ident))
            if name.startswith('The ') and len(name) > 7:
                d[name[4:]].add((et, ident))
    # 本地化里同名的「力量/卡」等关键词式能力会淹没统计，单独标记
    return d


KEYWORD_POWERS = {'Strength', 'Dexterity', 'Vulnerable', 'Weak', 'Frail', 'Poison', 'Doom', 'Focus', 'Vigor',
                  'Artifact', 'Intangible', 'Plating', 'Thorns', 'Block', 'Energy', 'Stars', 'Forge', 'Summon',
                  'Souls', 'Soul', 'Shiv', 'Shivs', 'Burn', 'Wound', 'Wounds', 'Dazed', 'Slimed', 'Void', 'Regen',
                  'Ritual', 'Metallicize', 'Barricade', 'Buffer', 'Slow', 'Strength Down', 'Osty', 'Sly', 'Retain',
                  'Exhaust', 'Ethereal', 'Innate', 'Unplayable', 'Eternal', 'Curse', 'Curses', 'Status'}

LEGACY_RX = re.compile(
    r"(?:\[b\])?([A-Z][A-Za-z'’!\-]+(?:\s+(?:of|the|a|in|to|for|from|and|[A-Z][A-Za-z'’!\-]+))*)(?:\[/b\])?\s+"
    r"(card|cards|relic|relics|potion|potions|event|encounter|enemy|elite|boss|blessing|power|enchantment|affliction|ascension)\b")
LEGACY_TYPE = {'card': 'card', 'cards': 'card', 'relic': 'relic', 'relics': 'relic', 'potion': 'potion',
               'potions': 'potion', 'event': 'event', 'encounter': 'encounter', 'enemy': 'monster', 'elite': 'monster',
               'boss': 'monster', 'blessing': 'blessing', 'power': 'power', 'enchantment': 'enchantment',
               'affliction': 'affliction', 'ascension': 'ascension'}
LEGACY_STOP = {'New', 'Added', 'Reworked', 'Deprecated', 'Nerfed', 'Buffed', 'Changed', 'Removed', 'Fixed', 'The',
               'This', 'Each', 'Every', 'Any', 'All', 'Some', 'Many', 'Most', 'Other', 'Boss', 'Elite', 'Rare',
               'Common', 'Uncommon', 'Ancient', 'Legendary', 'Starter', 'Shop', 'Event', 'Status', 'Curse',
               'Colorless', 'Basic', 'Attack', 'Skill', 'Power', 'Act', 'Re-added', 'Reintroduced', 'Renamed',
               'Several', 'Various', 'Multiple', 'Two', 'Three', 'A', 'An', 'Ironclad', 'Silent', 'Defect',
               'Regent', 'Necrobinder', 'Upgraded', 'Random', 'Quest', 'Token', 'Next', 'First', 'Last',
               'Updated', 'Improved', 'Adjusted', 'Tweaked', 'Implemented', 'Resized', 'Modified', 'Moved',
               'Lowered', 'Raised', 'Increased', 'Decreased', 'Reduced', 'Swapped', 'Replaced', 'Made', 'Gave',
               'Set', 'Allowed', 'Enabled', 'Disabled', 'Polished', 'Cleaned', 'Redesigned', 'Overhauled',
               'Revamped', 'Brought', 'Returning', 'Old', 'Unique', 'Specific', 'Certain', 'Starting', 'Enemy',
               'Monster', 'More', 'Less', 'Missing', 'Temporary', 'Placeholder', 'Beta', 'Multiplayer', 'Their',
               'Your', 'His', 'Her', 'Its', 'Both', 'When', 'If', 'Whenever', 'Unplayable', 'Ethereal', 'Exhaust'}
# 本地化标题里的「通用词」：会把正文里的普通单词误认成实体
ENTITY_STOP = {'Deprecated', 'Updated', 'Error', 'Proceed', 'Random', 'Status', 'Curse', 'Token', 'Event'}


class Matcher:
    def __init__(self, ents):
        self.ents = ents
        names = sorted(ents, key=len, reverse=True)
        self.rx = re.compile(r"(?<![A-Za-z'’])(" + '|'.join(re.escape(n) for n in names) + r")(?![A-Za-z])")

    def find(self, text, sub=''):
        plain = strip_markup(text)
        hits = []
        for m in self.rx.finditer(plain):
            name = m.group(1)
            types = sorted({et for et, _ in self.ents[name]})
            ids = sorted({i for _, i in self.ents[name]})
            hits.append((name, '|'.join(types), '|'.join(ids), m.start()))
        known = {h[0] for h in hits}
        for m in LEGACY_RX.finditer(text):
            nm = strip_markup(m.group(1)).strip()
            first = nm.split()[0]
            if first in LEGACY_STOP:
                nm = ' '.join(nm.split()[1:])
            if not nm or nm in known or nm.split()[0] in LEGACY_STOP or len(nm) < 3:
                continue
            if any(nm in k or k in nm for k in known):
                continue
            pos = plain.find(nm)
            hits.append((nm, 'legacy_' + LEGACY_TYPE[m.group(2)], '', pos if pos >= 0 else 10 ** 6))
            known.add(nm)
        # 2024-09 之后的补丁把实体名加粗：[b]Doormaker[/b]。词典里没有的加粗名 = 已删除/改名的旧内容
        for m in BOLD_RX.finditer(text):
            nm = strip_markup(m.group(1)).strip(' :.!')
            if (not nm or nm in known or len(nm) < 3 or len(nm) > 40 or nm.upper() == nm and len(nm) > 4
                    or nm.split()[0] in LEGACY_STOP or any(nm in k or k in nm for k in known)):
                continue
            after = text[m.end():m.end() + 14].lower()
            et = next((v for k, v in LEGACY_TYPE.items() if after.strip().startswith(k)), None)
            if et is None:
                et = SUB_TYPE.get(sub, 'unknown')
            pos = plain.find(nm)
            hits.append((nm, 'legacy_' + et, '', pos if pos >= 0 else 10 ** 6))
            known.add(nm)
        hits.sort(key=lambda h: h[3])
        return hits


BOLD_RX = re.compile(r'\[b\]([^\[]{2,60}?)\[/b\]')
SUB_TYPE = {'Ironclad': 'card', 'Silent': 'card', 'Defect': 'card', 'Regent': 'card', 'Necrobinder': 'card',
            'Colorless Cards': 'card', 'Colorless': 'card', 'Multiplayer': 'card', 'Enemies': 'monster',
            'Events': 'event', 'Potions & Relics': 'relic', 'Relics': 'relic', 'Potions': 'potion',
            'Ancients': 'ancient_option', 'Ancient': 'ancient_option'}


# ---------------------------------------------------------------- 解析一份补丁
def parse_file(path, lang):
    fn = os.path.basename(path)
    date = fn[:10].replace('_', '-')
    lines = open(path, encoding='utf-8').read().splitlines()
    entries = []
    section_raw, section, sub = '', 'NARRATIVE', ''
    cur = None
    seen_section = False

    def flush():
        nonlocal cur
        if cur and cur['text'].strip():
            entries.append(cur)
        cur = None

    for ln in lines:
        raw = ln.rstrip()
        if not raw.strip():
            if section == 'NARRATIVE' or (cur and cur.get('prose')):
                flush()
            continue
        if SKIP_LINE.search(raw):
            continue
        m_inline = INLINE_PREFIX.match(raw) if lang == 'eng' else None
        if m_inline:
            flush()
            typ = INLINE_MAP[m_inline.group(1).upper()]
            cur = dict(section_raw=m_inline.group(1), type=typ, sub=sub, text=m_inline.group(2), prose=False)
            seen_section = True
            continue
        bm = BULLET.match(raw)
        stripped = strip_markup(raw)
        # 标题判定：非列表、短、不以句号结尾
        is_marked = bool(re.match(r'^\s*(\[blue\]|\[b\]|\*\*|#)', raw))
        if not bm and len(stripped) <= 60 and not stripped.endswith('.') and (is_marked or not stripped.endswith('!')):
            typ = classify_section(raw.replace('!', ''), lang)
            if typ and (is_marked or stripped.upper() == stripped or stripped.endswith(':') or stripped.endswith('：')
                        or stripped in ('Patch Notes', 'Known Issues', 'Content', 'Bug Fixes')):
                flush()
                section_raw, section, sub = stripped.rstrip(':：'), typ, ''
                seen_section = True
                continue
            if (stripped.endswith(':') or stripped.endswith('：')) and len(stripped) <= 40 and seen_section:
                flush()
                sub = stripped.rstrip(':：').strip()
                continue
            if is_marked and seen_section and len(stripped) <= 50 and re.match(r'^\s*\[blue\]\[b\]', raw):
                # 自由命名的蓝色小标题（如「Doormaker Out, Aeonglass In」）：作为开发者说明段
                flush()
                section_raw, section, sub = stripped, 'DEV_COMMENTARY', ''
                continue
        if bm:
            indent = len(bm.group(1).replace('\t', '  '))
            body = bm.group(2).strip()
            # 有些补丁把「Added new cards:」的子项写成同级列表：父条目以冒号结尾时，
            # 后续不以动作动词开头的同级条目并入父条目
            pb = strip_markup(body)
            words = pb.split()
            verb_like = bool(words) and words[0].lower().endswith('ed') and len(words) > 2
            child_of_open = (indent == 0 and cur is not None and cur.get('open') and not cur.get('prose')
                             and classify_action(body, lang) == 'OTHER' and not verb_like
                             and not pb.rstrip().endswith(':'))
            if (indent == 0 and not child_of_open) or cur is None or cur.get('prose'):
                flush()
                typ = section if seen_section else 'NARRATIVE'
                cur = dict(section_raw=section_raw, type=typ, sub=sub, text=body, prose=False,
                           open=strip_markup(body).rstrip().endswith(':'))
            else:
                if indent > 0:
                    cur['open'] = False  # 已出现缩进子项：说明这份补丁用缩进表达层级，同级条目各自独立
                cur['text'] += ' | ' + body
            continue
        # 普通文本行
        if not seen_section or section in ('NARRATIVE', 'DEV_COMMENTARY'):
            # 叙述段落：同段合并
            if cur and cur.get('prose'):
                cur['text'] += ' ' + raw.strip()
            else:
                flush()
                cur = dict(section_raw=section_raw, type='NARRATIVE' if not seen_section else 'DEV_COMMENTARY',
                           sub=sub, text=raw.strip(), prose=True)
        else:
            # 段内无列表符号的条目（2023-04 那种一行一条），或段内的说明段落
            flush()
            prose = len(stripped) > 160 or stripped.count('. ') >= 2
            cur = dict(section_raw=section_raw, type='DEV_COMMENTARY' if prose else section, sub=sub,
                       text=raw.strip(), prose=prose)
            if not prose:
                flush()
    flush()
    for i, e in enumerate(entries):
        e.update(file=fn, date=date, lang=lang, idx=i, rollup=fn in ROLLUPS)
    return entries


# 主分支「合集」补丁：内容是此前 beta 补丁的重复汇总，实体频次统计时剔除，避免重复计数
ROLLUPS = {'2026_05_28.md', '2026_06_18.md', '2026_11_13.md'}


# ---------------------------------------------------------------- 改名抽取
_NAME = r"[A-Z][A-Za-z'’!.\-]*(?:\s+(?:of|the|a|in|to|for|from|and|on|[A-Z][A-Za-z'’!.\-]*|\(\w+\)))*"
RENAME_RXS = [
    re.compile(r"(?:^|\|\s*)(" + _NAME + r")\s*(?:->|→)\s*(" + _NAME + r")\s*(?=\(|$|\|)"),           # A -> B
    re.compile(r"[Rr]ename[ds]?\s+(?:the\s+)?(" + _NAME + r")\s+(?:card|relic|potion|event|power|enchantment|encounter|event/relic)?\s*to\s+(?:“|\")?(" + _NAME + r")"),
    re.compile(r"(" + _NAME + r")\s+\((?:now\s+called|now|renamed|also renamed|renamed to)\s+(" + _NAME + r")\)"),
    re.compile(r"(" + _NAME + r")\s+is now\s+(" + _NAME + r")(?= and| with|,|\.|$)"),
    re.compile(r"[Rr]eworked(?: and renamed)?\s+(?:the\s+)?(" + _NAME + r")\s+(?:card\s+|relic\s+|blessing\s+)?(?:into|->|→)\s+(?:a new\s+(?:boss,\s+)?)?(" + _NAME + r")"),
    re.compile(r"(" + _NAME + r")\s+reworked into\s+(" + _NAME + r")"),
    re.compile(r"[Rr]enamed\s+(?:to\s+)?(?:“|\")(" + _NAME + r")(?:”|\")"),
]
RENAME_BAD = re.compile(r"^(?:(?:Common|Uncommon|Rare|Legendary|Ancient|Basic|Status|Event|Token|Attack|Skill|Power|Shop|Boss|Elite|Normal|Weak|Strong|Old|New|Renamed)$|Act \d|(?:Skill|Power|Attack|Uncommon|Rare|Common) - )")
LEAD_VERB = re.compile(r"^(?:Renamed|Changed|Buffed|Nerfed|Reworked|Updated|Rename)\s+")


def extract_renames(entries):
    out = []
    for e in entries:
        if e['lang'] != 'eng' or e['rollup']:
            continue
        t = strip_markup(e['text'])
        low = t.lower()
        if not ('renam' in low or 'is now' in low or 'now called' in low or '(now ' in low or 'reworked into' in low
                or ' into ' in low or (e['date'] == '2023-05-05' and '->' in t)):
            continue
        if 'renam' not in low and '(now' not in low and 'into' not in low and 'is now' not in low:
            continue
        for i, rx in enumerate(RENAME_RXS):
            for m in rx.finditer(t):
                if i == 6:
                    continue
                a, b = LEAD_VERB.sub('', m.group(1).strip(' .')), m.group(2).strip(' .')
                if i == 0 and 'renam' not in low and e['date'] != '2023-05-05':
                    continue
                if any(ch.isdigit() for ch in a + b) or RENAME_BAD.match(a) or RENAME_BAD.match(b) or a == b:
                    continue
                if len(a) > 40 or len(b) > 40:
                    continue
                out.append(dict(date=e['date'], file=e['file'], type=e['type'], sub=e['sub'], old=a, new=b,
                                pattern=i, text=t[:240]))
    # 2023-05-05 的小写改名表单独处理（叙述段落里的 "lil toad -> nibbit"）
    seen = set(); res = []
    for r in out:
        k = (r['date'], r['old'].lower(), r['new'].lower())
        if k not in seen:
            seen.add(k); res.append(r)
    return res


def extract_rename_lists(files):
    """核查补丁（ch08 verify）：直接扫原文，补抓条目切分时丢掉的改名。
    条目切分会把「Renamed the following relics:」下的同级列表在某些项处切断（如以 -ed 结尾的
    「Used Notepad -> Stone Cracker」被当成新条目），导致整段列表漏抓。这里按原文行补抓：
      (1) 「Renamed the following …:」后紧跟的每个 A -> B 行；(2) 单行「Renamed A -> B / Renamed A to B」。"""
    out = []
    arrow = re.compile(r'\s*(?:->|→)\s*')
    for p, lang in files:
        fn = os.path.basename(p)
        if lang != 'eng' or fn in ROLLUPS:
            continue
        date = fn[:10].replace('_', '-')
        in_list, typ = False, 'NARRATIVE'
        for raw in open(p, encoding='utf-8').read().splitlines():
            s = strip_markup(raw).strip()
            if re.match(r'^\s*(\[blue\]|\*\*|#)', raw) and not BULLET.match(raw):
                t2 = classify_section(raw, lang)
                if t2:
                    typ = t2
            body = s.lstrip('-*• ').strip()
            if re.match(r'^renamed\b[^:]*:$', body, re.I):
                in_list = True
                continue
            if in_list:
                if not s:
                    in_list = False
                    continue
                parts = arrow.split(body)
                if (len(parts) == 2 and len(body) < 90 and not re.search(r'\d', body)
                        and not re.match(r'^(renamed|re-renamed|changed|buffed|nerfed|rarity)\b', body, re.I)):
                    out.append(dict(date=date, file=fn, type=typ, sub='', old=parts[0].strip(' .'),
                                    new=parts[1].strip(' .'), pattern='list', text=body[:240]))
                    continue
                in_list = False
            if re.search(r'\brenam', body, re.I) and 'executable' not in body.lower():
                m = (re.search(r"[Rr]enamed\s+(?:the\s+)?(?:\w+'s\s+)?(.+?)\s*(?:->|→)\s*(.+?)(?:\s+(?:and|to avoid|in order|which|but)\b.*|[.:]|$)", body)
                     or re.search(r"^(.+?)\s+(?:has been\s+)?renamed\s*(?:->|→|to)\s*(.+?)(?:\s+(?:and|to avoid|in order|which|but)\b.*|[.:]|$)", body)
                     or re.search(r"[Rr]enamed\s+(?:the\s+)?(.+?)\s+to\s+(.+?)(?:\s+(?:and|to avoid|in order|which|but|respectively)\b.*|[.:]|$)", body))
                if m:
                    a, b = m.group(1).strip(' "“”.,…'), m.group(2).strip(' "“”.,…')
                    a = re.sub(r'^(?:Changed|Reworked)\s+', '', a)
                    a = re.sub(r'(?:\s+card)?(?::\s*reworked)?\s+(?:and|&)$', '', a)
                    a = re.sub(r'\s+combat encounter$', '', a)
                    a = re.sub(r'\s+now\s.*$', '', a).strip(' "“”.,…')
                    b = re.sub(r'\s+to\s+(?:appease|avoid|reduce)\b.*$', '', b).strip(' "“”.,…')
                    a = re.sub(r'\s+(card|relic|potion|event|power|enchantment|monster|curse card|ancient|boss|intent|modifier|blessing|option|move)$', '', a, flags=re.I)
                    b = re.sub(r'\s+(card|relic|potion|event|power|enchantment|monster)$', '', b, flags=re.I)
                    if a and b and a.lower() != b.lower() and len(a) <= 50 and len(b) <= 50:
                        out.append(dict(date=date, file=fn, type=typ, sub='', old=a, new=b, pattern='line',
                                        text=body[:240]))
    return out


def main():
    ents = load_entities()
    matcher = Matcher(ents)
    files = []
    for lang in ('eng', 'zhs'):
        d = os.path.join(LOC, lang, 'patch_notes')
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.md'):
                files.append((os.path.join(d, fn), lang))
    all_entries = []
    for p, lang in files:
        all_entries.extend(parse_file(p, lang))
    for e in all_entries:
        e['action'] = classify_action(e['text'], e['lang'])
        e['phase'] = phase_of(e['date'])
        hits = matcher.find(e['text'], e['sub']) if e['lang'] == 'eng' else []
        e['hits'] = hits
    # ---------------- entries csv
    with open(os.path.join(OUT, 'ch08_patch_notes_entries.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['file', 'date', 'lang', 'phase', 'is_rollup', 'idx', 'type', 'section_raw', 'subcategory', 'action',
                    'text', 'entities', 'entity_types', 'entity_ids', 'n_entities'])
        for e in all_entries:
            hits = e['hits']
            w.writerow([e['file'], e['date'], e['lang'], e['phase'], int(e['rollup']), e['idx'], e['type'],
                        e['section_raw'], e['sub'],
                        e['action'], strip_markup(e['text'])[:3000], '; '.join(h[0] for h in hits),
                        '; '.join(h[1] for h in hits), '; '.join(h[2] for h in hits), len(hits)])
    eng = [e for e in all_entries if e['lang'] == 'eng']
    types = ['CONTENT', 'CONTENT_BALANCE', 'BALANCE', 'BUGFIX', 'ART', 'UI_UX', 'WORDING', 'AUDIO', 'PERFORMANCE',
             'MODDING', 'LOCALIZATION', 'FEATURE', 'DEBUG', 'KNOWN_ISSUE', 'GENERAL', 'NARRATIVE', 'DEV_COMMENTARY']
    acts = ['ADD', 'DEPRECATE', 'REWORK', 'RENAME', 'REVERT', 'BUFF', 'NERF', 'CHANGE', 'FIX', 'OTHER']
    # ---------------- timeline csv
    by_file = collections.OrderedDict()
    for e in eng:
        by_file.setdefault(e['file'], []).append(e)
    with open(os.path.join(OUT, 'ch08_patch_timeline.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['file', 'date', 'phase', 'is_rollup', 'n_lines', 'n_entries'] + ['t_' + t for t in types] +
                   ['a_' + a for a in acts] + ['chars_mentioned_in_content', 'headline'])
        for fn, es in by_file.items():
            n_lines = len(open(os.path.join(LOC, 'eng', 'patch_notes', fn), encoding='utf-8').read().splitlines())
            tc = collections.Counter(e['type'] for e in es)
            ac = collections.Counter(e['action'] for e in es if e['type'] not in ('NARRATIVE', 'DEV_COMMENTARY'))
            chars = collections.Counter(e['sub'] for e in es if e['type'] in ('CONTENT', 'CONTENT_BALANCE') and e['sub'])
            head = next((strip_markup(e['text']) for e in es if e['type'] == 'NARRATIVE' and len(e['text']) > 30), '')
            w.writerow([fn, es[0]['date'], es[0]['phase'], int(fn in ROLLUPS), n_lines, len(es)] +
                       [tc.get(t, 0) for t in types] +
                       [ac.get(a, 0) for a in acts] + ['; '.join(f'{k}:{v}' for k, v in chars.most_common(8)),
                                                       head[:300]])
    # ---------------- monthly csv
    by_month = collections.defaultdict(collections.Counter)
    files_month = collections.defaultdict(set)
    for e in eng:
        if e['rollup']:
            continue  # 合集补丁与 beta 补丁重复，按月统计时剔除
        mth = e['date'][:7]
        by_month[mth][e['type']] += 1
        by_month[mth]['ACT_' + e['action']] += 1 if e['type'] not in ('NARRATIVE', 'DEV_COMMENTARY') else 0
        files_month[mth].add(e['file'])
    with open(os.path.join(OUT, 'ch08_patch_monthly.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['month', 'n_patches', 'n_entries'] + types + ['act_' + a for a in acts])
        for mth in sorted(by_month):
            c = by_month[mth]
            n = sum(c[t] for t in types)
            w.writerow([mth, len(files_month[mth]), n] + [c[t] for t in types] + [c['ACT_' + a] for a in acts])
    # ---------------- top entities
    tot = collections.Counter(); bal = collections.Counter(); add = collections.Counter()
    dep = collections.Counter(); rew = collections.Counter(); buff = collections.Counter(); nerf = collections.Counter()
    etype = {}; first = {}; last = {}; files_hit = collections.defaultdict(set)
    subj_bal = collections.Counter(); bugfix = collections.Counter()
    for e in eng:
        if e['type'] in ('NARRATIVE',) or e['rollup']:
            continue
        if e['hits'] and e['type'] in ('BALANCE', 'CONTENT_BALANCE'):
            subj_bal[e['hits'][0][0]] += 1  # 条目的「主语」= 第一个被提到的实体
        for name, t, ids in {(h[0], h[1], h[2]) for h in e['hits']}:
            if e['type'] == 'BUGFIX':
                bugfix[name] += 1
            tot[name] += 1
            etype[name] = (t, ids)
            first.setdefault(name, e['date']); last[name] = e['date']
            files_hit[name].add(e['file'])
            if e['type'] in ('BALANCE', 'CONTENT_BALANCE'):
                bal[name] += 1
            if e['action'] == 'ADD': add[name] += 1
            if e['action'] == 'DEPRECATE': dep[name] += 1
            if e['action'] == 'REWORK': rew[name] += 1
            if e['action'] == 'BUFF': buff[name] += 1
            if e['action'] == 'NERF': nerf[name] += 1
    with open(os.path.join(OUT, 'ch08_patch_top_entities.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['name', 'entity_types', 'entity_ids', 'is_keyword_like', 'mentions_all', 'mentions_balance',
                    'balance_as_subject', 'mentions_bugfix', 'n_patches', 'add', 'deprecate', 'rework', 'buff', 'nerf',
                    'first_date', 'last_date'])
        for name, n in tot.most_common():
            t, ids = etype[name]
            kw = name in KEYWORD_POWERS or t.split('|')[0] in ('power', 'character', 'act', 'ascension')
            w.writerow([name, t, ids, kw, n, bal[name], subj_bal[name], bugfix[name], len(files_hit[name]), add[name],
                        dep[name], rew[name], buff[name], nerf[name], first[name], last[name]])
    # ---------------- renames
    rn = extract_renames(all_entries)
    for p2, lang in files:
        if p2.endswith('2023_05_05.md') and lang == 'eng':
            for ln in open(p2, encoding='utf-8').read().splitlines():
                m = re.match(r'^\s*-?\s*([a-z][a-z ]+?)\s*->\s*([a-z][a-z ]+?)\s*$', ln)
                if m:
                    rn.append(dict(date='2023-05-05', file='2023_05_05.md', type='NARRATIVE', sub='', old=m.group(1),
                                   new=m.group(2), pattern='lower', text=ln.strip()))
    # 核查补丁：补抓原文改名列表，与上面按 (日期, 新名) 及 (日期, 旧名) 去重
    n_before = len(rn)
    seen_new = {(r['date'], r['new'].lower().strip()) for r in rn}
    seen_old = {(r['date'], r['old'].lower().strip()) for r in rn}
    for r in extract_rename_lists(files):
        k1, k2 = (r['date'], r['new'].lower().strip()), (r['date'], r['old'].lower().strip())
        if k1 in seen_new or k2 in seen_old:
            continue
        seen_new.add(k1); seen_old.add(k2)
        rn.append(r)
    rn.sort(key=lambda r: r['date'])
    print('renames from entries', n_before, '+ raw-list supplement', len(rn) - n_before)
    with open(os.path.join(OUT, 'ch08_patch_renames.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['date', 'file', 'type', 'subcategory', 'old_name', 'new_name', 'new_in_current_loc', 'pattern', 'source_text'])
        for r in rn:
            w.writerow([r['date'], r['file'], r['type'], r['sub'], r['old'], r['new'], r['new'] in ents or
                        r['new'].replace('The ', '') in ents, r['pattern'], r['text']])
    print('renames', len(rn))
    # ---------------- 控制台摘要
    print('files', len(files), 'entries', len(all_entries), 'eng', len(eng))
    print('type counts', collections.Counter(e['type'] for e in eng).most_common())
    print('action counts', collections.Counter(e['action'] for e in eng if e['type'] not in ('NARRATIVE', 'DEV_COMMENTARY')).most_common())
    print('with entities', sum(1 for e in eng if e['hits']))


if __name__ == '__main__':
    main()
