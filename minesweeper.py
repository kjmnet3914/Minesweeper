"""
지뢰찾기 (Minesweeper)
======================
윈도우 내장 지뢰찾기와 동일한 기능 구현
- 초급 / 중급 / 고급 / 사용자 정의 난이도
- 첫 클릭 보호 (첫 클릭 위치에는 지뢰 미배치)
- 좌클릭: 셀 열기 / 우클릭: 깃발·물음표 토글
- 좌+우 동시 클릭: Chord Click (인접 깃발 수 == 숫자 → 자동 오픈)
- 빈 칸 자동 연쇄 열기 (BFS)
- 타이머, 지뢰 카운터, 이모지 상태 버튼
- 난이도별 최고 기록 저장 (best_records.json)
- 클래식 Windows 3D UI 스타일

v1.2 - 개선:
  * CELL_SIZE 26 → 32 (전체 화면 확대)
  * LCD, 이모지 버튼 폰트 크기 확대
  * 좌+우 동시 클릭 (Chord Click) 구현

Author : Antigravity AI
Date   : 2026-02-21
"""

import tkinter as tk
from tkinter import messagebox
import random
import json
import os

# ─────────────────────────────────────────────
#  상수 정의
# ─────────────────────────────────────────────
CELL_SIZE  = 64    # 셀 한 변 픽셀 (32 → 64, 2배)
INNER_PAD  = 16    # 패널-보드 사이 패딩

# 색상 팔레트 (클래식 Windows 지뢰찾기)
BG_GRAY    = "#C0C0C0"
DARK_GRAY  = "#808080"
WHITE      = "#FFFFFF"
SHADOW     = "#5A5A5A"   # 더 진한 음영
LIGHT      = "#FFFFFF"
LCD_BG     = "#000000"
LCD_FG     = "#FF0000"
CELL_CLOSED= "#D4D0C8"   # 닫힌 셀: 밝은 베이지-그레이
CELL_OPEN  = "#8C8C8C"   # 열린 셀: 확실히 어두운 회색
CELL_PRESS = "#A0A0A0"   # 눌린 셀: 중간 회색
MINE_COLOR = "#000000"
FLAG_RED   = "#FF0000"
HIT_RED    = "#FF0000"

# 숫자별 색상 (클래식 지뢰찾기 배색)
NUM_COLORS = {
    1: "#0000FF",
    2: "#007B00",
    3: "#FF0000",
    4: "#00007B",
    5: "#7B0000",
    6: "#007B7B",
    7: "#000000",
    8: "#7B7B7B",
}

# 난이도 프리셋 (rows, cols, mines)
DIFFICULTIES = {
    "초급": (9,  9,  10),
    "중급": (16, 16, 40),
    "고급": (16, 30, 99),
}

RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best_records.json")

# ─────────────────────────────────────────────
#  최고 기록 로드/저장
# ─────────────────────────────────────────────
def load_records() -> dict:
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"초급": None, "중급": None, "고급": None}

def save_records(records: dict):
    try:
        with open(RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[기록 저장 실패] {e}")

# ─────────────────────────────────────────────
#  셀 상태 상수
# ─────────────────────────────────────────────
STATE_CLOSED   = 0
STATE_OPEN     = 1
STATE_FLAG     = 2
STATE_QUESTION = 3

# ─────────────────────────────────────────────
#  메인 게임 클래스
# ─────────────────────────────────────────────
class Minesweeper:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("지뢰찾기")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_GRAY)

        self.records = load_records()

        # 난이도 상태변수 (메뉴 라디오버튼 공유)
        self.diff_var  = tk.StringVar(value="초급")
        self.difficulty = "초급"
        self.rows, self.cols, self.mine_count = DIFFICULTIES["초급"]

        self._build_menu()
        self._init_game()

    # ──────────────────────────────────────────
    #  메뉴 바
    # ──────────────────────────────────────────
    def _build_menu(self):
        MFONT = ("맑은 고딕", 13)
        menubar   = tk.Menu(self.root, font=MFONT)
        game_menu = tk.Menu(menubar, tearoff=0, font=MFONT)

        game_menu.add_command(label="새 게임 (F2)", command=self._new_game)
        game_menu.add_separator()

        for diff in ["초급", "중급", "고급"]:
            # 클로저 캡처를 위해 default 인자 사용
            game_menu.add_radiobutton(
                label=diff,
                variable=self.diff_var,
                value=diff,
                command=lambda d=diff: self._set_difficulty(d),
            )

        game_menu.add_command(label="사용자 정의...", command=self._custom_difficulty)
        game_menu.add_separator()
        game_menu.add_command(label="최고 기록 보기", command=self._show_records)
        game_menu.add_separator()
        game_menu.add_command(label="종료", command=self.root.quit)

        menubar.add_cascade(label="게임", menu=game_menu)
        self.root.configure(menu=menubar)
        self.root.bind("<F2>", lambda e: self._new_game())

    # ──────────────────────────────────────────
    #  게임 데이터 초기화
    # ──────────────────────────────────────────
    def _init_game(self):
        self.board       = [[0]*self.cols for _ in range(self.rows)]
        self.cell_state  = [[STATE_CLOSED]*self.cols for _ in range(self.rows)]
        self.first_click = True
        self.game_over   = False
        self.game_won    = False
        self.flags_count = 0
        self.open_count  = 0
        self.elapsed     = 0
        self._timer_id   = None
        self._press_pos  = None  # 현재 눌린 셀 (r, c)
        self._hint_mode  = False  # 힌트 오버레이 표시 여부

        self._build_ui()

    # ──────────────────────────────────────────
    #  UI 구성
    # ──────────────────────────────────────────
    def _build_ui(self):
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()

        # 외곽 프레임
        outer = tk.Frame(self.root, bg=BG_GRAY, relief="raised", bd=3)
        outer.pack(padx=4, pady=4)

        # ── 상단 패널 ──
        panel = tk.Frame(outer, bg=BG_GRAY, relief="sunken", bd=2)
        panel.pack(fill="x", padx=INNER_PAD, pady=(INNER_PAD, INNER_PAD // 2))

        # 지뢰 카운터 (LCD 크기 업)  
        self.mine_lbl = tk.Label(
            panel, text=self._lcd(self.mine_count),
            bg=LCD_BG, fg=LCD_FG,
            font=("Courier New", 48, "bold"),
            width=3, relief="sunken", bd=2, padx=6
        )
        self.mine_lbl.pack(side="left", padx=(12, 0), pady=12)

        # 얼굴 버튼 — 폰트는 28pt 고정, 패딩으로 버튼 크기 확보
        self.face_btn = tk.Button(
            panel, text="\U0001f642",
            font=("Segoe UI Emoji", 28),
            bg=BG_GRAY, activebackground=DARK_GRAY,
            relief="raised", bd=3,
            command=self._new_game,
            cursor="hand2",
            padx=16, pady=8
        )
        self.face_btn.pack(side="left", expand=True, pady=8)

        # 타이머 (LCD) — 먼저 pack(side=right) 해야 힌트 버튼이 왼쪽에 위치
        self.timer_lbl = tk.Label(
            panel, text=self._lcd(0),
            bg=LCD_BG, fg=LCD_FG,
            font=("Courier New", 48, "bold"),
            width=3, relief="sunken", bd=2, padx=6
        )
        self.timer_lbl.pack(side="right", padx=(0, 12), pady=12)

        # 💡 힌트 버튼 (타이머 왼쪽)
        self.hint_btn = tk.Button(
            panel, text="💡",
            font=("Segoe UI Emoji", 22),
            bg=BG_GRAY, activebackground=DARK_GRAY,
            relief="raised", bd=3,
            command=self._toggle_hint,
            cursor="hand2",
            padx=10, pady=6
        )
        self.hint_btn.pack(side="right", pady=8, padx=(0, 4))

        # ✔ 안전 셀 자동 열기 버튼 (힌트 모드에서만 표시)
        self.auto_safe_btn = tk.Button(
            panel, text="✔️안전",
            font=("맑은 고딕", 13, "bold"),
            bg="#C8F0C8", activebackground="#A0E0A0",
            relief="raised", bd=2,
            command=self._auto_open_safe,
            cursor="hand2",
            padx=6, pady=4
        )
        # 🚩 지뢰 자동 깃발 버튼 (힌트 모드에서만 표시)
        self.auto_flag_btn = tk.Button(
            panel, text="🚩지뢰",
            font=("맑은 고딕", 13, "bold"),
            bg="#F0C8C8", activebackground="#E0A0A0",
            relief="raised", bd=2,
            command=self._auto_flag_mines,
            cursor="hand2",
            padx=6, pady=4
        )
        # 🎲 자동 플레이 버튼 (안전→깃발→반복→교착시 ⭐클릭)
        self.auto_play_btn = tk.Button(
            panel, text="🎲자동",
            font=("맑은 고딕", 13, "bold"),
            bg="#C8D8F0", activebackground="#A0B8E0",
            relief="raised", bd=2,
            command=self._auto_play,
            cursor="hand2",
            padx=6, pady=4
        )
        # 초기에는 숨김 (힌트 on 시 표시)

        # ── 보드 캔버스 ──
        self.canvas = tk.Canvas(
            outer,
            width=self.cols * CELL_SIZE,
            height=self.rows * CELL_SIZE,
            bg=BG_GRAY, highlightthickness=0,
            relief="sunken", bd=3
        )
        self.canvas.pack(padx=INNER_PAD, pady=(0, INNER_PAD))

        self.canvas.bind("<Button-1>",         self._on_lpress)
        self.canvas.bind("<ButtonRelease-1>",  self._on_lrelease)
        self.canvas.bind("<Button-3>",         self._on_rpress)
        self.canvas.bind("<ButtonRelease-3>",  self._on_rrelease)
        self.canvas.bind("<B1-Motion>",        self._on_ldrag)
        self.canvas.bind("<B3-Motion>",        self._on_rdrag)

        self._draw_board()
        self.root.update_idletasks()

        # 마우스 버튼 상태 추적 (chord click용)
        self._left_down  = False
        self._right_down = False

    # ──────────────────────────────────────────
    #  그리기 유틸
    # ──────────────────────────────────────────
    def _lcd(self, n: int) -> str:
        n = max(-99, min(999, n))
        return f"-{abs(n):02d}" if n < 0 else f"{n:03d}"

    def _xy(self, r: int, c: int):
        """셀 좌상단 픽셀 좌표"""
        return c * CELL_SIZE, r * CELL_SIZE

    def _rc(self, x: int, y: int):
        """픽셀 → (row, col), 범위 밖이면 (None, None)"""
        c, r = x // CELL_SIZE, y // CELL_SIZE
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None, None

    def _tag(self, r, c):
        return f"c{r}_{c}"

    def _draw_board(self):
        self.canvas.delete("all")
        for r in range(self.rows):
            for c in range(self.cols):
                self._draw_cell(r, c)

    def _draw_cell(self, r: int, c: int):
        x0, y0 = self._xy(r, c)
        x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE
        st  = self.cell_state[r][c]
        val = self.board[r][c]
        tag = self._tag(r, c)
        self.canvas.delete(tag)

        if st == STATE_OPEN:
            self.canvas.create_rectangle(
                x0, y0, x1-1, y1-1,
                fill=CELL_OPEN, outline="#505050", tags=tag
            )
            if val == -1:
                self._draw_mine_normal(x0, y0, tag)
            elif val > 0:
                self.canvas.create_text(
                    x0 + CELL_SIZE // 2, y0 + CELL_SIZE // 2,
                    text=str(val),
                    font=("Arial", CELL_SIZE // 3, "bold"),
                    fill=NUM_COLORS.get(val, "#000000"),
                    tags=tag
                )
        elif st == STATE_CLOSED:
            self._draw_raised(x0, y0, x1, y1, tag)
        elif st == STATE_FLAG:
            self._draw_raised(x0, y0, x1, y1, tag)
            self._draw_flag(x0, y0, tag)
        elif st == STATE_QUESTION:
            self._draw_raised(x0, y0, x1, y1, tag)
            self.canvas.create_text(
                x0 + CELL_SIZE // 2, y0 + CELL_SIZE // 2,
                text="?", font=("Arial", CELL_SIZE // 3, "bold"),
                fill="#7B00FF", tags=tag
            )

    def _draw_raised(self, x0, y0, x1, y1, tag):
        """3D 돌출 셀 — 내부 rect로 테두리 그려 인접 셀 번짐 완전 방지"""
        bw = max(3, CELL_SIZE // 14)   # 64px → 4px
        # 배경 전체 채우기
        self.canvas.create_rectangle(
            x0, y0, x1-1, y1-1,
            fill=CELL_CLOSED, outline="", tags=tag
        )
        # 상단 LIGHT (horizontal strip)
        self.canvas.create_rectangle(
            x0, y0, x1-1, y0+bw-1,
            fill=LIGHT, outline="", tags=tag
        )
        # 좌측 LIGHT (vertical strip)
        self.canvas.create_rectangle(
            x0, y0, x0+bw-1, y1-1,
            fill=LIGHT, outline="", tags=tag
        )
        # 하단 SHADOW (horizontal strip) — 나중에 그려 코너를 덮음
        self.canvas.create_rectangle(
            x0, y1-bw, x1-1, y1-1,
            fill=SHADOW, outline="", tags=tag
        )
        # 우측 SHADOW (vertical strip)
        self.canvas.create_rectangle(
            x1-bw, y0, x1-1, y1-1,
            fill=SHADOW, outline="", tags=tag
        )

    def _draw_pressed(self, r: int, c: int):
        """눌린 효과 — 4변 어두운 띠를 명시적으로 그려 인접 셀 구분을 확실하게"""
        x0, y0 = self._xy(r, c)
        x1, y1 = x0 + CELL_SIZE, y0 + CELL_SIZE
        tag = self._tag(r, c)
        self.canvas.delete(tag)
        SEP   = "#303030"          # 구분선 색 (아주 어두운 회색, 대비 극대화)
        SEP_W = max(2, CELL_SIZE // 32)  # 구분선 두께 (64px→2px, 인접 시 2+2=4px띠)
        bw    = max(2, CELL_SIZE // 24)  # sunken 음영 두께

        # ① 배경
        self.canvas.create_rectangle(
            x0, y0, x1-1, y1-1,
            fill=CELL_PRESS, outline="", tags=tag
        )
        # ② sunken 음영 (구분선 안쪽에 그림)
        self.canvas.create_rectangle(
            x0+SEP_W, y0+SEP_W, x1-SEP_W-1, y0+SEP_W+bw-1,
            fill=SHADOW, outline="", tags=tag
        )
        self.canvas.create_rectangle(
            x0+SEP_W, y0+SEP_W, x0+SEP_W+bw-1, y1-SEP_W-1,
            fill=SHADOW, outline="", tags=tag
        )
        # ③ 4변 어두운 구분선 띠 (마지막에 그려 위에 덮음)
        self.canvas.create_rectangle(x0,       y0,       x1-1,       y0+SEP_W-1, fill=SEP, outline="", tags=tag)  # 상
        self.canvas.create_rectangle(x0,       y1-SEP_W, x1-1,       y1-1,       fill=SEP, outline="", tags=tag)  # 하
        self.canvas.create_rectangle(x0,       y0,       x0+SEP_W-1, y1-1,       fill=SEP, outline="", tags=tag)  # 좌
        self.canvas.create_rectangle(x1-SEP_W, y0,       x1-1,       y1-1,       fill=SEP, outline="", tags=tag)  # 우

    def _draw_flag(self, x0, y0, tag):
        """CELL_SIZE 뱄례 소수시배 깃발 그리기"""
        cx = x0 + CELL_SIZE // 2
        cy = y0 + CELL_SIZE // 2
        s  = CELL_SIZE // 4        # 스케일 인자 (64→s=16)
        lw = max(2, CELL_SIZE // 20)  # 선 두께
        # 깃대
        self.canvas.create_line(
            cx, cy + s + 2, cx, cy - s,
            fill=MINE_COLOR, width=lw, tags=tag
        )
        # 깃발 삼각형
        self.canvas.create_polygon(
            cx,     cy - s,
            cx,     cy,
            cx - s, cy - s // 2,
            fill=FLAG_RED, outline=FLAG_RED, tags=tag
        )
        # 받침대
        self.canvas.create_line(
            cx - s // 2, cy + s + 2,
            cx + s // 2, cy + s + 2,
            fill=MINE_COLOR, width=lw, tags=tag
        )

    def _draw_mine_core(self, cx, cy, r, tag):
        """지뢰 본체 (원 + 가시 + 반짝임) - 배경 위에 호출"""
        # 원
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                fill=MINE_COLOR, outline=MINE_COLOR, tags=tag)
        # 4방향 가시
        for dx, dy in [(0, -(r+2)), (0, r+2), (-(r+2), 0), (r+2, 0)]:
            self.canvas.create_line(cx, cy, cx+dx, cy+dy,
                                    fill=MINE_COLOR, width=2, tags=tag)
        # 반짝임
        hs = max(1, r // 3)
        self.canvas.create_oval(cx-hs, cy-hs, cx, cy,
                                fill=WHITE, outline="", tags=tag)

    def _draw_mine_normal(self, x0, y0, tag):
        """일반 지뢰 (회색 배경 위)"""
        cx = x0 + CELL_SIZE // 2
        cy = y0 + CELL_SIZE // 2
        r  = CELL_SIZE // 2 - 4
        self._draw_mine_core(cx, cy, r, tag)

    def _draw_mine_hit(self, x0, y0, tag):
        """밟은 지뢰 (빨간 배경)"""
        # 1) 빨간 배경
        self.canvas.create_rectangle(
            x0, y0, x0+CELL_SIZE, y0+CELL_SIZE,
            fill=HIT_RED, outline=DARK_GRAY, tags=tag
        )
        # 2) 지뢰 본체
        cx = x0 + CELL_SIZE // 2
        cy = y0 + CELL_SIZE // 2
        r  = CELL_SIZE // 2 - 4
        self._draw_mine_core(cx, cy, r, tag)

    def _draw_mine_wrong(self, x0, y0, tag):
        """틀린 깃발 위치 (지뢰+X)"""
        cx = x0 + CELL_SIZE // 2
        cy = y0 + CELL_SIZE // 2
        r  = CELL_SIZE // 2 - 4
        # 회색 배경은 이미 그려진 상태에서 호출됨
        self._draw_mine_core(cx, cy, r, tag)
        # 빨간 X
        m = 3
        self.canvas.create_line(x0+m, y0+m, x0+CELL_SIZE-m, y0+CELL_SIZE-m,
                                fill=HIT_RED, width=2, tags=tag)
        self.canvas.create_line(x0+CELL_SIZE-m, y0+m, x0+m, y0+CELL_SIZE-m,
                                fill=HIT_RED, width=2, tags=tag)

    # ──────────────────────────────────────────
    #  지뢰 배치
    # ──────────────────────────────────────────
    def _place_mines(self, safe_r: int, safe_c: int):
        """첫 클릭 주변 3×3 제외하고 지뢰 배치"""
        safe = {
            (safe_r+dr, safe_c+dc)
            for dr in range(-1, 2)
            for dc in range(-1, 2)
            if 0 <= safe_r+dr < self.rows and 0 <= safe_c+dc < self.cols
        }
        candidates = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) not in safe
        ]
        random.shuffle(candidates)
        for r, c in candidates[:self.mine_count]:
            self.board[r][c] = -1

        # 인접 수 계산
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    continue
                cnt = sum(
                    1
                    for dr in range(-1, 2)
                    for dc in range(-1, 2)
                    if 0 <= r+dr < self.rows and 0 <= c+dc < self.cols
                    and self.board[r+dr][c+dc] == -1
                )
                self.board[r][c] = cnt

    # ──────────────────────────────────────────
    #  셀 열기 (BFS)
    # ──────────────────────────────────────────
    def _open_cell(self, r: int, c: int):
        if self.cell_state[r][c] != STATE_CLOSED:
            return

        queue   = [(r, c)]
        visited = set()

        while queue:
            cr, cc = queue.pop(0)
            if (cr, cc) in visited:
                continue
            visited.add((cr, cc))
            if self.cell_state[cr][cc] != STATE_CLOSED:
                continue

            self.cell_state[cr][cc] = STATE_OPEN
            self.open_count += 1
            self._draw_cell(cr, cc)

            if self.board[cr][cc] == 0:
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = cr+dr, cc+dc
                        if (0 <= nr < self.rows and 0 <= nc < self.cols
                                and (nr, nc) not in visited
                                and self.cell_state[nr][nc] == STATE_CLOSED):
                            queue.append((nr, nc))

        # BFS 완료 후 힌트 레이어를 최상위로 올림
        # (새로 그려진 셀들이 힌트 텍스트를 가리지 않도록)
        if self._hint_mode:
            self.canvas.tag_raise("hint")

    # ──────────────────────────────────────────
    #  Chord Click 헬퍼
    # ──────────────────────────────────────────
    def _neighbors(self, r: int, c: int):
        """유효한 인접 셀 (r, c) 목록"""
        return [
            (r+dr, c+dc)
            for dr in range(-1, 2)
            for dc in range(-1, 2)
            if not (dr == 0 and dc == 0)
            and 0 <= r+dr < self.rows
            and 0 <= c+dc < self.cols
        ]

    def _show_chord_preview(self, r: int, c: int):
        """chord 대상 셀들 눌린 미리보기 표시"""
        if self.cell_state[r][c] != STATE_OPEN or self.board[r][c] <= 0:
            return
        for nr, nc in self._neighbors(r, c):
            if self.cell_state[nr][nc] == STATE_CLOSED:
                self._draw_pressed(nr, nc)

    def _hide_chord_preview(self, r: int, c: int):
        """chord 미리보기 원상 복귀"""
        if self.cell_state[r][c] != STATE_OPEN:
            return
        for nr, nc in self._neighbors(r, c):
            if self.cell_state[nr][nc] == STATE_CLOSED:
                self._draw_cell(nr, nc)

    def _try_chord(self, r: int, c: int):
        """
        Chord Click 실행:
        열린 숫자 셀 위에서 좌+우 동시 클릭 →
        인접 깃발 수 == 셀 숫자이면 나머지 닫힌 셀 전부 열기.
        지뢰 오픈 시 게임 오버.
        """
        if self.cell_state[r][c] != STATE_OPEN:
            return
        val = self.board[r][c]
        if val <= 0:
            return

        neighbors = self._neighbors(r, c)
        flag_cnt = sum(
            1 for nr, nc in neighbors
            if self.cell_state[nr][nc] == STATE_FLAG
        )

        if flag_cnt != val:
            # 조건 미충족 → 미리보기만 복원 + 힌트 원상복구
            self._hide_chord_preview(r, c)
            self._update_hints_if_active()
            return

        # 조건 충족 → 닫힌 셀 모두 열기
        hit = None
        for nr, nc in neighbors:
            if self.cell_state[nr][nc] == STATE_CLOSED:
                if self.board[nr][nc] == -1:
                    hit = (nr, nc)
                else:
                    self._open_cell(nr, nc)

        if hit:
            self._do_game_over(*hit)
        else:
            self._check_win()
        # 성공/실패 모든 경우 힌트 재계산
        self._update_hints_if_active()

    # ──────────────────────────────────────────
    #  마우스 이벤트
    # ──────────────────────────────────────────
    def _on_lpress(self, event):
        if self.game_over or self.game_won:
            return
        self._left_down = True
        r, c = self._rc(event.x, event.y)
        if r is None:
            return
        self._press_pos = (r, c)
        self.face_btn.config(text="😮")

        if self._right_down:
            # 양쪽 동시: chord 미리보기
            self._show_chord_preview(r, c)
        elif self.cell_state[r][c] == STATE_CLOSED:
            self._draw_pressed(r, c)

    def _on_ldrag(self, event):
        if self.game_over or self.game_won:
            return
        # 이전 셀 복원
        if self._press_pos:
            pr, pc = self._press_pos
            if self._right_down:
                self._hide_chord_preview(pr, pc)
            else:
                self._draw_cell(pr, pc)

        r, c = self._rc(event.x, event.y)
        if r is None:
            self._press_pos = None
            return
        self._press_pos = (r, c)

        if self._right_down:
            self._show_chord_preview(r, c)
        elif self.cell_state[r][c] == STATE_CLOSED:
            self._draw_pressed(r, c)

    def _on_lrelease(self, event):
        self._left_down = False
        self.face_btn.config(text="🙂")
        if self.game_over or self.game_won:
            return

        r, c = self._rc(event.x, event.y)
        if r is None:
            return

        if self._right_down:
            # chord 실행
            self._try_chord(r, c)
            return

        if self.cell_state[r][c] != STATE_CLOSED:
            return

        # 첫 클릭 → 지뢰 배치 + 타이머 시작
        if self.first_click:
            self.first_click = False
            self._place_mines(r, c)
            self._start_timer()

        if self.board[r][c] == -1:
            self._do_game_over(r, c)
        else:
            self._open_cell(r, c)
            self._check_win()
            self._update_hints_if_active()

    def _on_rpress(self, event):
        if self.game_over or self.game_won:
            return
        self._right_down = True
        r, c = self._rc(event.x, event.y)
        if r is None:
            return
        self._press_pos = (r, c)

        if self._left_down:
            # 양쪽 동시: chord 미리보기
            self.face_btn.config(text="😮")
            self._show_chord_preview(r, c)
        # 우클릭만 단독: press 이벤트에서는 아무것도 안 함 (release에서 토글)

    def _on_rdrag(self, event):
        if self.game_over or self.game_won:
            return
        if not self._left_down:
            return  # 우클릭 단독 드래그는 무시
        # 이전 셀 복원
        if self._press_pos:
            self._hide_chord_preview(*self._press_pos)
        r, c = self._rc(event.x, event.y)
        if r is None:
            self._press_pos = None
            return
        self._press_pos = (r, c)
        self._show_chord_preview(r, c)

    def _on_rrelease(self, event):
        self._right_down = False
        if self.game_over or self.game_won:
            return

        r, c = self._rc(event.x, event.y)
        if r is None:
            return

        if self._left_down:
            # chord 실행
            self.face_btn.config(text="🙂")
            self._try_chord(r, c)
            return

        # 우클릭 단독: 깃발 토글
        st = self.cell_state[r][c]
        if st == STATE_OPEN:
            return
        if st == STATE_CLOSED:
            self.cell_state[r][c] = STATE_FLAG
            self.flags_count += 1
        elif st == STATE_FLAG:
            self.cell_state[r][c] = STATE_QUESTION
            self.flags_count -= 1
        elif st == STATE_QUESTION:
            self.cell_state[r][c] = STATE_CLOSED

        self._draw_cell(r, c)
        self.mine_lbl.config(text=self._lcd(self.mine_count - self.flags_count))
        self._update_hints_if_active()

    # ──────────────────────────────────────────
    #  타이머
    # ──────────────────────────────────────────
    def _start_timer(self):
        self.elapsed = 0
        self._tick()

    def _tick(self):
        if self.game_over or self.game_won:
            return
        self.elapsed = min(999, self.elapsed + 1)
        self.timer_lbl.config(text=self._lcd(self.elapsed))
        self._timer_id = self.root.after(1000, self._tick)

    def _stop_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

    # ──────────────────────────────────────────
    #  승리 / 패배
    # ──────────────────────────────────────────
    def _check_win(self):
        if self.open_count >= self.rows * self.cols - self.mine_count:
            self._do_win()

    def _do_win(self):
        self.game_won = True
        self._stop_timer()
        self.face_btn.config(text="😎")

        # 힌트 오버레이 즉시 제거
        self.canvas.delete("hint")
        self._hint_mode = False
        self.hint_btn.config(relief="raised", bg=BG_GRAY)
        self.auto_safe_btn.pack_forget()
        self.auto_flag_btn.pack_forget()

        # 미표시 지뢰에 깃발 자동 설치
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1 and self.cell_state[r][c] != STATE_FLAG:
                    self.cell_state[r][c] = STATE_FLAG
                    self._draw_cell(r, c)
        self.mine_lbl.config(text=self._lcd(0))

        # 최고 기록 처리
        record_msg = ""
        if self.difficulty in self.records:
            prev = self.records[self.difficulty]
            if prev is None or self.elapsed < prev:
                self.records[self.difficulty] = self.elapsed
                save_records(self.records)
                record_msg = f"\n🏆 최고 기록 갱신!  {self.elapsed}초"
            else:
                record_msg = f"\n현재: {self.elapsed}초  |  최고: {prev}초"
        else:
            record_msg = f"\n클리어 시간: {self.elapsed}초"

        t = self.elapsed
        self.root.after(150, lambda: messagebox.showinfo(
            "축하합니다! 🎉",
            f"지뢰찾기 성공!\n클리어 시간: {t}초{record_msg}"
        ))

    def _do_game_over(self, hit_r: int, hit_c: int):
        self.game_over = True
        self._stop_timer()
        self.face_btn.config(text="😵")

        # 힌트 오버레이 즉시 제거
        self.canvas.delete("hint")
        self._hint_mode = False
        self.hint_btn.config(relief="raised", bg=BG_GRAY)
        self.auto_safe_btn.pack_forget()
        self.auto_flag_btn.pack_forget()

        for r in range(self.rows):
            for c in range(self.cols):
                st  = self.cell_state[r][c]
                val = self.board[r][c]
                x0, y0 = self._xy(r, c)
                tag = self._tag(r, c)

                if r == hit_r and c == hit_c:
                    # 밟은 지뢰: 빨간 배경 + 지뢰
                    self.cell_state[r][c] = STATE_OPEN
                    self.canvas.delete(tag)
                    self._draw_mine_hit(x0, y0, tag)

                elif val == -1 and st not in (STATE_FLAG, STATE_OPEN):
                    # 미발견 지뢰: 공개
                    self.cell_state[r][c] = STATE_OPEN
                    self.canvas.delete(tag)
                    self.canvas.create_rectangle(
                        x0, y0, x0+CELL_SIZE, y0+CELL_SIZE,
                        fill=CELL_OPEN, outline=DARK_GRAY, tags=tag
                    )
                    self._draw_mine_normal(x0, y0, tag)

                elif val != -1 and st == STATE_FLAG:
                    # 틀린 깃발: 지뢰 + 빨간 X
                    self.cell_state[r][c] = STATE_OPEN
                    self.canvas.delete(tag)
                    self.canvas.create_rectangle(
                        x0, y0, x0+CELL_SIZE, y0+CELL_SIZE,
                        fill=CELL_OPEN, outline=DARK_GRAY, tags=tag
                    )
                    self._draw_mine_wrong(x0, y0, tag)

    # ──────────────────────────────────────────
    #  힌트 (지뢰 확률 표시)
    # ──────────────────────────────────────────
    def _toggle_hint(self):
        """💡 버튼: 힌트 오버레이 토글"""
        if self.first_click:
            messagebox.showinfo("힌트", "첫 클릭 후 사용할 수 있습니다.")
            return
        self._hint_mode = not self._hint_mode
        if self._hint_mode:
            self.hint_btn.config(relief="sunken", bg="#E0E0B0")
            self.auto_safe_btn.pack(side="right", pady=8, padx=(0, 2))
            self.auto_flag_btn.pack(side="right", pady=8, padx=(0, 2))
            self.auto_play_btn.pack(side="right", pady=8, padx=(0, 2))
            self._show_hints()
        else:
            self.hint_btn.config(relief="raised", bg=BG_GRAY)
            self.auto_safe_btn.pack_forget()
            self.auto_flag_btn.pack_forget()
            self.auto_play_btn.pack_forget()
            self.canvas.delete("hint")

    def _auto_open_safe(self):
        """✔ 0% 확률 셀을 반복적으로 모두 자동 열기 (+ 100% 깃발도 동시)"""
        if self.game_over or self.game_won or self.first_click:
            return
        self._auto_solve_loop()
        self._update_hints_if_active()

    def _auto_flag_mines(self):
        """🚩 100% 확률 셀을 반복적으로 모두 자동 깃발 (+ 0% 열기도 동시)"""
        if self.game_over or self.game_won or self.first_click:
            return
        self._auto_solve_loop()
        self._update_hints_if_active()

    def _auto_solve_loop(self):
        """0%→열기, 100%→깃발을 더 이상 진전 없을 때까지 반복"""
        for _ in range(200):  # 무한루프 방지
            if self.game_over or self.game_won:
                return
            probs = self._calc_probabilities()
            progress = False

            # 100% 깃발
            for (r, c), p in probs.items():
                if round(p * 100) == 100 and self.cell_state[r][c] == STATE_CLOSED:
                    self.cell_state[r][c] = STATE_FLAG
                    self.flags_count += 1
                    self._draw_cell(r, c)
                    progress = True
            if progress:
                self.mine_lbl.config(text=self._lcd(self.mine_count - self.flags_count))

            # 0% 열기
            for (r, c), p in probs.items():
                if round(p * 100) == 0 and self.cell_state[r][c] == STATE_CLOSED:
                    self._open_cell(r, c)
                    progress = True
                    if self.game_over:
                        return

            if progress:
                self._check_win()
            else:
                break  # 더 이상 진전 없음

    def _auto_play(self):
        """🎲 전자동: 안전→깃발→반복→교착 시 ⭐클릭까지 자동 수행"""
        if self.game_over or self.game_won or self.first_click:
            return
        for _ in range(500):  # 무한루프 방지
            if self.game_over or self.game_won:
                break
            # 먼저 확정적 수를 모두 둠
            self._auto_solve_loop()
            if self.game_over or self.game_won:
                break

            # 교착 상태: 최저 확률 셀 자동 클릭 (⭐)
            probs = self._calc_probabilities()
            closed = {(r,c): p for (r,c), p in probs.items()
                      if self.cell_state[r][c] == STATE_CLOSED}
            if not closed:
                break
            best = min(closed, key=lambda k: closed[k])
            r, c = best
            self._open_cell(r, c)
            if self.game_over:
                break
            self._check_win()
        self._update_hints_if_active()

    def _calc_probabilities(self) -> dict:
        """
        완전 열거 (조합 탐색) + 독립 그룹 분리 방식.

        [알고리즘]
        1. 제약 수집
        2. 제약 전파(Propagation): 확정 안전/지뢰 셀 선행 확정
        3. Union-Find 로 독립 그룹 분리
        4. 백트래킹 열거 (노드 한도 초과 시 로컬 추정 폴백)
        5. 그룹 간 Convolution + C(nf,k) 가중치
        6. 셀별 정확 확률 계산
        """
        from math import comb

        MAX_GROUP_SIZE = 100      # 이 이상인 그룹 → MC 샘플링 폴백
        MAX_BT_NODES   = 2_000_000 # 백트래킹 노드 한도 (속도 보호)

        def safe_comb(n, k):
            return comb(n, k) if 0 <= k <= n else 0

        # ── 1. 제약 수집 ──────────────────────────────────
        raw = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_state[r][c] != STATE_OPEN:
                    continue
                val = self.board[r][c]
                if val <= 0:
                    continue
                nbrs  = self._neighbors(r, c)
                flags = sum(1 for nr, nc in nbrs if self.cell_state[nr][nc] == STATE_FLAG)
                cl = frozenset(
                    (nr, nc) for nr, nc in nbrs
                    if self.cell_state[nr][nc] == STATE_CLOSED
                )
                if not cl:
                    continue
                raw.append((val - flags, cl))
        cst_set = list(set(raw))

        total_closed    = sum(1 for r in range(self.rows) for c in range(self.cols)
                              if self.cell_state[r][c] == STATE_CLOSED)
        total_remaining = self.mine_count - self.flags_count
        global_prob     = total_remaining / max(1, total_closed)

        # 제약이 없으면 글로벌 확률
        if not cst_set:
            return {(r, c): global_prob
                    for r in range(self.rows) for c in range(self.cols)
                    if self.cell_state[r][c] == STATE_CLOSED}

        # ── 2. 제약 전파 + Gaussian Elimination ────────────
        defi_safe = set()
        defi_mine = set()
        changed = True
        while changed:
            changed = False

            # (a) 기본 전파: rem=0 → safe, rem=len → mine
            new_cst = []
            for rem, cl in cst_set:
                cl2  = frozenset(c for c in cl if c not in defi_safe and c not in defi_mine)
                rem2 = rem - sum(1 for c in cl if c in defi_mine)
                if rem2 < 0 or rem2 > len(cl2):
                    continue
                if rem2 == 0 and cl2:
                    defi_safe.update(cl2);  changed = True
                elif cl2 and rem2 == len(cl2):
                    defi_mine.update(cl2);  changed = True
                elif cl2:
                    new_cst.append((rem2, cl2))
            cst_set = new_cst

            # (b) Gaussian elimination: 정수 행렬 행 축소
            if not cst_set:
                break

            # 변수(셀) 인덱싱
            all_cells_g = set()
            for _, cl in cst_set:
                all_cells_g.update(cl)
            cell_list = sorted(all_cells_g)
            cell_idx  = {c: i for i, c in enumerate(cell_list)}
            n_vars    = len(cell_list)
            n_rows    = len(cst_set)

            # 행렬 구축: [계수들 | 나머지값]
            matrix = []
            for rem, cl in cst_set:
                row = [0] * (n_vars + 1)
                for c in cl:
                    row[cell_idx[c]] = 1
                row[n_vars] = rem
                matrix.append(row)

            # 정수 가우스 소거 (피벗 열 순서대로)
            pivot_row_idx = 0
            for col in range(n_vars):
                if pivot_row_idx >= n_rows:
                    break
                # 피벗 행 찾기
                pr = None
                for r in range(pivot_row_idx, n_rows):
                    if matrix[r][col] != 0:
                        pr = r
                        break
                if pr is None:
                    continue
                matrix[pivot_row_idx], matrix[pr] = matrix[pr], matrix[pivot_row_idx]
                pv = matrix[pivot_row_idx][col]  # 피벗 값

                # 다른 행에서 이 열 소거
                for r in range(n_rows):
                    if r == pivot_row_idx or matrix[r][col] == 0:
                        continue
                    factor = matrix[r][col]
                    for j in range(n_vars + 1):
                        matrix[r][j] = matrix[r][j] * pv - factor * matrix[pivot_row_idx][j]
                    # GCD 정규화 (계수 폭발 방지)
                    from math import gcd
                    row_gcd = 0
                    for j in range(n_vars + 1):
                        row_gcd = gcd(row_gcd, abs(matrix[r][j]))
                    if row_gcd > 1:
                        for j in range(n_vars + 1):
                            matrix[r][j] //= row_gcd
                pivot_row_idx += 1

            # 축소된 행렬에서 확정 셀 도출
            for row in matrix:
                coeffs = row[:n_vars]
                rem_val = row[n_vars]
                pos_cells = [cell_list[i] for i in range(n_vars) if coeffs[i] > 0]
                neg_cells = [cell_list[i] for i in range(n_vars) if coeffs[i] < 0]
                pos_sum   = sum(coeffs[i] for i in range(n_vars) if coeffs[i] > 0)
                neg_sum   = sum(-coeffs[i] for i in range(n_vars) if coeffs[i] < 0)

                if not pos_cells and not neg_cells:
                    continue

                # sum(pos*x) - sum(neg*x) = rem_val
                # 최솟값: 0 - neg_sum = -neg_sum
                # 최댓값: pos_sum - 0 = pos_sum

                if len(pos_cells) + len(neg_cells) == 0:
                    continue

                # 모든 계수가 +1인 경우 (서브셋 추론 포함)
                if not neg_cells and all(coeffs[cell_idx[c]] == 1 for c in pos_cells):
                    if rem_val == 0:
                        defi_safe.update(pos_cells); changed = True
                    elif rem_val == len(pos_cells):
                        defi_mine.update(pos_cells); changed = True

                # 단일 변수: coeff * x = rem → x = rem / coeff
                non_zero = [(i, coeffs[i]) for i in range(n_vars) if coeffs[i] != 0]
                if len(non_zero) == 1:
                    i, c = non_zero[0]
                    if c != 0 and rem_val % c == 0:
                        v = rem_val // c
                        if v == 0:
                            defi_safe.add(cell_list[i]); changed = True
                        elif v == 1:
                            defi_mine.add(cell_list[i]); changed = True

                # ±1 혼합: 극단값 체크
                # pos_cells 전부 1 + neg_cells 전부 0 → rem = pos_sum
                # pos_cells 전부 0 + neg_cells 전부 1 → rem = -neg_sum
                if pos_cells and neg_cells:
                    if rem_val == pos_sum:
                        # pos 전부 mine, neg 전부 safe
                        defi_mine.update(pos_cells); changed = True
                        defi_safe.update(neg_cells); changed = True
                    elif rem_val == -neg_sum:
                        # pos 전부 safe, neg 전부 mine
                        defi_safe.update(pos_cells); changed = True
                        defi_mine.update(neg_cells); changed = True

        # ── 3. 확정 셀 제외 후 frontier 재구성 ──────────
        frontier = set()
        for _, cl in cst_set:
            frontier.update(cl)

        # ── 4. Union-Find 그룹 분리 ──────────────────────
        parent = {cell: cell for cell in frontier}
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for _, cl in cst_set:
            it = iter(cl); f = next(it)
            for cell in it:
                union(f, cell)

        groups = {}
        for cell in frontier:
            groups.setdefault(find(cell), []).append(cell)
        group_cst = {root: [] for root in groups}
        for rem, cl in cst_set:
            group_cst[find(next(iter(cl)))].append((rem, cl))

        # ── 5. 그룹 백트래킹 열거 ─────────────────────────
        def enumerate_group(cells, cst, randomize=False):
            n       = len(cells)
            cst_cnt = {cell: 0 for cell in cells}
            for _, cl in cst:
                for c in cl:
                    cst_cnt[c] += 1
            cells = sorted(cells, key=lambda c: -cst_cnt[c])

            idx_map = {cell: i for i, cell in enumerate(cells)}
            cell_cst_idx = [[] for _ in range(n)]
            cst_list     = []
            for ci, (rem, cl) in enumerate(cst):
                cst_list.append((rem, cl))
                for c in cl:
                    cell_cst_idx[idx_map[c]].append(ci)

            assignment = [0] * n
            results    = []
            nodes      = [0]
            aborted    = [False]

            def bt(pos, mines):
                if aborted[0]:
                    return
                nodes[0] += 1
                if nodes[0] > MAX_BT_NODES:
                    aborted[0] = True
                    return
                if pos == n:
                    results.append((tuple(assignment), mines))
                    return
                vals = (0, 1)
                if randomize:
                    import random as _rng
                    vals = (0, 1) if _rng.random() < 0.5 else (1, 0)
                for val in vals:
                    ok = True
                    for ci in cell_cst_idx[pos]:
                        rem, cl = cst_list[ci]
                        m = u = 0
                        for c in cl:
                            j = idx_map[c]
                            if   j < pos:  m += assignment[j]
                            elif j == pos: m += val
                            else:          u += 1
                        if m > rem or (rem - m) > u:
                            ok = False; break
                    if ok:
                        assignment[pos] = val
                        bt(pos + 1, mines + val)
                        assignment[pos] = 0

            bt(0, 0)
            if not results:
                return None
            return (results, cells)  # (배치목록, 정렬된셀)

        # ── 6. 그룹별 계산 ───────────────────────────────
        group_data     = {}
        fallback_cells = set()

        for root, cells in groups.items():
            if len(cells) > MAX_GROUP_SIZE:
                # 대그룹: 부분 열거 (randomize로 편향 감소)
                result = enumerate_group(cells, group_cst[root], randomize=True)
                if result is not None:
                    group_data[root] = (result[1], result[0])
                else:
                    fallback_cells.update(cells)
                continue
            result = enumerate_group(cells, group_cst[root])
            if result is None:
                fallback_cells.update(cells)
                continue
            sorted_cells, configs = result[1], result[0]
            group_data[root] = (sorted_cells, configs)

        # ── 7. Convolution + C(nf,k) 가중치 ─────────────
        def convolve(d1, d2):
            out = {}
            for m1, c1 in d1.items():
                for m2, c2 in d2.items():
                    k = m1 + m2
                    out[k] = out.get(k, 0) + c1 * c2
            return out

        total_dist  = {0: 1}
        group_dists = {}
        for root, (_, configs) in group_data.items():
            d = {}
            for _, mc in configs:
                d[mc] = d.get(mc, 0) + 1
            group_dists[root] = d
            total_dist = convolve(total_dist, d)

        adj_nf = max(0, (total_closed - len(frontier) - len(defi_safe) - len(defi_mine))
                     + len(fallback_cells))

        total_weight = sum(
            cnt * safe_comb(adj_nf, total_remaining - len(defi_mine) - m)
            for m, cnt in total_dist.items()
        )

        probs = {}
        for cell in defi_safe:
            probs[cell] = 0.0
        for cell in defi_mine:
            probs[cell] = 1.0

        if total_weight > 0:
            for j_root, (j_cells, j_configs) in group_data.items():
                j_map = {cell: i for i, cell in enumerate(j_cells)}
                other_dist = {0: 1}
                for k_root, k_dist in group_dists.items():
                    if k_root != j_root:
                        other_dist = convolve(other_dist, k_dist)

                rem_base = total_remaining - len(defi_mine)
                for cell in j_cells:
                    ci = j_map[cell]
                    mine_w = sum(
                        c_o * safe_comb(adj_nf, rem_base - m_j - m_o)
                        for asgn, m_j in j_configs if asgn[ci] == 1
                        for m_o, c_o in other_dist.items()
                    )
                    probs[cell] = mine_w / total_weight

            # 비-frontier / fallback 셀 확률
            rem_base = total_remaining - len(defi_mine)
            nf_w = sum(cnt * safe_comb(adj_nf - 1, rem_base - m - 1)
                       for m, cnt in total_dist.items()) if adj_nf > 0 else 0
            nf_prob = nf_w / total_weight if adj_nf > 0 else 0.0
        else:
            nf_prob = global_prob

        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_state[r][c] != STATE_CLOSED:
                    continue
                cell = (r, c)
                if cell not in probs:
                    probs[cell] = nf_prob

        return probs

    def _show_hints(self):
        """힌트 오버레이를 캔버스에 그림 (태그 'hint')"""
        self.canvas.delete("hint")
        if self.first_click or self.game_over or self.game_won:
            return

        probs    = self._calc_probabilities()
        fs       = max(9, CELL_SIZE // 5)       # 폰트 크기
        fs_small = max(7, CELL_SIZE // 7)       # 작은 폰트 (글로벌 확률용)

        # 0% 셀이 없을 경우, 최저 확률 셀을 '추천 클릭' 셀로 표시
        has_safe = any(round(p * 100) == 0 for p in probs.values())
        best_cell = None
        if not has_safe and probs:
            min_p = min(probs.values())
            if round(min_p * 100) < 100:  # 전부 100%가 아닐 때만
                best_cell = min(probs, key=lambda k: probs[k])

        for (r, c), p in probs.items():
            x0, y0 = self._xy(r, c)
            cx = x0 + CELL_SIZE // 2
            cy = y0 + CELL_SIZE // 2

            pct = round(p * 100)

            if (r, c) == best_cell:
                # ⭐ 추천 셀 — 가장 낮은 확률
                text  = f"⭐{pct}%"
                color = "#0088FF"   # 밝은 파랑
                font  = ("Arial", fs, "bold")
            elif pct == 0:
                text  = "✓"
                color = "#00CC00"   # 밝은 초록 — 안전
                font  = ("Arial", fs, "bold")
            elif pct == 100:
                text  = "💣"
                color = "#CC0000"   # 진한 빨강 — 지뢰 확실
                font  = ("Segoe UI Emoji", fs)
            elif pct <= 25:
                text  = f"{pct}%"
                color = "#33AA00"   # 초록
                font  = ("Arial", fs, "bold")
            elif pct <= 50:
                text  = f"{pct}%"
                color = "#BB9900"   # 노랑
                font  = ("Arial", fs, "bold")
            elif pct <= 75:
                text  = f"{pct}%"
                color = "#FF6600"   # 주황
                font  = ("Arial", fs, "bold")
            else:
                text  = f"{pct}%"
                color = "#FF1100"   # 빨강
                font  = ("Arial", fs, "bold")

            self.canvas.create_text(
                cx, cy, text=text, font=font, fill=color, tags="hint"
            )

    def _update_hints_if_active(self):
        """힌트 모드가 켜져 있으면 자동 갱신"""
        if self._hint_mode and not self.first_click:
            self._show_hints()

    # ──────────────────────────────────────────
    #  새 게임 / 난이도
    # ──────────────────────────────────────────
    def _new_game(self):
        self._stop_timer()
        if self.difficulty in DIFFICULTIES:
            self.rows, self.cols, self.mine_count = DIFFICULTIES[self.difficulty]
        self._init_game()

    def _set_difficulty(self, diff: str):
        self.difficulty = diff
        self.diff_var.set(diff)
        self.rows, self.cols, self.mine_count = DIFFICULTIES[diff]
        self._stop_timer()
        self._init_game()

    def _custom_difficulty(self):
        dlg = CustomDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.result:
            self.difficulty = "사용자 정의"
            self.rows       = dlg.result["rows"]
            self.cols       = dlg.result["cols"]
            self.mine_count = dlg.result["mines"]
            self._stop_timer()
            self._init_game()

    # ──────────────────────────────────────────
    #  최고 기록
    # ──────────────────────────────────────────
    def _show_records(self):
        lines = ["🏆 난이도별 최고 기록", "─" * 22]
        for diff in ["초급", "중급", "고급"]:
            val = self.records.get(diff)
            record_str = f"{val}초" if val is not None else "기록 없음"
            lines.append(f"  {diff}  :  {record_str}")
        lines.append("─" * 22)
        messagebox.showinfo("최고 기록", "\n".join(lines))


# ─────────────────────────────────────────────
#  사용자 정의 난이도 다이얼로그
# ─────────────────────────────────────────────
class CustomDialog:
    def __init__(self, parent: tk.Tk):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("사용자 정의")
        self.top.resizable(False, False)
        self.top.configure(bg=BG_GRAY)
        self.top.grab_set()
        self.top.minsize(600, 420)   # 다이얼로그 최소 크기 고정

        F_TITLE = ("맑은 고딕", 26, "bold")
        F_LABEL = ("맑은 고딕", 22)
        F_ENTRY = ("맑은 고딕", 22)
        F_BTN   = ("맑은 고딕", 20)

        tk.Label(self.top, text="사용자 정의 난이도",
                 font=F_TITLE,
                 bg=BG_GRAY).grid(row=0, column=0, columnspan=2, pady=(28, 16), padx=40)

        specs = [
            ("높이 (행, 9~24):", "9"),
            ("너비 (열, 9~30):", "9"),
            ("지뢰 수:",         "10"),
        ]
        self.vars = []
        for i, (label, default) in enumerate(specs):
            tk.Label(self.top, text=label, bg=BG_GRAY,
                     font=F_LABEL).grid(row=i+1, column=0, sticky="e", padx=24, pady=12)
            var = tk.StringVar(value=default)
            tk.Entry(self.top, textvariable=var, width=8, justify="center",
                     font=F_ENTRY).grid(
                row=i+1, column=1, padx=24, pady=12)
            self.vars.append(var)

        bf = tk.Frame(self.top, bg=BG_GRAY)
        bf.grid(row=4, column=0, columnspan=2, pady=28)
        tk.Button(bf, text="확인", width=10, command=self._ok,
                  font=F_BTN, bg=BG_GRAY, relief="raised", bd=3).pack(side="left", padx=14)
        tk.Button(bf, text="취소", width=10, command=self.top.destroy,
                  font=F_BTN, bg=BG_GRAY, relief="raised", bd=3).pack(side="left", padx=14)

        self.top.bind("<Return>", lambda e: self._ok())
        self.top.bind("<Escape>", lambda e: self.top.destroy())

    def _ok(self):
        try:
            rows  = int(self.vars[0].get())
            cols  = int(self.vars[1].get())
            mines = int(self.vars[2].get())
        except ValueError:
            messagebox.showerror("오류", "숫자만 입력하세요.", parent=self.top)
            return

        rows  = max(9, min(24, rows))
        cols  = max(9, min(30, cols))
        mines = max(1, min(rows * cols - 9, mines))

        self.result = {"rows": rows, "cols": cols, "mines": mines}
        self.top.destroy()


# ─────────────────────────────────────────────
#  진입점
# ─────────────────────────────────────────────
def main():
    root = tk.Tk()

    # DPI 인식 (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    Minesweeper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
