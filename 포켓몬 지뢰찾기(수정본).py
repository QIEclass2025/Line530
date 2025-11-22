import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import requests
from io import BytesIO
from PIL import Image, ImageTk

# --- 기본 상수 (초기값) ---
DEFAULT_BOARD_SIZE = 10
DEFAULT_NUM_MINES = 15
DEFAULT_BUTTON_SIZE = 24
DEFAULT_LARGE_IMG_SIZE = 96
DEFAULT_HINTS = 3

# --- 색상 설정 ---
COLORS = {
    1: '#0000FF', 2: '#008200', 3: '#FF0000', 4: '#000084',
    5: '#840000', 6: '#008284', 7: '#840084', 8: '#000000',
}
BG_COLOR_REVEALED = '#D0D0D0'


class MinesweeperGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("포켓몬 지뢰찾기 FINAL + 타이머")
        self.master.resizable(True, True)

        # 게임 설정 값 (변경 가능)
        self.board_size = DEFAULT_BOARD_SIZE
        self.num_mines = DEFAULT_NUM_MINES
        self.button_size = DEFAULT_BUTTON_SIZE
        self.large_img_size = DEFAULT_LARGE_IMG_SIZE
        self.hints_per_game = DEFAULT_HINTS

        # 타이머 관련
        self.timer_limit = None      # 제한 시간(초), None이면 끔
        self.remaining_time = None   # 남은 시간(초)
        self.timer_job = None        # after 작업 ID
        self.timer_running = False   # 타이머 동작 여부

        self.images = {}
        self.images_loaded_successfully = False
        self.load_all_assets()

        self.create_widgets()
        self.start_new_game()

    # ---------------- 자원 로딩 -----------------
    def _load_image_from_url(self, url, size):
        try:
            response = requests.get(url)
            response.raise_for_status()
            img_data = response.content
            img = Image.open(BytesIO(img_data)).resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Warning: Could not load image from {url}: {e}")
            return None

    def load_all_assets(self):
        """게임에 필요한 모든 이미지를 준비하고, 한글 이름을 가져옵니다."""
        # 버튼 기본 이미지들
        self.images['bush'] = ImageTk.PhotoImage(
            Image.new('RGBA', (self.button_size, self.button_size), (34, 177, 76, 255))
        )
        self.images['blank'] = ImageTk.PhotoImage(
            Image.new('RGBA', (self.button_size, self.button_size), (0, 0, 0, 0))
        )
        self.images['flag'] = self._load_image_from_url(
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/master-ball.png",
            (self.button_size, self.button_size)
        )

        # 포켓몬 이미지/이름
        self.images['pokemon'] = []
        try:
            response = requests.get("https://pokeapi.co/api/v2/pokemon?limit=151")
            response.raise_for_status()
            pokemon_list = response.json()['results']

            count = min(self.num_mines, len(pokemon_list))
            selected_pokemon = random.sample(pokemon_list, count)

            for pokemon in selected_pokemon:
                poke_id = pokemon['url'].split('/')[-2]

                # 한글 이름 가져오기
                kor_name = pokemon['name'].capitalize()
                try:
                    species_res = requests.get(f"https://pokeapi.co/api/v2/pokemon-species/{poke_id}")
                    species_res.raise_for_status()
                    species_data = species_res.json()
                    for name_entry in species_data['names']:
                        if name_entry['language']['name'] == 'ko':
                            kor_name = name_entry['name']
                            break
                except requests.exceptions.RequestException as e:
                    print(f"Could not fetch Korean name for {poke_id}: {e}")

                # 이미지 가져오기
                url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{poke_id}.png"
                small_img = self._load_image_from_url(url, (self.button_size, self.button_size))
                large_img = self._load_image_from_url(url, (self.large_img_size, self.large_img_size))

                if small_img and large_img:
                    self.images['pokemon'].append((small_img, large_img, kor_name))

            if len(self.images['pokemon']) == count:
                self.images_loaded_successfully = True
            else:
                self.images_loaded_successfully = False

        except requests.exceptions.RequestException:
            self.images_loaded_successfully = False

    # ---------------- 위젯 구성 -----------------
    def create_widgets(self):
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(pady=5, fill=tk.X)

        self.status_label = tk.Label(self.top_frame, text="", font=('Helvetica', 12))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # 타이머 라벨
        self.timer_label = tk.Label(self.top_frame, text="타이머: 끔", font=('Helvetica', 12))
        self.timer_label.pack(side=tk.LEFT, padx=10)

        self.hint_button = tk.Button(self.top_frame, text="힌트 사용", command=self.use_hint)
        self.hint_button.pack(side=tk.LEFT, padx=5)

        # 오른쪽 버튼들
        self.settings_button = tk.Button(self.top_frame, text="설정", command=self.open_settings_window)
        self.settings_button.pack(side=tk.RIGHT, padx=5)

        self.timer_button = tk.Button(self.top_frame, text="타이머 설정", command=self.set_timer_limit)
        self.timer_button.pack(side=tk.RIGHT, padx=5)

        self.restart_button = tk.Button(self.top_frame, text="다시 시작", command=self.start_new_game)
        self.restart_button.pack(side=tk.RIGHT, padx=5)

        self.board_frame = tk.Frame(self.master, bd=2, relief=tk.SUNKEN)
        self.board_frame.pack(padx=10, pady=10)

    # ---------------- 게임 로직 -----------------
    def start_new_game(self):
        # 기존 보드 정리
        for widget in self.board_frame.winfo_children():
            widget.destroy()

        # 타이머 리셋
        if self.timer_job is not None:
            self.master.after_cancel(self.timer_job)
            self.timer_job = None
        self.timer_running = False
        self.remaining_time = self.timer_limit
        self.update_timer_label()

        self.game_over = False
        self.first_click = True
        self.flags_placed = 0
        self.hints_left = self.hints_per_game
        self.hint_button.config(state=tk.NORMAL if self.hints_left > 0 else tk.DISABLED)

        self.update_status_label()

        # 버튼(타일) 생성
        self.buttons = []
        for r in range(self.board_size):
            row_buttons = []
            for c in range(self.board_size):
                button = tk.Button(
                    self.board_frame,
                    width=self.button_size,
                    height=self.button_size,
                    image=self.images.get('bush'),
                    relief=tk.RAISED,
                    bd=1
                )
                button.bind('<Button-1>', lambda e, r=r, c=c: self.on_left_click(r, c))
                button.bind('<Button-3>', lambda e, r=r, c=c: self.on_right_click(r, c))
                button.grid(row=r, column=c)
                row_buttons.append(button)
            self.buttons.append(row_buttons)

    def _initialize_board(self, safe_row, safe_col):
        self.mine_board = [[0 for _ in range(self.board_size)] for _ in range(self.board_size)]

        # 첫 클릭 주변(3x3)은 지뢰 금지
        possible_mine_locations = [
            (r, c)
            for r in range(self.board_size)
            for c in range(self.board_size)
            if abs(r - safe_row) > 1 or abs(c - safe_col) > 1
        ]

        max_mines = len(possible_mine_locations)
        actual_mines = min(self.num_mines, max_mines)
        if actual_mines < self.num_mines:
            messagebox.showwarning(
                "설정 조정",
                f"현재 보드 크기에서는 지뢰를 최대 {actual_mines}개까지만 놓을 수 있어요.\n"
                f"지뢰 수를 {actual_mines}개로 조정합니다."
            )
        self.mines_this_game = actual_mines

        mine_locations = random.sample(possible_mine_locations, actual_mines)

        # 포켓몬 또는 'P'로 지뢰 채우기
        if self.images_loaded_successfully and len(self.images.get('pokemon', [])) >= actual_mines:
            mines_to_place = self.images['pokemon'][:actual_mines]
        else:
            mines_to_place = ['P'] * actual_mines
            if not self.images_loaded_successfully:
                messagebox.showwarning(
                    "네트워크 오류",
                    "포켓몬 이미지를 불러오지 못했습니다. 지뢰는 텍스트('P')로 표시됩니다."
                )

        random.shuffle(mines_to_place)

        for (r, c), mine in zip(mine_locations, mines_to_place):
            self.mine_board[r][c] = mine

        # 숫자 칸 계산
        for r in range(self.board_size):
            for c in range(self.board_size):
                if isinstance(self.mine_board[r][c], (tuple, str)):
                    continue
                count = 0
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        nr, nc = r + i, c + j
                        if 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                            cell = self.mine_board[nr][nc]
                            if isinstance(cell, (tuple, str)):
                                count += 1
                self.mine_board[r][c] = count

        self.update_status_label()

    # ---------------- 입력 처리 -----------------
    def on_left_click(self, r, c):
        if self.game_over:
            return
        button = self.buttons[r][c]
        if button.cget('image') == str(self.images.get('flag')):
            return

        if self.first_click:
            self._initialize_board(r, c)
            self.first_click = False
            self.start_timer_if_needed()

        cell_value = self.mine_board[r][c]

        if isinstance(cell_value, (tuple, str)):
            # 지뢰 클릭 -> 게임 오버
            self.reveal_all_mines(loss=True, triggered_cell=(r, c))
            self.end_game(won=False, mine_data=cell_value)
            return

        self.reveal_cell(r, c)

        if self.check_win():
            # 승리 시에도 지뢰 자동 공개
            self.reveal_all_mines(loss=False)
            self.end_game(won=True)

    def on_right_click(self, r, c):
        if self.game_over or self.buttons[r][c]['state'] == 'disabled':
            return
        button = self.buttons[r][c]
        current_image = button.cget('image')

        if current_image == str(self.images.get('bush')):
            button.config(image=self.images.get('flag', self.images['blank']))
            self.flags_placed += 1
        elif current_image == str(self.images.get('flag')):
            button.config(image=self.images['bush'])
            self.flags_placed -= 1

        self.update_status_label()

    # ---------------- 셀 공개/체크 -----------------
    def reveal_cell(self, r, c):
        if not (0 <= r < self.board_size and 0 <= c < self.board_size):
            return
        button = self.buttons[r][c]
        if button['state'] == 'disabled':
            return

        cell_value = self.mine_board[r][c]

        button.config(state='disabled', relief=tk.SUNKEN, bg=BG_COLOR_REVEALED)
        if isinstance(cell_value, int) and cell_value > 0:
            button.config(
                image=self.images['blank'],
                text=str(cell_value),
                font=('Helvetica', 10, 'bold'),
                fg=COLORS.get(cell_value),
                compound='center'
            )
        elif isinstance(cell_value, int) and cell_value == 0:
            button.config(image=self.images['blank'], text='')
            for i in range(-1, 2):
                for j in range(-1, 2):
                    self.reveal_cell(r + i, c + j)

    def reveal_all_mines(self, loss=True, triggered_cell=None):
        """게임 종료 시 모든 지뢰를 보여준다.
        loss=True면 패배 연출(분홍색), False면 승리 연출(황금색)을 사용."""
        if not hasattr(self, 'mine_board'):
            return
        for r in range(self.board_size):
            for c in range(self.board_size):
                cell_value = self.mine_board[r][c]
                if isinstance(cell_value, (tuple, str)):
                    button = self.buttons[r][c]
                    if isinstance(cell_value, str):  # Fallback 'P'
                        button.config(
                            text='P',
                            image=self.images['blank'],
                            compound='center',
                            bg='#FFB6C1' if loss else '#FFFACD'
                        )
                    else:  # Pokemon Image Tuple
                        button.config(
                            image=cell_value[0],
                            bg='#FFB6C1' if loss else '#FFFACD'
                        )

        # 지뢰를 밟은 칸은 붉게 표시
        if loss and triggered_cell:
            tr, tc = triggered_cell
            self.buttons[tr][tc].config(bg='red')

    # ---------------- 게임 종료/상태 -----------------
    def end_game(self, won, mine_data=None, reason=None):
        self.game_over = True
        self.hint_button.config(state=tk.DISABLED)

        # 타이머 정지
        self.timer_running = False
        if self.timer_job is not None:
            self.master.after_cancel(self.timer_job)
            self.timer_job = None
        self.update_timer_label()

        # 커스텀 게임오버 팝업 (이미지 + 메시지 통합)
        popup = tk.Toplevel(self.master)
        popup.title("게임 종료")
        popup.transient(self.master)
        popup.grab_set()
        popup.minsize(320, 200)

        frame = tk.Frame(popup, bg="white")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 상단 이미지 (패배 + 지뢰 클릭일 때만)
        if not won and reason != "timeout" and isinstance(mine_data, tuple):
            img_label = tk.Label(frame, image=mine_data[1], bg="white")
            img_label.image = mine_data[1]
            img_label.pack(pady=(0, 10))

        # 메시지 구성
        if reason == "timeout":
            message = "시간 초과! 포켓몬에게 들키기 전에 탈출 실패!"
        else:
            if won:
                message = "축하합니다! 모든 포켓몬을 피했습니다!"
            else:
                pokemon_name = mine_data[2] if isinstance(mine_data, tuple) else "포켓몬"
                message = f"이런! 야생의 {pokemon_name}와(과) 마주쳤습니다!"

        msg_label = tk.Label(frame, text=message, bg="white", font=("Helvetica", 12))
        msg_label.pack(pady=(0, 10))

        # 버튼들
        btn_frame = tk.Frame(frame, bg="white")
        btn_frame.pack(pady=(10, 0))

        def restart_and_close():
            popup.destroy()
            self.start_new_game()

        restart_btn = tk.Button(btn_frame, text="다시 시작", command=restart_and_close)
        restart_btn.pack(side=tk.LEFT, padx=5)

        close_btn = tk.Button(btn_frame, text="닫기", command=popup.destroy)
        close_btn.pack(side=tk.LEFT, padx=5)

    def check_win(self):
        revealed_count = sum(
            1
            for r in range(self.board_size)
            for c in range(self.board_size)
            if self.buttons[r][c]['state'] == 'disabled'
        )
        total_cells = self.board_size * self.board_size
        return revealed_count == total_cells - getattr(self, "mines_this_game", self.num_mines)

    def update_status_label(self):
        remaining_mines = getattr(self, "mines_this_game", self.num_mines) - self.flags_placed
        remaining_mines = max(remaining_mines, 0)
        self.status_label.config(
            text=f"포켓몬(지뢰): {remaining_mines} / 힌트: {self.hints_left if hasattr(self, 'hints_left') else self.hints_per_game}"
        )

    # ---------------- 트위스트: 힌트 기능 -----------------
    def use_hint(self):
        """아직 열리지 않은 안전한 칸을 하나 자동으로 열어주는 힌트."""
        if self.game_over:
            return
        if self.first_click:
            messagebox.showinfo("힌트", "먼저 칸을 하나 클릭해서 게임을 시작하세요!")
            return
        if self.hints_left <= 0:
            return

        # 아직 안 열린 안전한 칸 목록
        safe_cells = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.buttons[r][c]['state'] != 'disabled':
                    cell_value = self.mine_board[r][c]
                    if isinstance(cell_value, int):  # 숫자 or 0 이면 안전
                        safe_cells.append((r, c))

        if not safe_cells:
            return

        r, c = random.choice(safe_cells)
        self.reveal_cell(r, c)
        self.hints_left -= 1
        if self.hints_left <= 0:
            self.hint_button.config(state=tk.DISABLED)
        self.update_status_label()

        if self.check_win():
            self.reveal_all_mines(loss=False)
            self.end_game(won=True)

    # ---------------- 설정창 -----------------
    def open_settings_window(self):
        win = tk.Toplevel(self.master)
        win.title("게임 설정")
        win.transient(self.master)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="보드 크기 (NxN)").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        board_size_var = tk.IntVar(value=self.board_size)
        tk.Spinbox(win, from_=5, to=20, textvariable=board_size_var, width=5).grid(
            row=0, column=1, padx=10, pady=5
        )

        tk.Label(win, text="포켓몬(지뢰) 수").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        mine_var = tk.IntVar(value=self.num_mines)
        tk.Spinbox(win, from_=1, to=300, textvariable=mine_var, width=5).grid(
            row=1, column=1, padx=10, pady=5
        )

        tk.Label(win, text="타일 크기 (픽셀)").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        tile_var = tk.IntVar(value=self.button_size)
        tk.Spinbox(win, from_=18, to=48, textvariable=tile_var, width=5).grid(
            row=2, column=1, padx=10, pady=5
        )

        tk.Label(win, text="힌트 개수").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        hint_var = tk.IntVar(value=self.hints_per_game)
        tk.Spinbox(win, from_=0, to=10, textvariable=hint_var, width=5).grid(
            row=3, column=1, padx=10, pady=5
        )

        def apply_settings():
            try:
                new_board = int(board_size_var.get())
                new_mines = int(mine_var.get())
                new_tile = int(tile_var.get())
                new_hints = int(hint_var.get())
            except ValueError:
                messagebox.showerror("설정 오류", "모든 값은 정수여야 합니다.")
                return

            if new_board < 5:
                new_board = 5
            if new_board > 20:
                new_board = 20

            # 보드 크기에 맞는 최대 지뢰 수 (첫 클릭 주변 3x3 제외)
            max_mines = max(new_board * new_board - 9, 1)
            if new_mines > max_mines:
                messagebox.showwarning(
                    "설정 조정",
                    f"이 보드에서는 지뢰를 최대 {max_mines}개까지만 둘 수 있어요.\n"
                    f"지뢰 수를 {max_mines}개로 조정합니다."
                )
                new_mines = max_mines
            if new_mines < 1:
                new_mines = 1

            if new_tile < 18:
                new_tile = 18
            if new_tile > 48:
                new_tile = 48

            if new_hints < 0:
                new_hints = 0
            if new_hints > 10:
                new_hints = 10

            self.board_size = new_board
            self.num_mines = new_mines
            self.button_size = new_tile
            self.large_img_size = max(new_tile * 3, 72)
            self.hints_per_game = new_hints

            # 이미지 다시 로딩 후 새 게임 시작
            self.load_all_assets()
            self.start_new_game()
            win.destroy()

        btn_frame = tk.Frame(win)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

        tk.Button(btn_frame, text="적용", command=apply_settings).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="취소", command=win.destroy).pack(side=tk.LEFT, padx=5)

    # ---------------- 타이머 설정/동작 -----------------
    def set_timer_limit(self):
        """타이머 제한 시간을 초 단위로 설정. 0 또는 취소 시 타이머 끔."""
        value = simpledialog.askinteger(
            "타이머 설정",
            "제한 시간을 초 단위로 입력하세요.\n0 또는 취소: 타이머 끄기",
            minvalue=0,
        )
        if value is None:
            return

        if value <= 0:
            self.timer_limit = None
        else:
            self.timer_limit = value

        # 새 설정으로 새 게임 시작
        self.start_new_game()

    def update_timer_label(self):
        """타이머 라벨에 현재 상태를 표시."""
        if self.timer_limit is None or self.timer_limit <= 0:
            self.timer_label.config(text="타이머: 끔")
            return

        remaining = self.remaining_time if self.remaining_time is not None else self.timer_limit
        self.timer_label.config(text=f"남은 시간: {remaining}초")

    def start_timer_if_needed(self):
        """첫 클릭 이후 타이머 시작."""
        if self.timer_limit is None or self.timer_limit <= 0:
            return
        if self.timer_running:
            return

        self.remaining_time = self.timer_limit
        self.timer_running = True
        self._tick_timer()

    def _tick_timer(self):
        """1초마다 호출되는 타이머 콜백."""
        if not self.timer_running or self.game_over:
            return
        if self.remaining_time is None:
            return

        self.update_timer_label()

        if self.remaining_time <= 0:
            # 시간 초과
            self.timer_running = False
            self.update_timer_label()
            # 남은 지뢰 표시 후 시간 초과 패배 처리
            self.reveal_all_mines(loss=True)
            self.end_game(won=False, mine_data=None, reason="timeout")
            return

        self.remaining_time -= 1
        self.timer_job = self.master.after(1000, self._tick_timer)


if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk  # noqa: F401
    except ImportError:
        messagebox.showerror("라이브러리 필요", "Pillow 라이브러리가 필요합니다: pip install Pillow")
        exit()
    root = tk.Tk()
    game = MinesweeperGUI(root)
    root.mainloop()
