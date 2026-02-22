"""
지뢰찾기 힌트(확률) 계산 검증 테스트 v2
- 게임 오버(False Safe 첫 발생) 즉시 중단 → 반복 카운트 없음
- 각 게임에서 False Safe가 1번이라도 있으면 오류 게임으로 집계
"""
import random
from math import comb

STATE_CLOSED   = 0
STATE_OPEN     = 1
STATE_FLAG     = 2

def neighbors(r, c, rows, cols):
    return [(r+dr, c+dc) for dr in range(-1,2) for dc in range(-1,2)
            if (dr,dc)!=(0,0) and 0<=r+dr<rows and 0<=c+dc<cols]

def place_mines(board, rows, cols, n_mines, sr, sc):
    safe = {(r,c) for r in range(sr-1,sr+2) for c in range(sc-1,sc+2)
            if 0<=r<rows and 0<=c<cols}
    pool = [(r,c) for r in range(rows) for c in range(cols) if (r,c) not in safe]
    mines = set(random.sample(pool, min(n_mines, len(pool))))
    for r,c in mines: board[r][c] = -1
    for r in range(rows):
        for c in range(cols):
            if board[r][c] == -1: continue
            board[r][c] = sum(1 for nr,nc in neighbors(r,c,rows,cols) if board[nr][nc]==-1)
    return mines

def open_bfs(board, cs, r, c, rows, cols):
    q, visited = [(r,c)], set()
    while q:
        cr,cc = q.pop(0)
        if (cr,cc) in visited or cs[cr][cc] != STATE_CLOSED: continue
        visited.add((cr,cc)); cs[cr][cc] = STATE_OPEN
        if board[cr][cc] == 0:
            for nr,nc in neighbors(cr,cc,rows,cols):
                if (nr,nc) not in visited and cs[nr][nc] == STATE_CLOSED:
                    q.append((nr,nc))

def calc_probs(board, cs, rows, cols, n_mines, flags_count):
    MAX_G, MAX_N = 100, 2_000_000

    def sc(n, k):
        return comb(n, k) if 0 <= k <= n else 0

    raw = []
    for r in range(rows):
        for c in range(cols):
            if cs[r][c] != STATE_OPEN: continue
            val = board[r][c]
            if val <= 0: continue
            nbrs = neighbors(r, c, rows, cols)
            flags = sum(1 for nr,nc in nbrs if cs[nr][nc] == STATE_FLAG)
            cl = frozenset((nr,nc) for nr,nc in nbrs if cs[nr][nc] == STATE_CLOSED)
            if not cl: continue
            raw.append((val - flags, cl))
    cst = list(set(raw))

    tot_cl   = sum(1 for r in range(rows) for c in range(cols) if cs[r][c] == STATE_CLOSED)
    tot_rem  = n_mines - flags_count
    gprob    = tot_rem / max(1, tot_cl)

    if not cst:
        return {(r,c): gprob for r in range(rows) for c in range(cols) if cs[r][c] == STATE_CLOSED}

    # 제약 전파 + Gaussian Elimination
    ds, dm, changed = set(), set(), True
    while changed:
        changed = False
        # (a) 기본 전파
        new = []
        for rem, cl in cst:
            cl2 = frozenset(c for c in cl if c not in ds and c not in dm)
            r2  = rem - sum(1 for c in cl if c in dm)
            if r2 < 0 or r2 > len(cl2): continue
            if r2 == 0 and cl2:          ds.update(cl2); changed = True
            elif cl2 and r2 == len(cl2): dm.update(cl2); changed = True
            elif cl2: new.append((r2, cl2))
        cst = new
        if not cst: break

        # (b) Gaussian elimination
        from math import gcd
        acg = set()
        for _, cl in cst: acg.update(cl)
        cl_list = sorted(acg)
        ci = {c: i for i, c in enumerate(cl_list)}
        nv, nr = len(cl_list), len(cst)
        mat = []
        for rem, cl in cst:
            row = [0]*(nv+1)
            for c in cl: row[ci[c]] = 1
            row[nv] = rem
            mat.append(row)
        pri = 0
        for col in range(nv):
            if pri >= nr: break
            pr = None
            for r in range(pri, nr):
                if mat[r][col] != 0: pr = r; break
            if pr is None: continue
            mat[pri], mat[pr] = mat[pr], mat[pri]
            pv = mat[pri][col]
            for r in range(nr):
                if r == pri or mat[r][col] == 0: continue
                fac = mat[r][col]
                for j in range(nv+1):
                    mat[r][j] = mat[r][j]*pv - fac*mat[pri][j]
                rg = 0
                for j in range(nv+1): rg = gcd(rg, abs(mat[r][j]))
                if rg > 1:
                    for j in range(nv+1): mat[r][j] //= rg
            pri += 1
        for row in mat:
            co = row[:nv]; rv = row[nv]
            nz = [(i, co[i]) for i in range(nv) if co[i] != 0]
            if not nz: continue
            pc = [cl_list[i] for i in range(nv) if co[i] > 0]
            nc = [cl_list[i] for i in range(nv) if co[i] < 0]
            ps = sum(co[i] for i in range(nv) if co[i] > 0)
            ns = sum(-co[i] for i in range(nv) if co[i] < 0)
            if not nc and all(co[ci[c]]==1 for c in pc):
                if rv == 0: ds.update(pc); changed = True
                elif rv == len(pc): dm.update(pc); changed = True
            if len(nz) == 1:
                i, c = nz[0]
                if c != 0 and rv % c == 0:
                    v = rv // c
                    if v == 0: ds.add(cl_list[i]); changed = True
                    elif v == 1: dm.add(cl_list[i]); changed = True
            if pc and nc:
                if rv == ps:
                    dm.update(pc); ds.update(nc); changed = True
                elif rv == -ns:
                    ds.update(pc); dm.update(nc); changed = True

    frontier = set()
    for _, cl in cst: frontier.update(cl)

    parent = {c: c for c in frontier}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(x, y):
        px, py = find(x), find(y)
        if px != py: parent[px] = py

    for _, cl in cst:
        it = iter(cl); f = next(it)
        for cell in it: union(f, cell)

    groups = {}
    for cell in frontier: groups.setdefault(find(cell), []).append(cell)

    gcst = {root: [] for root in groups}
    for rem, cl in cst: gcst[find(next(iter(cl)))].append((rem, cl))

    def enum_group(cells, cst_g, randomize=False):
        n = len(cells)
        cnt = {c: 0 for c in cells}
        for _, cl in cst_g:
            for c in cl: cnt[c] += 1
        cells = sorted(cells, key=lambda c: -cnt[c])
        imap = {c: i for i,c in enumerate(cells)}
        cid, cl_list = [[] for _ in range(n)], []
        for ci, (rem, cl) in enumerate(cst_g):
            cl_list.append((rem, cl))
            for c in cl: cid[imap[c]].append(ci)
        asgn, res, nodes, abort = [0]*n, [], [0], [False]
        def bt(pos, m):
            if abort[0]: return
            nodes[0] += 1
            if nodes[0] > MAX_N: abort[0] = True; return
            if pos == n: res.append((tuple(asgn), m)); return
            vals = (0, 1)
            if randomize:
                import random as _rng
                vals = (0, 1) if _rng.random() < 0.5 else (1, 0)
            for v in vals:
                ok = True
                for ci in cid[pos]:
                    rem, cl = cl_list[ci]; mm = uu = 0
                    for c in cl:
                        j = imap[c]
                        if j < pos: mm += asgn[j]
                        elif j == pos: mm += v
                        else: uu += 1
                    if mm > rem or (rem-mm) > uu: ok = False; break
                if ok: asgn[pos] = v; bt(pos+1, m+v); asgn[pos] = 0
        bt(0, 0)
        if not res: return None
        return (res, cells)

    gdata, fb = {}, set()
    for root, cells in groups.items():
        if len(cells) > MAX_G:
            result = enum_group(cells, gcst[root], randomize=True)
            if result is not None:
                gdata[root] = (result[1], result[0])
            else:
                fb.update(cells)
            continue
        result = enum_group(cells, gcst[root])
        if result is None: fb.update(cells); continue
        sorted_cells, cfg = result[1], result[0]
        gdata[root] = (sorted_cells, cfg)

    def conv(d1, d2):
        out = {}
        for m1,c1 in d1.items():
            for m2,c2 in d2.items():
                k = m1+m2; out[k] = out.get(k,0)+c1*c2
        return out

    tdist, gdists = {0: 1}, {}
    for root, (_, cfg) in gdata.items():
        d = {}
        for _, mc in cfg: d[mc] = d.get(mc,0)+1
        gdists[root] = d; tdist = conv(tdist, d)

    adj_nf = max(0, (tot_cl - len(frontier) - len(ds) - len(dm)) + len(fb))
    tw = sum(cnt * sc(adj_nf, tot_rem - len(dm) - m) for m,cnt in tdist.items())

    probs = {}
    for cell in ds: probs[cell] = 0.0
    for cell in dm: probs[cell] = 1.0

    if tw > 0:
        for jroot, (jcells, jcfg) in gdata.items():
            jmap = {c: i for i,c in enumerate(jcells)}
            od = {0: 1}
            for kr, kd in gdists.items():
                if kr != jroot: od = conv(od, kd)
            rb = tot_rem - len(dm)
            for cell in jcells:
                ci = jmap[cell]
                mw = sum(co * sc(adj_nf, rb-mj-mo)
                         for a,mj in jcfg if a[ci]==1
                         for mo,co in od.items())
                probs[cell] = mw / tw
        rb = tot_rem - len(dm)
        nfw = sum(cnt * sc(adj_nf-1, rb-m-1) for m,cnt in tdist.items()) if adj_nf > 0 else 0
        nfp = nfw / tw if adj_nf > 0 else 0.0
    else:
        nfp = gprob

    for r in range(rows):
        for c in range(cols):
            if cs[r][c] != STATE_CLOSED: continue
            cell = (r, c)
            if cell not in probs:
                probs[cell] = nfp

    return probs


def simulate(rows, cols, n_mines):
    board = [[0]*cols for _ in range(rows)]
    cs    = [[STATE_CLOSED]*cols for _ in range(rows)]
    flags = 0

    sr, sc_ = rows//2, cols//2
    place_mines(board, rows, cols, n_mines, sr, sc_)
    open_bfs(board, cs, sr, sc_, rows, cols)

    false_safe = False
    zero_preds = 0

    for _ in range(rows * cols):
        probs = calc_probs(board, cs, rows, cols, n_mines, flags)

        safe = [(r,c) for (r,c),p in probs.items()
                if round(p*100) == 0 and cs[r][c] == STATE_CLOSED]
        mine = [(r,c) for (r,c),p in probs.items()
                if round(p*100) == 100 and cs[r][c] == STATE_CLOSED]

        if not safe and not mine:
            break

        # 깃발 먼저
        for r,c in mine:
            if cs[r][c] == STATE_CLOSED:
                cs[r][c] = STATE_FLAG; flags += 1

        # 안전 셀 오픈 → 지뢰면 즉시 게임오버
        hit = False
        for r,c in safe:
            if cs[r][c] != STATE_CLOSED: continue
            zero_preds += 1
            if board[r][c] == -1:
                false_safe = True
                hit = True
                break   # ← 게임오버: 더 이상 열지 않음
            else:
                open_bfs(board, cs, r, c, rows, cols)

        if hit:
            break   # 이 게임 종료

        opened = sum(1 for r in range(rows) for c in range(cols) if cs[r][c] == STATE_OPEN)
        if opened >= rows * cols - n_mines:
            break

    return false_safe, zero_preds


def run_test(rows, cols, n_mines, n_games, label):
    print(f"\n[{label}] {rows}×{cols}, 지뢰 {n_mines}개, {n_games}게임")
    fs_games = 0; total_zp = 0; crashes = 0

    for i in range(n_games):
        try:
            fs, zp = simulate(rows, cols, n_mines)
            total_zp += zp
            if fs:
                fs_games += 1
                if fs_games <= 5:   # 최초 5건만 출력
                    print(f"  ⚠  Game {i+1:4d}: FALSE SAFE 발생 (0% 예측 {zp}건 중)")
        except Exception as e:
            crashes += 1
            print(f"  ❌ Game {i+1:4d}: 예외 → {e}")

    rate = fs_games / n_games * 100
    print(f"  결과: 0% 예측 총 {total_zp}건 | "
          f"False Safe 게임 {fs_games}/{n_games} ({rate:.1f}%) | 크래시 {crashes}건")
    verdict = "✅ PASS" if fs_games == 0 and crashes == 0 else "❌ FAIL"
    print(f"  판정: {verdict}")
    return fs_games, crashes


if __name__ == "__main__":
    import time
    print("="*60)
    print("  지뢰찾기 확률 힌트 검증  (False Safe = 0%인데 지뢰)")
    print("  ※ 게임오버 즉시 중단, 게임당 최대 1회 카운트")
    print("="*60)
    t0 = time.time()

    fs1, c1 = run_test(9,  9,  10,  500, "초급")
    fs2, c2 = run_test(16, 16, 40,  200, "중급")
    fs3, c3 = run_test(16, 30, 99,  100, "고급")

    elapsed  = time.time() - t0
    total_fs = fs1 + fs2 + fs3
    total_c  = c1  + c2  + c3
    print(f"\n{'='*60}")
    print(f"  최종: False Safe 게임 {total_fs}건 / 크래시 {total_c}건")
    print(f"  소요 시간: {elapsed:.1f}초")
    verdict = "✅ ALL PASS" if total_fs == 0 and total_c == 0 else "❌ ISSUES FOUND"
    print(f"  전체 판정: {verdict}")
    print("="*60)
