"""第 08 章：美术 / 音频 / 动画资源清单（只统计路径与体积，不导出任何资源）。

输入
  data/pck_index.csv                       PCK 全量目录（path/ext/size/offset/md5）
  游戏目录 SlayTheSpire2.pck                只读；仅在内存里读取 *.import 文本（导入映射元数据，不是美术）
  data/pck_text/images/atlases/*.tpsheet   TexturePacker 图集清单（文本）
  data/pck_text/scenes/creature_visuals/*.tscn + animations/**/_skel_data.tres（文本）
  data/csv/{cards,relics,potions,powers,monsters,encounters,events,enchantments,orbs,characters,modifiers}.csv

输出
  data/csv/ch08_asset_catalog.csv          按类别汇总：数量、体积、路径规律、代码出处
  data/csv/ch08_asset_paths_by_entity.csv  卡/遗物/药水/能力/怪物/事件… id → 资源路径（是否存在、最终走哪条回退）
  data/csv/ch08_import_map.csv             源路径 → .godot/imported 导入物（importer、格式、体积）
  data/csv/ch08_shaders.csv                全部 .gdshader / .gdshaderinc / 着色器 .tres

用法:  python -I -X utf8 scripts/ch08_assets.py
"""
import csv, collections, glob, hashlib, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCK = r'C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck'
TXT = os.path.join(ROOT, 'data', 'pck_text')
CSV = os.path.join(ROOT, 'data', 'csv')

# ------------------------------------------------------------------ PCK 目录 + .import 元数据
idx = {r['path']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'pck_index.csv'), encoding='utf-8'))}


def read_imports():
    """只读 *.import（几百字节的文本元数据），返回 src -> dict(importer,type,dests)"""
    out = {}
    with open(PCK, 'rb') as f:
        for p, r in idx.items():
            if not p.endswith('.import'):
                continue
            f.seek(int(r['offset']))
            data = f.read(int(r['size']))
            assert hashlib.md5(data).hexdigest() == r['md5'], p
            t = data.decode('utf-8', 'replace')
            importer = re.search(r'importer="([^"]+)"', t)
            typ = re.search(r'^type="([^"]+)"', t, re.M)
            dests = re.findall(r'^path(?:\.(\w+))?="res://([^"]+)"', t, re.M)
            out[p[:-len('.import')]] = dict(importer=importer.group(1) if importer else '',
                                            type=typ.group(1) if typ else '',
                                            dests=[(fmt or '', d) for fmt, d in dests])
    return out


imports = read_imports()
imported_files = {p for p in idx if p.startswith('.godot/imported/')}
claimed = set()
for src, info in imports.items():
    for _, d in info['dests']:
        claimed.add(d)


def imported_size(src):
    info = imports.get(src)
    if not info:
        return 0, ''
    tot, fmts = 0, []
    for fmt, d in info['dests']:
        if d in idx:
            tot += int(idx[d]['size'])
            fmts.append(fmt or 'raw')
    return tot, '+'.join(fmts)


# 验证 Godot 导入物命名：<文件名>-<md5("res://源路径")>.<格式>.<扩展>
name_rule_ok = name_rule_bad = 0
for src, info in imports.items():
    for _, d in info['dests']:
        h = hashlib.md5(('res://' + src).encode()).hexdigest()
        if os.path.basename(d).startswith(os.path.basename(src) + '-' + h):
            name_rule_ok += 1
        else:
            name_rule_bad += 1

# ------------------------------------------------------------------ 逻辑资源 = 源路径（.import 去后缀）或普通文件
logical = {}
for p, r in idx.items():
    if p.startswith('.godot/'):
        continue
    if p.endswith('.import'):
        src = p[:-len('.import')]
        sz, fmt = imported_size(src)
        logical[src] = dict(bytes=sz, fmt=fmt, importer=imports.get(src, {}).get('importer', ''), files=1 + len(
            [d for _, d in imports.get(src, {}).get('dests', []) if d in idx]), raw_in_pck=src in idx)
    elif p.endswith('.remap'):
        continue
    else:
        if p in logical:      # 原始文件和 .import 同时打包（debug_audio 的 mp3、icon png）
            logical[p]['bytes'] += int(r['size']); logical[p]['files'] += 1
            continue
        logical[p] = dict(bytes=int(r['size']), fmt='raw', importer='', files=1, raw_in_pck=True)

# ------------------------------------------------------------------ 分类规则（按顺序匹配源路径）
CODE = {
    'card': 'MegaCrit.Sts2.Core.Models/CardModel.cs:143-151',
    'atlas_loader': 'MegaCrit.Sts2.Core.Assets/AtlasResourceLoader.cs:272-368',
    'atlas_mgr': 'MegaCrit.Sts2.Core.Assets/AtlasManager.cs:30',
    'relic': 'MegaCrit.Sts2.Core.Models/RelicModel.cs:128-138',
    'power': 'MegaCrit.Sts2.Core.Models/PowerModel.cs:104-112',
    'potion': 'MegaCrit.Sts2.Core.Models/PotionModel.cs:67-71,99',
    'monster': 'MegaCrit.Sts2.Core.Models/MonsterModel.cs:217',
    'character': 'MegaCrit.Sts2.Core.Models/CharacterModel.cs:117-173',
    'event': 'MegaCrit.Sts2.Core.Models/EventModel.cs:172-206',
    'enchant': 'MegaCrit.Sts2.Core.Models/EnchantmentModel.cs:83-87',
    'orb': 'MegaCrit.Sts2.Core.Models/OrbModel.cs:112-114',
    'act': 'MegaCrit.Sts2.Core.Models/ActModel.cs:51-63,176,249',
    'ancient': 'MegaCrit.Sts2.Core.Models/AncientEventModel.cs:111-133',
    'encounter': 'MegaCrit.Sts2.Core.Models/EncounterModel.cs:181',
    'modifier': 'MegaCrit.Sts2.Core.Models/ModifierModel.cs:63',
    'epoch': 'MegaCrit.Sts2.Core.Timeline/EpochModel.cs:185-187',
    'affliction': 'MegaCrit.Sts2.Core.Models/AfflictionModel.cs:62',
    'tmpsfx': 'MegaCrit.Sts2.Core.Audio.Debug/TmpSfx.cs:7-84',
    'img': 'MegaCrit.Sts2.Core.Helpers/ImageHelper.cs:14',
    'scene': 'MegaCrit.Sts2.Core.Helpers/SceneHelper.cs:12',
}
RULES = [
    # (类别, 中文, 正则, 路径规律, 代码出处)
    ('card_portrait_png', '卡图原图（打包前）', r'^images/packed/card_portraits/[^/]+/(?!beta/)[^/]+\.png$',
     'images/packed/card_portraits/<卡池Title>/<卡id小写>.png', CODE['card']),
    ('card_portrait_beta', '卡图 beta 占位', r'^images/packed/card_portraits/([^/]+/beta/|beta)', 'images/packed/card_portraits/<池>/beta/<id>.png；兜底 card_portraits/beta.png', CODE['atlas_loader']),
    ('atlas_page_card', '卡图图集页', r'^images/atlases/card_atlas_\d+\.png$', 'images/atlases/card_atlas_N.png（tpsheet 给出 <池>/<id>.png 的区域）', CODE['atlas_mgr']),
    ('atlas_page_other', '其它图集页（遗物/能力/药水/意图/UI…）', r'^images/atlases/[^/]+\.png$', 'images/atlases/<图集名>[_N].png', CODE['atlas_mgr']),
    ('atlas_sheet', 'TexturePacker 图集清单', r'^images/atlases/[^/]+\.tpsheet$', 'images/atlases/<图集名>.tpsheet（JSON）', CODE['atlas_mgr']),
    ('atlas_sprite_stub', '图集子图 .tres 桩', r'^images/atlases/[^/]+\.sprites/', 'images/atlases/<图集名>.sprites/<子图>.tres（AtlasTexture，运行时由 AtlasResourceLoader 拦截）', CODE['atlas_loader']),
    ('relic_icon', '遗物大图标', r'^images/relics/(?!beta/)', 'images/relics/<IconBaseName>.png（默认 = id 小写）', CODE['relic']),
    ('relic_icon_beta', '遗物 beta 图标', r'^images/relics/beta/', 'images/relics/beta/<id>.png', CODE['relic']),
    ('power_icon', '能力大图标', r'^images/powers/', 'images/powers/[beta/]<能力id小写>.png', CODE['power']),
    ('potion_image', '药水图', r'^images/potions/', 'images/potions/large/<id>.png；missing_potion.png', CODE['potion']),
    ('enchantment_icon', '附魔图标', r'^images/enchantments/', 'images/enchantments/[beta/]<id>.png', CODE['enchant']),
    ('orb_icon', '充能球图标', r'^images/orbs/', 'images/orbs/<id>.png', CODE['orb']),
    ('event_art', '事件插图', r'^images/events/', 'images/events/<事件id>.png / <id>_phobia_mode.png', CODE['event']),
    ('ancient_art', '古神占位图', r'^images/ancients/', 'images/ancients/<名字>_placeholder.png', ''),
    ('epoch_art', '时间线纪元插图', r'^images/timeline/', 'images/timeline/epoch_portraits/[placeholder/]<纪元id>.png', CODE['epoch']),
    ('map_art', '地图（底图/节点/古神节点）', r'^images/(packed/)?map/', 'images/packed/map/map_bgs/<幕>/map_{top,middle,bottom}_<幕>.png', CODE['act']),
    ('room_art', '房间/战斗背景图层', r'^images/rooms/', 'images/rooms/<幕或Boss>/…（由 scenes/backgrounds/*.tscn 引用）', CODE['act']),
    ('intent_icon', '意图图标', r'^images/packed/intents/', 'images/packed/intents/<意图类>/…', ''),
    ('monster_image', '怪物静态图（beta / 恐惧症模式）', r'^images/monsters/', 'images/monsters/{beta,phobia_mode}/…', ''),
    ('card_overlay', '卡面覆盖层（感染）', r'^images/card_overlays/', 'images/card_overlays/infection/…', CODE['affliction']),
    ('vfx_image', '特效贴图', r'^images/(packed/)?vfx/', 'images/vfx/<类>/…、images/packed/vfx/…', ''),
    ('ui_image', 'UI 贴图', r'^images/(ui/|packed/|ftue/|debug/|icon|sort_arrow)', 'images/ui/…、images/packed/<界面>/…', CODE['img']),
    ('spine_monster', '怪物 Spine 骨骼动画', r'^animations/monsters/', 'animations/monsters/<目录>/<名>.skel + .atlas + .png，<名>_skel_data.tres 串起来', CODE['monster']),
    ('spine_character', '角色 Spine（战斗/选人/商店/营火）', r'^animations/(characters|character_select|merchant|rest_site)/', 'animations/{characters,character_select,merchant,rest_site}/<角色>/…', CODE['character']),
    ('spine_background', '背景 Spine（主菜单/商店/宝箱/Boss 节点）', r'^animations/(backgrounds|map)/', 'animations/backgrounds/<场景>/…、animations/map/<boss>_boss/…', CODE['act']),
    ('spine_vfx_ui', '特效/UI Spine', r'^animations/', 'animations/{vfx,ui}/…', ''),
    ('creature_visual_scene', '生物外观场景', r'^scenes/creature_visuals/', 'scenes/creature_visuals/<怪物或角色id小写>.tscn', CODE['monster']),
    ('background_scene', '战斗背景场景', r'^scenes/backgrounds/', 'scenes/backgrounds/<幕>/<幕>_background.tscn、<boss>_boss/…', CODE['act']),
    ('encounter_scene', '遭遇站位场景', r'^scenes/encounters/', 'scenes/encounters/<遭遇id小写>.tscn', CODE['encounter']),
    ('event_scene', '事件场景', r'^scenes/events/', 'scenes/events/{default,combat}_event_layout.tscn、background_scenes/<id>.tscn、custom/<id>.tscn', CODE['event']),
    ('vfx_scene', '特效场景', r'^scenes/vfx/', 'scenes/vfx/…（vfx/events/<事件id>_vfx.tscn 等）', CODE['event']),
    ('debug_scene', '调试场景', r'^scenes/debug/', 'scenes/debug/…', ''),
    ('ui_scene', 'UI / 界面场景', r'^scenes/', 'scenes/{screens,ui,combat,cards,merchant,rest_site,timeline_screen,ftue,…}/…', CODE['scene']),
    ('material', '材质', r'^materials/', 'materials/{cards,transitions,ui,vfx}/….tres', ''),
    ('shader', '着色器', r'\.(gdshader|gdshaderinc)$', 'shaders/…、各场景目录内联', ''),
    ('shader_res', '着色器资源 .tres', r'^shaders/', 'shaders/….tres', ''),
    ('font', '字体', r'^fonts/', 'fonts/[<语言>/]<字体>.ttf|otf → .fontdata', ''),
    ('theme', 'UI 主题', r'^themes/', 'themes/[fonts/]….tres', ''),
    ('fmod_bank', 'FMOD 音频 bank', r'^banks/', 'banks/desktop/<bank>.bank', 'MegaCrit.Sts2.Core.Models/ActModel.cs:MusicBankPaths'),
    ('debug_audio', '临时音效 mp3（仍在用）', r'^debug_audio/', 'debug_audio/<名>.mp3（TmpSfx.GetPath）', CODE['tmpsfx']),
    ('localization', '本地化文本', r'^localization/', 'localization/<语言>/<表>.json、eng/patch_notes/*.md', ''),
    ('model_3d', '3D 模型', r'^models/', 'models/vfx/…', ''),
    ('addon', '插件（FMOD/Spine/Sentry/自研工具）', r'^addons/', 'addons/<插件>/…', ''),
    ('script_stub', '脚本占位（C# 已编进 sts2.dll，这里只剩路径）', r'^(src/|RiderTestRunner/)', 'src/Core/…/*.cs（0~1 字节）、src/gdscript/*.gdc', ''),
    ('other', '其它', r'.', '', ''),
]
RULES_RX = [(k, zh, re.compile(rx), pat, code) for k, zh, rx, pat, code in RULES]


def classify(p):
    for k, zh, rx, pat, code in RULES_RX:
        if rx.search(p):
            return k
    return 'other'


cat = collections.defaultdict(lambda: dict(n=0, files=0, bytes=0, ext=collections.Counter(), ex=[]))
for p, info in logical.items():
    k = classify(p)
    c = cat[k]
    c['n'] += 1; c['files'] += info['files']; c['bytes'] += info['bytes']
    c['ext'][os.path.splitext(p)[1].lower()] += 1
    if len(c['ex']) < 2:
        c['ex'].append(p)
unclaimed = imported_files - claimed
total_bytes = sum(int(r['size']) for r in idx.values())

with open(os.path.join(CSV, 'ch08_asset_catalog.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['category', 'category_zh', 'n_source_assets', 'n_pck_files', 'bytes', 'MB', 'pct_of_pck', 'source_exts',
                'path_pattern', 'code_rule', 'example'])
    for k, zh, rx, pat, code in RULES:
        if k not in cat:
            continue
        c = cat[k]
        w.writerow([k, zh, c['n'], c['files'], c['bytes'], round(c['bytes'] / 1e6, 2),
                    round(100 * c['bytes'] / total_bytes, 2),
                    ' '.join(f'{e or "(无)"}:{n}' for e, n in c['ext'].most_common(6)), pat, code, ' | '.join(c['ex'])])
    w.writerow(['_unclaimed_imported', '无 .import 认领的导入物', len(unclaimed), len(unclaimed),
                sum(int(idx[p]['size']) for p in unclaimed), '', '', '', '', '', ' | '.join(sorted(unclaimed)[:2])])

# ------------------------------------------------------------------ 导入映射表
with open(os.path.join(CSV, 'ch08_import_map.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['source_path', 'category', 'importer', 'resource_type', 'format', 'imported_path', 'imported_bytes',
                'md5_of_res_path', 'name_rule_ok'])
    for src in sorted(imports):
        info = imports[src]
        h = hashlib.md5(('res://' + src).encode()).hexdigest()
        for fmt, d in info['dests']:
            w.writerow([src, classify(src), info['importer'], info['type'], fmt or 'default', d,
                        idx[d]['size'] if d in idx else '', h, os.path.basename(d).startswith(os.path.basename(src) + '-' + h)])

# ------------------------------------------------------------------ 着色器
with open(os.path.join(CSV, 'ch08_shaders.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['path', 'kind', 'bytes', 'shader_type', 'n_uniforms', 'used_by_n_scenes'])
    shader_paths = [p for p in idx if p.endswith(('.gdshader', '.gdshaderinc')) or
                    (p.startswith('shaders/') and p.endswith('.tres'))]
    # 被多少 tscn/tres 引用
    refs = collections.Counter()
    for fp in glob.glob(os.path.join(TXT, '**', '*.t*'), recursive=True):
        if not fp.endswith(('.tscn', '.tres')):
            continue
        try:
            t = open(fp, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for m in re.finditer(r'path="res://([^"]+\.(?:gdshader|gdshaderinc|tres))"', t):
            if m.group(1).endswith(('.gdshader', '.gdshaderinc')) or m.group(1).startswith('shaders/'):
                refs[m.group(1)] += 1
    for p in sorted(shader_paths):
        fp = os.path.join(TXT, p.replace('/', os.sep))
        st, nu = '', ''
        if os.path.exists(fp):
            t = open(fp, encoding='utf-8', errors='replace').read()
            m = re.search(r'shader_type\s+(\w+)', t)
            st = m.group(1) if m else ('ShaderMaterial/VisualShader' if p.endswith('.tres') else '')
            nu = len(re.findall(r'^\s*uniform\s', t, re.M))
        w.writerow([p, os.path.splitext(p)[1][1:], idx[p]['size'], st, nu, refs.get(p, 0)])

# ------------------------------------------------------------------ 图集清单（tpsheet）
atlas_sprites = {}
for fp in glob.glob(os.path.join(TXT, 'images', 'atlases', '*.tpsheet')):
    name = os.path.basename(fp)[:-len('.tpsheet')]
    d = json.load(open(fp, encoding='utf-8'))
    s = set()
    for tex in d['textures']:
        for sp in tex['sprites']:
            s.add(sp['filename'][:-4] if sp['filename'].endswith('.png') else sp['filename'])
    atlas_sprites[name] = s


def has_res(p):
    """res 路径是否存在（原文件或 .import 认领）"""
    p = p.replace('res://', '')
    return p in idx or (p + '.import') in idx


def res_bytes(p):
    p = p.replace('res://', '')
    if (p + '.import') in idx:
        return imported_size(p)[0]
    return int(idx[p]['size']) if p in idx else 0


def load_csv(name):
    return list(csv.DictReader(open(os.path.join(CSV, name + '.csv'), encoding='utf-8-sig')))


rows_out = []


def add(etype, eid, zh, en, role, path, exists, via='', note='', code=''):
    rows_out.append([etype, eid, zh, en, role, path, int(bool(exists)), via, res_bytes(path) if exists else 0, note, code])


POOL_TITLE = {'Deprecated': 'token'}
for r in load_csv('cards'):
    pool = POOL_TITLE.get(r['pool'], r['pool'].lower())
    cid = r['id'].lower()
    sprite = f'{pool}/{cid}'
    in_atlas = sprite in atlas_sprites['card_atlas']
    png = f'images/packed/card_portraits/{pool}/{cid}.png'
    beta = f'images/packed/card_portraits/{pool}/beta/{cid}.png'
    via = 'atlas' if in_atlas else ('png' if has_res(png) else ('beta' if has_res(beta) else 'missing'))
    add('card', r['id'], r['name_zh'], r['name_en'], 'portrait_atlas_sprite',
        f'images/atlases/card_atlas.sprites/{sprite}.tres', in_atlas, via, '', CODE['card'])
    add('card', r['id'], r['name_zh'], r['name_en'], 'portrait_png', png, has_res(png), via, '', CODE['atlas_loader'])
    if has_res(beta):
        add('card', r['id'], r['name_zh'], r['name_en'], 'portrait_beta_png', beta, True, via, '', CODE['atlas_loader'])

for r in load_csv('relics'):
    rid = r['id'].lower()
    note = ''
    if r['cls'] in ('LoomingFruit',):
        note = 'IconBaseName 动态：无丰饶角时用 <id>_2'
    if r['cls'] in ('YummyCookie',):
        note = 'IconBaseName 按角色变化'
    in_atlas = rid in atlas_sprites['relic_atlas']
    big = f'images/relics/{rid}.png'; beta = f'images/relics/beta/{rid}.png'
    via = 'atlas' if in_atlas else ('png' if has_res(big) else ('beta' if has_res(beta) else 'missing'))
    add('relic', r['id'], r['name_zh'], r['name_en'], 'icon_atlas_sprite', f'images/atlases/relic_atlas.sprites/{rid}.tres', in_atlas, via, note, CODE['relic'])
    add('relic', r['id'], r['name_zh'], r['name_en'], 'icon_outline_sprite', f'images/atlases/relic_outline_atlas.sprites/{rid}.tres', rid in atlas_sprites['relic_outline_atlas'], via, note, CODE['relic'])
    add('relic', r['id'], r['name_zh'], r['name_en'], 'big_icon_png', big, has_res(big), via, note, CODE['relic'])
    if has_res(beta):
        add('relic', r['id'], r['name_zh'], r['name_en'], 'beta_icon_png', beta, True, via, note, CODE['relic'])

for r in load_csv('potions'):
    pid = r['id'].lower()
    in_atlas = pid in atlas_sprites['potion_atlas']
    large = f'images/potions/large/{pid}.png'
    add('potion', r['id'], r['name_zh'], r['name_en'], 'image_atlas_sprite', f'images/atlases/potion_atlas.sprites/{pid}.tres', in_atlas, 'atlas' if in_atlas else 'missing', '', CODE['potion'])
    add('potion', r['id'], r['name_zh'], r['name_en'], 'outline_atlas_sprite', f'images/atlases/potion_outline_atlas.sprites/{pid}.tres', pid in atlas_sprites['potion_outline_atlas'], '', '', CODE['potion'])
    add('potion', r['id'], r['name_zh'], r['name_en'], 'large_png', large, has_res(large), '' if has_res(large) else 'missing_potion.png', '', CODE['potion'])

for r in load_csv('powers'):
    pid = r['id'].lower()
    in_atlas = pid in atlas_sprites['power_atlas']
    big = f'images/powers/{pid}.png'; beta = f'images/powers/beta/{pid}.png'
    via = 'atlas' if in_atlas else ('png' if has_res(big) else ('beta' if has_res(beta) else 'missing'))
    add('power', r['id'], r['name_zh'], r['name_en'], 'icon_atlas_sprite', f'images/atlases/power_atlas.sprites/{pid}.tres', in_atlas, via, '', CODE['power'])
    add('power', r['id'], r['name_zh'], r['name_en'], 'big_icon_png', big if has_res(big) else beta, has_res(big) or has_res(beta), via, '', CODE['power'])


def spine_of_scene(scene_rel):
    """从 creature_visuals/*.tscn 找 SpineSkeletonDataResource，再从 _skel_data.tres 找 .skel/.atlas"""
    fp = os.path.join(TXT, scene_rel.replace('/', os.sep))
    if not os.path.exists(fp):
        return []
    t = open(fp, encoding='utf-8', errors='replace').read()
    out = []
    for m in re.finditer(r'type="SpineSkeletonDataResource"[^\n]*path="res://([^"]+)"', t):
        sd = m.group(1); out.append(('spine_skel_data', sd))
        fp2 = os.path.join(TXT, sd.replace('/', os.sep))
        if os.path.exists(fp2):
            t2 = open(fp2, encoding='utf-8', errors='replace').read()
            for m2 in re.finditer(r'path="res://([^"]+\.(skel|atlas|json))"', t2):
                out.append(('spine_' + m2.group(2), m2.group(1)))
                if m2.group(2) == 'atlas':
                    # 同目录同名 png 页（atlas 可能多页：<名>.png、<名>_2.png…）
                    base = m2.group(1)[:-len('.atlas')]
                    for cand in [base + '.png'] + [f'{base}_{i}.png' for i in range(2, 9)]:
                        if has_res(cand):
                            out.append(('spine_png', cand))
    return out


for r in load_csv('monsters'):
    mid = r['id'].lower()
    vis = f'scenes/creature_visuals/{mid}.tscn'
    note = 'VisualsPath 被覆盖为 defect（测试怪）' if r['cls'] in ('BigDummy',) else ''
    add('monster', r['id'], r['name_zh'], r['name_en'], 'creature_visuals_scene', vis, has_res(vis), '', note, CODE['monster'])
    for role, p in spine_of_scene(vis):
        add('monster', r['id'], r['name_zh'], r['name_en'], role, p, has_res(p), '', '', CODE['monster'])

for r in load_csv('characters'):
    cid = r['id'].lower()
    for role, p in [('creature_visuals_scene', f'scenes/creature_visuals/{cid}.tscn'),
                    ('char_select_icon', f'images/packed/character_select/char_select_{cid}.png'),
                    ('char_select_locked', f'images/packed/character_select/char_select_{cid}_locked.png'),
                    ('top_panel_icon', f'images/ui/top_panel/character_icon_{cid}.png'),
                    ('map_marker', f'images/packed/map/icons/map_marker_{cid}.png')]:
        add('character', r['id'], r['name_zh'], r.get('name_en', ''), role, p, has_res(p), '', '', CODE['character'])
    for role, p in spine_of_scene(f'scenes/creature_visuals/{cid}.tscn'):
        add('character', r['id'], r['name_zh'], r.get('name_en', ''), role, p, has_res(p), '', '', CODE['character'])

for r in load_csv('encounters'):
    eid = r['id'].lower()
    p = f'scenes/encounters/{eid}.tscn'
    add('encounter', r['id'], r['name_zh'], '', 'encounter_scene', p, has_res(p), '', '无站位场景时按默认排布（推断）' if not has_res(p) else '', CODE['encounter'])
    bg = [q for q in idx if q.startswith(f'scenes/backgrounds/{eid}/') and q.endswith('.tscn')]
    for q in bg[:3]:
        add('encounter', r['id'], r['name_zh'], '', 'custom_background_scene', q, True, '', '', CODE['act'])

for r in load_csv('events'):
    eid = r['id'].lower()
    for role, p in [('portrait', f'images/events/{eid}.png'), ('portrait_phobia', f'images/events/{eid}_phobia_mode.png'),
                    ('background_scene', f'scenes/events/background_scenes/{eid}.tscn'),
                    ('custom_layout', f'scenes/events/custom/{eid}.tscn'), ('vfx_scene', f'scenes/vfx/events/{eid}_vfx.tscn'),
                    ('ancient_map_node', f'images/packed/map/ancients/ancient_node_{eid}.png')]:
        if has_res(p) or role == 'portrait':
            add('event', r['id'], r['name_zh'], r.get('name_en', ''), role, p, has_res(p), '', '', CODE['event'] if role != 'ancient_map_node' else CODE['ancient'])

for name, etype, pat, code in [('enchantments', 'enchantment', 'images/enchantments/{}.png', CODE['enchant']),
                               ('orbs', 'orb', 'images/orbs/{}.png', CODE['orb']),
                               ('modifiers', 'modifier', 'images/packed/modifiers/{}.png', CODE['modifier'])]:
    for r in load_csv(name):
        i = r['id'].lower()
        p = pat.format(i)
        if not has_res(p) and etype == 'enchantment' and has_res(f'images/enchantments/beta/{i}.png'):
            p = f'images/enchantments/beta/{i}.png'
        add(etype, r['id'], r['name_zh'], r.get('name_en', ''), 'icon', p, has_res(p), '', '', code)
        if etype == 'orb':
            q = f'scenes/orbs/orb_visuals/{i}.tscn'
            add(etype, r['id'], r['name_zh'], r.get('name_en', ''), 'orb_visual_scene', q, has_res(q), '', '', code)

for r in load_csv('afflictions'):
    i = r['id'].lower()
    p = f'scenes/cards/overlays/afflictions/{i}.tscn'
    add('affliction', r['id'], r['name_zh'], r.get('name_en', ''), 'overlay_scene', p, has_res(p), '', '', CODE['affliction'])

for r in load_csv('acts'):
    a = r['act'].lower()
    for role, p in [('combat_background_scene', f'scenes/backgrounds/{a}/{a}_background.tscn'),
                    ('map_top', f'images/packed/map/map_bgs/{a}/map_top_{a}.png'),
                    ('map_middle', f'images/packed/map/map_bgs/{a}/map_middle_{a}.png'),
                    ('map_bottom', f'images/packed/map/map_bgs/{a}/map_bottom_{a}.png')]:
        add('act', r['act'], r['name_zh'], '', role, p, has_res(p), '', '', CODE['act'])

# 时间线纪元
ep = json.load(open(os.path.join(TXT, 'localization', 'eng', 'epochs.json'), encoding='utf-8'))
for k in sorted({k.split('.')[0] for k in ep if k.endswith('.title')}):
    i = k.lower()
    real = f'images/timeline/epoch_portraits/{i}.png'
    ph = f'images/timeline/epoch_portraits/placeholder/{i}.png'
    add('epoch', k, '', ep.get(k + '.title', ''), 'portrait', real if has_res(real) else ph,
        has_res(real) or has_res(ph), 'real' if has_res(real) else ('placeholder' if has_res(ph) else 'missing'), '', CODE['epoch'])

# 已删除内容（本地化残留，无类）的资源残留
CUT = {'card': ['CHRYSALIS', 'DESPAIR', 'FLAME_IN_THE_DARK', 'GHOST_EATER', 'GOOD_INSTINCTS', 'IMMORTALITY', 'IMPALE',
                'OFF_BY_ONE', 'PAELS_STRIKE', 'PITY', 'QUICK_SLASH', 'RESERVES', 'SHARP_EDGE', 'SPIKED', 'STAR_BLAST',
                'STAR_SHIELD', 'SWIFT_STRIKE', 'TEZCATARAS_MIGHT', 'TRAINING_STRIKE', 'VETERAN',
                'VISIONS_OF_GRANDEUR', 'WARP_SPACE'],
       'relic': ['CURSED_KETTLE', 'ENDLESS_APPETITE', 'GLOWING_ORB', 'INK_BOTTLE', 'MYSTERIOUS_COCOON', 'RED_VINE_TEA',
                 'VINE_BRACELET'],
       'monster': ['BYRDONIS_NEST', 'COCOON', 'GAZING_MOTH', 'GEM_EATER', 'HATCHLING', 'THE_ARM', 'THE_BELL',
                   'THE_DREAMER']}
for et, ids in CUT.items():
    for i in ids:
        lo = i.lower()
        if et == 'card':
            hits = [p for p in idx if re.search(r'card_portraits/[^/]+/(beta/)?' + lo + r'\.png', p)] + \
                   [f'atlas:{s}' for s in atlas_sprites['card_atlas'] if s.endswith('/' + lo)]
        elif et == 'relic':
            hits = [p for p in idx if re.search(r'images/relics/(beta/)?' + lo + r'\.png', p)] + \
                   [f'atlas:{lo}'] * (lo in atlas_sprites['relic_atlas'])
        else:
            hits = [p for p in idx if f'/{lo}/' in p or f'/{lo}.' in p or f'/{lo}_' in p]
        add('cut_' + et, i, '', '', 'leftover_assets', '; '.join(sorted(hits)[:6]) if hits else '(无)', bool(hits),
            '', '本地化有 key、代码无类（已删内容）', '')

# 图集里有子图、但当前没有对应模型的「孤儿子图」= 已删/改名内容的成品美术残留（或同一物品的变体图）
cur_cards = {(POOL_TITLE.get(r['pool'], r['pool'].lower())) + '/' + r['id'].lower() for r in load_csv('cards')}
cur = {'card_atlas': cur_cards, 'relic_atlas': {r['id'].lower() for r in load_csv('relics')},
       'power_atlas': {r['id'].lower() for r in load_csv('powers')},
       'potion_atlas': {r['id'].lower() for r in load_csv('potions')}}
for atlas, ids in cur.items():
    for s in sorted(atlas_sprites[atlas] - ids):
        variant = bool(re.search(r'(_\d|_open|_(ironclad|silent|defect|necro|regent)|beta|missing_power|_plus_power)$', s)) \
            or s.startswith('event/mad_science_') or s.startswith('status/wither')
        add('orphan_sprite', s, '', '', atlas, f'images/atlases/{atlas}.sprites/{s}.tres', True,
            'variant' if variant else 'no_model', '同一物品的变体/占位图' if variant else '图集里有成品图、代码里无此模型（已删或改名）',
            CODE['atlas_mgr'])

with open(os.path.join(CSV, 'ch08_asset_paths_by_entity.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['entity_type', 'id', 'name_zh', 'name_en', 'asset_role', 'res_path', 'exists_in_pck', 'resolved_via',
                'imported_bytes', 'note', 'code_rule'])
    w.writerows(rows_out)

# ------------------------------------------------------------------ 控制台摘要
print('pck files', len(idx), 'total MB', round(total_bytes / 1e6, 1))
print('.import', len(imports), 'imported files', len(imported_files), 'unclaimed', len(unclaimed))
print('import name rule ok/bad', name_rule_ok, name_rule_bad)
print('logical assets', len(logical))
for k, zh, *_ in RULES:
    if k in cat:
        print(f'  {k:24s} n={cat[k]["n"]:5d} files={cat[k]["files"]:5d} MB={cat[k]["bytes"] / 1e6:8.2f}')
cov = collections.defaultdict(collections.Counter)
seen = set()
for row in rows_out:
    key = (row[0], row[1], row[4])
    if key in seen:
        continue
    seen.add(key)
    cov[(row[0], row[4])][row[6]] += 1
for (et, role), c in sorted(cov.items()):
    print(f'  {et:12s} {role:26s} exists={c[1]} missing={c[0]}')
via = collections.defaultdict(collections.Counter)
for row in rows_out:
    if row[4] in ('portrait_atlas_sprite', 'icon_atlas_sprite', 'image_atlas_sprite') or (row[0] == 'epoch'):
        via[row[0]][row[7]] += 1
print('resolved via', {k: dict(v) for k, v in via.items()})
print('atlas sprites', {k: len(v) for k, v in atlas_sprites.items()})
