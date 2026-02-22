"""
⭐ 추천 셀(최저 확률) 클릭 성공률 테스트
- 0% 안전 셀이 없는 교착 상황에서 최저 확률 셀을 클릭
- 그 셀이 실제 안전한지(성공) / 지뢰인지(실패) 집계
"""
import random
from test_hint import *


def simulate_with_star(rows, cols, n_mines):
    board = [[0]*cols for _ in range(rows)]
    cs    = [[STATE_CLOSED]*cols for _ in range(rows)]
    flags = 0

    sr, sc_ = rows//2, cols//2
    place_mines(board, rows, cols, n_mines, sr, sc_)
    open_bfs(board, cs, sr, sc_, rows, cols)

    star_attempts = 0    # ⭐ 클릭 횟수
    star_success  = 0    # ⭐ 클릭 성공 (안전)
    star_fail     = 0    # ⭐ 클릭 실패 (지뢰)
    star_probs    = []   # ⭐ 셀의 확률 기록

    for _ in range(rows * cols):
        probs = calc_probs(board, cs, rows, cols, n_mines, flags)

        safe = [(r,c) for (r,c),p in probs.items()
                if round(p*100)==0 and cs[r][c]==STATE_CLOSED]
        mine = [(r,c) for (r,c),p in probs.items()
                if round(p*100)==100 and cs[r][c]==STATE_CLOSED]

        # 깃발 먼저
        for r,c in mine:
            if cs[r][c]==STATE_CLOSED:
                cs[r][c]=STATE_FLAG; flags+=1

        if safe:
            # 0% 셀이 있으면 오픈
            for r,c in safe:
                if cs[r][c]!=STATE_CLOSED: continue
                if board[r][c]==-1:
                    return star_attempts, star_success, star_fail, star_probs  # 이론상 false safe
                open_bfs(board, cs, r, c, rows, cols)
        elif not safe and not mine:
            # ⭐ 추천: 최저 확률 셀 클릭
            closed_probs = {(r,c):p for (r,c),p in probs.items()
                           if cs[r][c]==STATE_CLOSED}
            if not closed_probs:
                break
            best = min(closed_probs, key=lambda k: closed_probs[k])
            best_p = closed_probs[best]
            star_attempts += 1
            star_probs.append(round(best_p*100))

            r, c = best
            if board[r][c] == -1:
                star_fail += 1
                break   # 게임오버
            else:
                star_success += 1
                open_bfs(board, cs, r, c, rows, cols)
        # safe 없고 mine만 있는 경우 → 다시 루프

        opened = sum(1 for r in range(rows) for c in range(cols) if cs[r][c]==STATE_OPEN)
        if opened >= rows*cols - n_mines:
            break

    return star_attempts, star_success, star_fail, star_probs


def run_star_test(rows, cols, n_mines, n_games, label):
    print(f"\n[{label}] {rows}×{cols}, 지뢰 {n_mines}개, {n_games}게임")
    total_att = 0; total_suc = 0; total_fail = 0
    all_probs = []; wins = 0

    for i in range(n_games):
        att, suc, fail, ps = simulate_with_star(rows, cols, n_mines)
        total_att  += att
        total_suc  += suc
        total_fail += fail
        all_probs.extend(ps)
        if fail == 0:
            wins += 1

    click_rate = total_suc / max(1, total_att) * 100
    win_rate   = wins / n_games * 100
    avg_prob   = sum(all_probs) / max(1, len(all_probs))

    print(f"  ⭐ 클릭 총 {total_att}회  |  성공 {total_suc}  |  실패(💥) {total_fail}")
    print(f"  ⭐ 클릭 생존율: {click_rate:.1f}%")
    print(f"  ⭐ 셀 평균 확률: {avg_prob:.1f}%")
    print(f"  게임 클리어율 (힌트 활용): {win_rate:.1f}% ({wins}/{n_games})")

    if all_probs:
        from collections import Counter
        dist = Counter(all_probs)
        print(f"  ⭐ 확률 분포 (상위 10):")
        for pct, cnt in sorted(dist.items())[:10]:
            bar = '█' * (cnt * 40 // max(dist.values()))
            print(f"    {pct:3d}% : {cnt:4d}회 {bar}")


if __name__ == "__main__":
    import time
    print("="*60)
    print("  ⭐ 추천 셀 클릭 성공률 테스트")
    print("  (0% 셀 없을 때 최저확률 셀 클릭)")
    print("="*60)
    t0 = time.time()

    run_star_test(9,  9,  10,  500, "초급")
    run_star_test(16, 16, 40,  300, "중급")
    run_star_test(16, 30, 99,  500, "고급")

    print(f"\n{'='*60}")
    print(f"  소요 시간: {time.time()-t0:.1f}초")
    print("="*60)
