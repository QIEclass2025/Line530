import tkinter as tk
from tkinter import messagebox
import random
import requests
from io import BytesIO
from PIL import Image, ImageTk

# --- 상수 정의 ---
BOARD_SIZE = 10
NUM_MINES = 15
BUTTON_SIZE = 24
LARGE_IMG_SIZE = 96

# --- 색상 설정 ---
COLORS = {
    1: '#0000FF', 2: '#008200', 3: '#FF0000', 4: '#000084',
    5: '#840000', 6: '#008284', 7: '#840084', 8: '#000000',
}
BG_COLOR_REVEALED = '#D0D0D0'

class MinesweeperGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("포켓몬 지뢰찾기 FINAL")
        self.master.resizable(True, True)

        self.images = {}
        self.images_loaded_successfully = False
        self.load_all_assets()

        self.create_widgets()
        self.start_new_game()

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
        self.images['bush'] = ImageTk.PhotoImage(Image.new('RGBA', (BUTTON_SIZE, BUTTON_SIZE), (34, 177, 76, 255)))
        self.images['flag'] = self._load_image_from_url("https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/master-ball.png", (BUTTON_SIZE, BUTTON_SIZE))
        self.images['blank'] = ImageTk.PhotoImage(Image.new('RGBA', (BUTTON_SIZE, BUTTON_SIZE), (0, 0, 0, 0)))

        self.images['pokemon'] = []
        try:
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon?limit=151")
            response.raise_for_status()
            pokemon_list = response.json()['results']
            selected_pokemon = random.sample(pokemon_list, NUM_MINES)
            
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
                small_img = self._load_image_from_url(url, (BUTTON_SIZE, BUTTON_SIZE))
                large_img = self._load_image_from_url(url, (LARGE_IMG_SIZE, LARGE_IMG_SIZE))
                
                if small_img and large_img:
                    self.images['pokemon'].append((small_img, large_img, kor_name))
            
            if len(self.images['pokemon']) == NUM_MINES:
                self.images_loaded_successfully = True

        except requests.exceptions.RequestException:
            self.images_loaded_successfully = False

    def create_widgets(self):
        self.top_frame = tk.Frame(self.master)
        self.top_frame.pack(pady=5)
        self.status_label = tk.Label(self.top_frame, text=f"포켓몬: {NUM_MINES}", font=('Helvetica', 12))
        self.status_label.pack(side=tk.LEFT, padx=10)
        self.restart_button = tk.Button(self.top_frame, text="다시 시작", command=self.start_new_game)
        self.restart_button.pack(side=tk.RIGHT, padx=10)

        self.board_frame = tk.Frame(self.master, bd=2, relief=tk.SUNKEN)
        self.board_frame.pack(padx=10, pady=10)

    def start_new_game(self):
        if not self.images['pokemon']:
            self.load_all_assets()
            if not self.images_loaded_successfully:
                 messagebox.showwarning("네트워크 오류", "포켓몬 이미지를 불러오지 못했습니다. 지뢰는 텍스트('P')로 표시됩니다.")

        for widget in self.board_frame.winfo_children():
            widget.destroy()

        self.game_over = False
        self.first_click = True
        self.flags_placed = 0
        self.update_status_label()
        
        self.buttons = []
        for r in range(BOARD_SIZE):
            row_buttons = []
            for c in range(BOARD_SIZE):
                button = tk.Button(self.board_frame, width=BUTTON_SIZE, height=BUTTON_SIZE, image=self.images['bush'])
                button.bind('<Button-1>', lambda e, r=r, c=c: self.on_left_click(r, c))
                button.bind('<Button-3>', lambda e, r=r, c=c: self.on_right_click(r, c))
                button.grid(row=r, column=c)
                row_buttons.append(button)
            self.buttons.append(row_buttons)

    def _initialize_board(self, safe_row, safe_col):
        self.mine_board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        possible_mine_locations = [(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if abs(r - safe_row) > 1 or abs(c - safe_col) > 1]
        mine_locations = random.sample(possible_mine_locations, NUM_MINES)
        
        mines_to_place = self.images['pokemon'][:] if self.images_loaded_successfully else ['P'] * NUM_MINES
        random.shuffle(mines_to_place)

        for r, c in mine_locations:
            self.mine_board[r][c] = mines_to_place.pop()

        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.mine_board[r][c] != 0: continue
                count = 0
                for i in range(-1, 2):
                    for j in range(-1, 2):
                        if 0 <= r + i < BOARD_SIZE and 0 <= c + j < BOARD_SIZE:
                            cell = self.mine_board[r + i][c + j]
                            if isinstance(cell, (tuple, str)):
                                count += 1
                self.mine_board[r][c] = count

    def on_left_click(self, r, c):
        button = self.buttons[r][c]
        if self.game_over or button.cget('image') == str(self.images.get('flag')):
            return

        if self.first_click:
            self._initialize_board(r, c)
            self.first_click = False

        cell_value = self.mine_board[r][c]
        if isinstance(cell_value, (tuple, str)):
            self.reveal_all_mines()
            button.config(bg='red')
            self.end_game(won=False, mine_data=cell_value)
            return

        self.reveal_cell(r, c)
        if self.check_win(): self.end_game(won=True)

    def on_right_click(self, r, c):
        if self.game_over or self.buttons[r][c]['state'] == 'disabled': return
        button = self.buttons[r][c]
        current_image = button.cget('image')

        if current_image == str(self.images.get('bush')):
            button.config(image=self.images['flag'])
            self.flags_placed += 1
        elif current_image == str(self.images.get('flag')):
            button.config(image=self.images['bush'])
            self.flags_placed -= 1
        self.update_status_label()

    def reveal_cell(self, r, c):
        if not (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE) or self.buttons[r][c]['state'] == 'disabled': return
        button = self.buttons[r][c]
        cell_value = self.mine_board[r][c]

        button.config(state='disabled', relief=tk.SUNKEN, bg=BG_COLOR_REVEALED)
        if cell_value > 0:
            button.config(image=self.images['blank'], text=str(cell_value), font=('Helvetica', 10, 'bold'), fg=COLORS.get(cell_value), compound='center')
        else:
            button.config(image=self.images['blank'], text='')
            for i in range(-1, 2):
                for j in range(-1, 2):
                    self.reveal_cell(r + i, c + j)

    def reveal_all_mines(self):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                cell_value = self.mine_board[r][c]
                if isinstance(cell_value, (tuple, str)):
                    button = self.buttons[r][c]
                    if isinstance(cell_value, str): # Fallback 'P'
                        button.config(text='P', bg='#FFB6C1', image=self.images['blank'], compound='center')
                    else: # Pokemon Image Tuple
                        button.config(image=cell_value[0], bg='#FFB6C1')

    def end_game(self, won, mine_data=None):
        self.game_over = True
        popup_to_wait = None
        message = "축하합니다! 모든 포켓몬을 피했습니다!"

        if not won and mine_data:
            pokemon_name = mine_data[2] if isinstance(mine_data, tuple) else "포켓몬"
            message = f"이런! 야생의 {pokemon_name}와(과) 마주쳤습니다!"
            if isinstance(mine_data, tuple):
                popup = tk.Toplevel(self.master)
                popup.title("야생 포켓몬!")
                label = tk.Label(popup, image=mine_data[1], bg="white")
                label.image = mine_data[1]
                label.pack(padx=20, pady=20)
                popup_to_wait = popup

        if popup_to_wait:
            self.master.wait_window(popup_to_wait)
        
        messagebox.showinfo("게임 종료", message)

    def check_win(self):
        revealed_count = sum(1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if self.buttons[r][c]['state'] == 'disabled')
        return revealed_count == (BOARD_SIZE * BOARD_SIZE) - NUM_MINES

    def update_status_label(self):
        self.status_label.config(text=f"포켓몬: {NUM_MINES - self.flags_placed}")

if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        messagebox.showerror("라이브러리 필요", "Pillow 라이브러리가 필요합니다: pip install Pillow")
        exit()
    root = tk.Tk()
    game = MinesweeperGUI(root)
    root.mainloop()
