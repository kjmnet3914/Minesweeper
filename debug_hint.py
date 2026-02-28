import random
from math import comb
from test_hint import *

random.seed(2)
board=[[0]*9 for _ in range(9)]
cs=[[STATE_CLOSED]*9 for _ in range(9)]
place_mines(board,9,9,10,4,4)
open_bfs(board,cs,4,4,9,9)

# Reproduce full calc
raw=[]
for r in range(9):
    for c in range(9):
        if cs[r][c]!=STATE_OPEN: continue
        val=board[r][c]
        if val<=0: continue
        nbrs=neighbors(r,c,9,9)
        flags=sum(1 for nr,nc in nbrs if cs[nr][nc]==STATE_FLAG)
        cl=frozenset((nr,nc) for nr,nc in nbrs if cs[nr][nc]==STATE_CLOSED)
        if not cl: continue
        raw.append((val-flags, cl))
cst=list(set(raw))
ds=set(); dm=set(); changed=True
while changed:
    changed=False; new=[]
    for rem,cl in cst:
        cl2=frozenset(c for c in cl if c not in ds and c not in dm)
        r2=rem-sum(1 for c in cl if c in dm)
        if r2<0 or r2>len(cl2): continue
        if r2==0 and cl2: ds.update(cl2); changed=True
        elif cl2 and r2==len(cl2): dm.update(cl2); changed=True
        elif cl2: new.append((r2,cl2))
    cst=new
frontier=set()
for _,cl in cst: frontier.update(cl)

tot_cl=sum(1 for r in range(9) for c in range(9) if cs[r][c]==STATE_CLOSED)
tot_rem=10-0  # n_mines - flags

print(f"tot_cl={tot_cl}, tot_rem={tot_rem}")
print(f"frontier={len(frontier)}, ds={len(ds)}, dm={len(dm)}")

# Group 1: cells[(2,0),(3,0),(4,0),(5,0)]  configs=[(0,1,1,0), mines=2]
# Group 2: cells of size 9  
# adj_nf = tot_cl - frontier - ds - dm + fb
adj_nf = tot_cl - len(frontier) - len(ds) - len(dm)
print(f"adj_nf={adj_nf}")

# Group dists
# Group(5,0): only config has 2 mines -> dist = {2: 1}
# Group(0,8): let's check
# total_dist = conv({2:1}, group2_dist)
# total_weight = sum(cnt * C(adj_nf, tot_rem - dm_count - m))
rem_base = tot_rem - len(dm)
print(f"rem_base = {rem_base} (tot_rem={tot_rem} - dm={len(dm)})")

# For group (5,0): m_j = 2
# For the (5,0)=1 config: mine_w needs C(adj_nf, rem_base - m_j - m_o) > 0
# rem_base - m_j = 7 - 2 = 5
# need C(adj_nf, 5 - m_o) where adj_nf=6
# adj_nf=6, so C(6, 5-m_o) needs 0 <= 5-m_o <= 6
print(f"For (5,0)=mine: need C({adj_nf}, {rem_base}-2-m_o) for each m_o in group2")
print(f"  = C({adj_nf}, {rem_base-2}-m_o)")
print(f"  rem_base-2 = {rem_base-2}")
print(f"  adj_nf = {adj_nf}")
print(f"  So need m_o such that 0 <= {rem_base-2}-m_o <= {adj_nf}")
print(f"  i.e. m_o <= {rem_base-2} and m_o >= {rem_base-2-adj_nf}")
print(f"  i.e. {rem_base-2-adj_nf} <= m_o <= {rem_base-2}")
