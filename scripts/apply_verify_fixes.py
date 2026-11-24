"""把核查员的 logs/verify/chNN_fixes.json 套回正文：fix_old 必须在目标文件里逐字唯一出现才替换。

python -I -X utf8 scripts/apply_verify_fixes.py            # 预演，只报告能否匹配
python -I -X utf8 scripts/apply_verify_fixes.py --apply    # 备份后真正替换
结果写 logs/verify/apply_log.csv
"""
import csv, glob, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VDIR = os.path.join(ROOT, 'logs', 'verify')
apply = '--apply' in sys.argv


def norm(p):
    p = p.replace('\\', '/')
    for pre in (ROOT.replace('\\', '/') + '/',):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def main():
    fixes = []
    for jf in sorted(glob.glob(os.path.join(VDIR, 'ch*_fixes.json'))):
        src = os.path.basename(jf)
        try:
            items = json.load(open(jf, encoding='utf-8'))
        except Exception as e:
            print(f'!! {src} 解析失败: {e}')
            continue
        for i, it in enumerate(items):
            fixes.append(dict(src=src, idx=i, **{k: it.get(k, '') for k in ('file', 'fix_old', 'fix_new', 'severity', 'reason', 'evidence')}))

    texts, log = {}, []
    for f in fixes:
        rel = norm(f['file'])
        path = os.path.join(ROOT, rel)
        if rel not in texts:
            texts[rel] = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        t = texts[rel]
        if t is None:
            status = 'no_file'
        elif not f['fix_old']:
            status = 'empty_old'
        elif f['fix_old'] == f['fix_new']:
            status = 'noop'
        else:
            n = t.count(f['fix_old'])
            if n == 1:
                texts[rel] = t.replace(f['fix_old'], f['fix_new'], 1)
                status = 'applied'
            elif n == 0:
                status = 'not_found'
            else:
                status = f'ambiguous_{n}'
        log.append(dict(source=f['src'], idx=f['idx'], file=rel, status=status, severity=f['severity'],
                        reason=f['reason'], fix_old=f['fix_old'][:200], fix_new=f['fix_new'][:200]))

    if apply:
        bdir = os.path.join(VDIR, 'backup')
        os.makedirs(bdir, exist_ok=True)
        for rel, t in texts.items():
            if t is None:
                continue
            path = os.path.join(ROOT, rel)
            orig = open(path, encoding='utf-8').read()
            if orig != t:
                shutil.copy2(path, os.path.join(bdir, rel.replace('/', '__')))
                open(path, 'w', encoding='utf-8', newline='').write(t)

    with open(os.path.join(VDIR, 'apply_log.csv'), 'w', newline='', encoding='utf-8-sig') as o:
        w = csv.DictWriter(o, fieldnames=list(log[0].keys()) if log else ['status'])
        w.writeheader()
        w.writerows(log)

    from collections import Counter
    print('mode', 'APPLY' if apply else 'dry-run', '| fixes', len(log))
    print('status', dict(Counter(x['status'] for x in log)))
    print('severity', dict(Counter(x['severity'] for x in log)))
    print('by source', dict(Counter(x['source'] for x in log)))
    for x in log:
        if x['status'] != 'applied':
            print(' -', x['source'], x['idx'], x['status'], x['file'], '|', x['fix_old'][:80].replace('\n', ' '))


if __name__ == '__main__':
    main()
