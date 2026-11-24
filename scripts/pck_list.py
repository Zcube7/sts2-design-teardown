"""Godot 4 PCK (format v2/v3) directory lister / extractor.

用法:
  python -I scripts/pck_list.py <pck> list  <out.csv>
  python -I scripts/pck_list.py <pck> extract <out_dir> <regex>   # 只解匹配的路径(非美术)
"""
import csv, hashlib, re, struct, sys, os

PACK_DIR_ENCRYPTED = 1
PACK_REL_FILEBASE = 2
PACK_FILE_ENCRYPTED = 1
PACK_FILE_REMOVAL = 2


def read_dir(path):
    f = open(path, 'rb')
    magic = f.read(4)
    assert magic == b'GDPC', magic
    fmt, vmaj, vmin, vpat, flags = struct.unpack('<5I', f.read(20))
    file_base, = struct.unpack('<Q', f.read(8))
    if fmt >= 3:
        dir_ofs, = struct.unpack('<Q', f.read(8))
    else:
        dir_ofs = None
    f.read(16 * 4)
    if dir_ofs is not None:
        f.seek(dir_ofs)
    if flags & PACK_DIR_ENCRYPTED:
        raise SystemExit('directory is encrypted')
    count, = struct.unpack('<I', f.read(4))
    entries = []
    for _ in range(count):
        n, = struct.unpack('<I', f.read(4))
        p = f.read(n).rstrip(b'\0').decode('utf-8')
        ofs, size = struct.unpack('<QQ', f.read(16))
        md5 = f.read(16).hex()
        fl, = struct.unpack('<I', f.read(4))
        if flags & PACK_REL_FILEBASE:
            ofs += file_base
        entries.append((p, ofs, size, md5, fl))
    hdr = dict(fmt=fmt, godot=f'{vmaj}.{vmin}.{vpat}', flags=flags, file_base=file_base, dir_ofs=dir_ofs, count=count)
    return f, hdr, entries


def main():
    pck, mode, out = sys.argv[1:4]
    f, hdr, entries = read_dir(pck)
    print(hdr)
    if mode == 'list':
        with open(out, 'w', newline='', encoding='utf-8') as o:
            w = csv.writer(o)
            w.writerow(['path', 'ext', 'size', 'offset', 'md5', 'flags'])
            for p, ofs, size, md5, fl in entries:
                ext = os.path.splitext(p)[1].lower()
                w.writerow([p, ext, size, ofs, md5, fl])
        enc = sum(1 for e in entries if e[4] & PACK_FILE_ENCRYPTED)
        print('entries', len(entries), 'encrypted', enc, 'total bytes', sum(e[2] for e in entries))
    elif mode == 'extract':
        rx = re.compile(sys.argv[4])
        n = bad = 0
        for p, ofs, size, md5, fl in entries:
            if not rx.search(p):
                continue
            if fl & PACK_FILE_ENCRYPTED:
                print('skip encrypted', p)
                continue
            f.seek(ofs)
            data = f.read(size)
            if hashlib.md5(data).hexdigest() != md5:
                bad += 1
            rel = p.replace('res://', '').replace(':', '_')
            dst = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as o:
                o.write(data)
            n += 1
        print('extracted', n, 'md5 mismatch', bad)


if __name__ == '__main__':
    main()
