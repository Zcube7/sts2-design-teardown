"""第 05 章：StandardActMap 地图生成的 Python 复刻 + 蒙特卡洛统计 -> data/csv/ch05_map_sim.csv

python -I -X utf8 scripts/ch05_map_sim.py [每幕样本数，默认 400]

复刻范围（逐行对照 csharp/sts2_src/MegaCrit.Sts2.Core.Map/）：
  StandardActMap.GenerateMap / GenerateNextCoord / HasInvalidCrossover / AssignPointTypes / IsValidPointType
  MapPathPruning.PruneAndRepair 全套（含 BreakAParentChildRelationship）
  ActModel 各幕 GetMapPointTypes（NextGaussianInt 拒绝采样）
不复刻：MapPostProcessing（只挪列坐标，不改拓扑与类型）。
RNG 用 Python random，不是游戏的 .NET Random——只能看统计分布，不能按种子复现具体地图。
"""
import csv
import math
import os
import random
import statistics
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'data', 'csv')

W = 7
UNASSIGNED, UNKNOWN, SHOP, TREASURE, REST, MONSTER, ELITE, BOSS, ANCIENT = range(9)
TNAME = {UNKNOWN: '未知', SHOP: '商店', TREASURE: '宝箱', REST: '休息处', MONSTER: '敌人', ELITE: '精英'}


class P:
    __slots__ = ('col', 'row', 'children', 'parents', 'type', 'mod', 'uid')
    _n = 0

    def __init__(self, col, row):
        self.col, self.row = col, row
        self.children, self.parents = [], []   # 用 list 保序，增删时去重（等价 HashSet）
        self.type = UNASSIGNED
        self.mod = True
        P._n += 1
        self.uid = P._n

    def add_child(self, c):
        if c not in self.children:
            self.children.append(c)
        if self not in c.parents:
            c.parents.append(self)

    def remove_child(self, c):
        if c in self.children:
            self.children.remove(c)
        if self in c.parents:
            c.parents.remove(self)


def gaussian_int(rng, mean, sd, lo, hi):
    while True:
        d = 1.0 - rng.random()
        n = 1.0 - rng.random()
        z = math.sqrt(-2.0 * math.log(d)) * math.sin(2 * math.pi * n)
        v = round(mean + sd * z)
        if lo <= v <= hi:
            return v


def act_counts(act, rng, swarming=False):
    unknown = gaussian_int(rng, 12, 1, 10, 14)
    if act in ('Overgrowth', 'Underdocks'):
        rest = gaussian_int(rng, 7, 1, 6, 7)
    elif act == 'Hive':
        rest = gaussian_int(rng, 6, 1, 6, 7)
        unknown -= 1
    else:  # Glory
        rest = rng.randrange(5, 7)
        unknown -= 1
    # 源码里 rest 先于 unknown 抽（两次调用顺序不影响分布）
    elites = round(5 * (1.6 if swarming else 1.0))
    return dict(rest=rest, shop=3, elite=elites, unknown=unknown)


ROOMS = {'Overgrowth': 15, 'Underdocks': 15, 'Hive': 14, 'Glory': 13}


class Map:
    def __init__(self, act, rng, multiplayer=False, swarming=False):
        self.rng = rng
        self.L = ROOMS[act] - (1 if multiplayer else 0) + 1   # _mapLength
        self.grid = [[None] * self.L for _ in range(W)]
        self.counts = act_counts(act, rng, swarming)
        self.boss = P(W // 2, self.L)
        self.start = P(W // 2, 0)
        self.starts = []
        self.generate()
        self.assign()
        self.nodes_before_prune = len(self.all_points())
        self.prune_and_repair()

    # ---------- 拓扑 ----------
    def get_or_create(self, col, row):
        p = self.grid[col][row]
        if p is None:
            p = P(col, row)
            self.grid[col][row] = p
        return p

    def invalid_crossover(self, cur, tx):
        dx = tx - cur.col
        if dx == 0:
            return False
        nb = self.grid[tx][cur.row]
        if nb is None:
            return False
        return any(ch.col - nb.col == -dx for ch in nb.children)

    def next_coord(self, cur):
        col = cur.col
        lo, hi = max(0, col - 1), min(col + 1, 6)
        dirs = [-1, 0, 1]
        self.rng.shuffle(dirs)
        for d in dirs:
            tx = {-1: lo, 0: col, 1: hi}[d]
            if not self.invalid_crossover(cur, tx):
                return tx, cur.row + 1
        raise RuntimeError('Cannot find next node')

    def path_generate(self, p):
        while p.row < self.L - 1:
            c, r = self.next_coord(p)
            q = self.get_or_create(c, r)
            p.add_child(q)
            p = q

    def generate(self):
        for i in range(7):
            p = self.get_or_create(self.rng.randrange(7), 1)
            if i == 1:
                while p in self.starts:
                    p = self.get_or_create(self.rng.randrange(7), 1)
            if p not in self.starts:
                self.starts.append(p)
            self.path_generate(p)
        for p in self.row(self.L - 1):
            p.add_child(self.boss)
        for p in self.row(1):
            self.start.add_child(p)

    def row(self, r):
        return [self.grid[c][r] for c in range(W) if self.grid[c][r] is not None]

    def all_points(self):
        return [self.grid[c][r] for c in range(W) for r in range(self.L) if self.grid[c][r] is not None]

    # ---------- 类型 ----------
    def valid(self, t, p):
        if p.row >= self.L - 3 and t == REST:
            return False
        if p.row < 6 and t in (REST, ELITE):
            return False
        if t in (ELITE, REST, TREASURE, SHOP):
            if any(q.type == t for q in p.parents + p.children):
                return False
        if t in (REST, MONSTER, UNKNOWN, ELITE, SHOP):
            sib = [c for par in p.parents for c in par.children if c is not p]
            if any(q.type == t for q in sib):
                return False
        return True

    def next_valid(self, queue, p):
        for _ in range(len(queue)):
            t = queue.pop(0)
            if self.valid(t, p):
                return t
            queue.append(t)
        return UNASSIGNED

    def assign(self):
        for p in self.row(self.L - 1):
            p.type, p.mod = REST, False
        for p in self.row(self.L - 7):
            p.type, p.mod = TREASURE, False
        for p in self.row(1):
            p.type, p.mod = MONSTER, False
        c = self.counts
        queue = [REST] * c['rest'] + [SHOP] * c['shop'] + [ELITE] * c['elite'] + [UNKNOWN] * c['unknown']
        self.dropped = 0
        for _ in range(3):
            if not queue:
                break
            un = [p for p in self.all_points() if p.type == UNASSIGNED]
            self.rng.shuffle(un)
            for p in un:
                if not queue:
                    break
                p.type = self.next_valid(queue, p)
        self.dropped = len(queue)
        for p in self.all_points():
            if p.type == UNASSIGNED:
                p.type = MONSTER
        self.boss.type = BOSS
        self.start.type = ANCIENT

    # ---------- 剪枝 ----------
    def find_all_paths(self, p):
        if p.type == BOSS:
            return [[p]]
        out = []
        for ch in p.children:
            for tail in self.find_all_paths(ch):
                out.append([p] + tail)
        return out

    def find_matching(self):
        segs = {}
        for path in self.find_all_paths(self.start):
            n = len(path)
            for i in range(n - 1):
                s = path[i]
                if not (len(s.children) > 1 or s.row == 0):
                    continue
                for j in range(2, n - i):
                    e = path[i + j]
                    if len(e.parents) >= 2:
                        seg = path[i:i + j + 1]
                        head = f'{s.row}-' if s.row == 0 else f'{s.col},{s.row}-'
                        key = head + f'{e.col},{e.row}-' + ','.join(str(q.type) for q in seg)
                        lst = segs.get(key)
                        if lst is None:
                            segs[key] = [seg]
                        elif not any(self.overlap(a, seg) for a in lst):
                            lst.append(seg)
        return [segs[k] for k in sorted(segs) if len(segs[k]) > 1]

    @staticmethod
    def overlap(a, b):
        if len(a) < 3 or len(b) < 3:
            return False
        return any(a[i] is b[i] for i in range(1, len(a) - 1))

    def in_map(self, p):
        if self.grid[p.col][p.row] is None and p.type != ANCIENT:
            return p.type == BOSS
        return True

    def removed(self, p):
        return p.row >= self.L or self.grid[p.col][p.row] is None

    def remove_point(self, p):
        self.grid[p.col][p.row] = None
        if p in self.starts:
            self.starts.remove(p)
        for c in list(p.children):
            p.remove_child(c)
        for par in list(p.parents):
            par.remove_child(p)

    def prune_segment(self, seg):
        res = False
        for i in range(len(seg) - 1):
            p = seg[i]
            if not self.in_map(p):
                return True
            if len(p.children) > 1 or len(p.parents) > 1 or any(len(par.children) == 1 and not self.removed(par) for par in p.parents):
                continue
            if not any(len(n.children) > 1 and len(n.parents) == 1 for n in seg[i:]):
                if len(seg[-1].parents) == 1:
                    return False
                if not any(len(c.parents) == 1 for c in p.children if c not in seg):
                    self.remove_point(p)
                    res = True
        return res

    def prune_paths(self, matching):
        for lst in matching:
            self.rng.shuffle(lst)
            num = 0
            for m in lst:
                if num == len(lst) - 1:
                    break
                if self.prune_segment(m):
                    num += 1
            if num:
                return True
            for seg in lst:
                broke = False
                for i in range(len(seg) - 1):
                    p = seg[i]
                    if len(p.children) >= 2 and len(seg[i + 1].parents) != 1:
                        p.remove_child(seg[i + 1])
                        broke = True
                if broke:
                    return True
        return False

    def prune(self):
        it = 0
        while self.prune_paths(self.find_matching()):
            it += 1
            if it > 50:
                raise RuntimeError('prune > 50')
        return it

    def repair(self):
        changed = False
        for t, target in ((SHOP, self.counts['shop']), (ELITE, self.counts['elite']), (REST, self.counts['rest']), (UNKNOWN, self.counts['unknown'])):
            pts = self.all_points()
            need = target - sum(1 for p in pts if p.type == t)
            if need <= 0:
                continue
            mons = [p for p in pts if p.type == MONSTER and p.mod]
            self.rng.shuffle(mons)
            for p in mons:
                if need == 0:
                    break
                if self.valid(t, p):
                    p.type = t
                    need -= 1
                    changed = True
        return changed

    def prune_and_repair(self):
        self.prune_rounds = 0
        for _ in range(3):
            self.prune_rounds += self.prune()
            if not self.repair():
                break


def stats_for(act, n, seed, multiplayer=False, swarming=False):
    rng = random.Random(seed)
    rows = []
    for k in range(n):
        m = Map(act, rng, multiplayer, swarming)
        pts = m.all_points()
        reach = set()
        stack = [m.start]
        while stack:
            q = stack.pop()
            for c in q.children:
                if c is not m.boss and c.uid not in reach:
                    reach.add(c.uid)
                    stack.append(c)
        tc = Counter(p.type for p in pts)
        paths = m.find_all_paths(m.start)
        per = {t: [sum(1 for q in path if q.type == t) for path in paths] for t in TNAME}
        rows.append(dict(
            nodes_before=m.nodes_before_prune, nodes=len(pts), reachable=len(reach), dropped=m.dropped,
            starts=len(m.row(1)), paths=len(paths),
            **{f'map_{TNAME[t]}': tc.get(t, 0) for t in TNAME},
            **{f'path_min_{TNAME[t]}': min(per[t]) for t in TNAME},
            **{f'path_max_{TNAME[t]}': max(per[t]) for t in TNAME},
            **{f'path_mean_{TNAME[t]}': statistics.mean(per[t]) for t in TNAME},
            target_rest=m.counts['rest'], target_unknown=m.counts['unknown'],
        ))
    return rows


def summarize(label, rows):
    out = {'scenario': label, 'samples': len(rows)}
    for k in rows[0]:
        vals = [r[k] for r in rows]
        out[k + '_avg'] = round(statistics.mean(vals), 2)
        if k in ('nodes', 'paths', 'starts') or k.startswith('map_') or k.startswith('path_m'):
            out[k + '_p10'] = sorted(vals)[len(vals) // 10]
            out[k + '_p90'] = sorted(vals)[len(vals) * 9 // 10]
    return out


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    scen = [
        ('密林 Overgrowth 单人', 'Overgrowth', False, False),
        ('巢穴 Hive 单人', 'Hive', False, False),
        ('荣耀 Glory 单人', 'Glory', False, False),
        ('密林 Overgrowth 多人(-1行)', 'Overgrowth', True, False),
        ('密林 Overgrowth 进阶1 精英×1.6', 'Overgrowth', False, True),
    ]
    summ = []
    for i, (label, act, mp, sw) in enumerate(scen):
        rows = stats_for(act, n, 20261123 + i, mp, sw)
        s = summarize(label, rows)
        summ.append(s)
        print(label, {k: v for k, v in s.items() if k.endswith('_avg') and (k.startswith('map_') or k.startswith('path_mean') or k in ('nodes_avg', 'paths_avg', 'nodes_before_avg', 'starts_avg', 'dropped_avg', 'reachable_avg'))})
    keys = []
    for s in summ:
        for k in s:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(OUT, 'ch05_map_sim.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(summ)
    print('wrote ch05_map_sim.csv')
