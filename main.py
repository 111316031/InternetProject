# filepath: C:\Users\ethan\Desktop\Project\main.py
"""
E-Card (國王與奴隸) - 單機版
===========================

這是一個基於 Python 與 Pygame 開發的「國王與奴隸」心理博弈卡牌遊戲。
玩家可以自由選擇「國王」或「奴隸」陣營，與採用隨機出牌策略的電腦對手（AI）對戰。

專案架構 (Architecture Tree)
--------------------------
C:\\Users\\ethan\\Desktop\\Project\\
└── main.py (包含完整遊戲邏輯、UI 渲染與動畫系統)

系統依賴與安裝 (Dependencies & Installation)
----------------------------------------
本專案僅依賴 pygame 庫。請在命令列執行以下指令進行安裝：
    pip install pygame

執行方式 (How to Run)
--------------------
在專案根目錄下執行：
    python main.py

遊戲規則 (Game Rules)
--------------------
1. 陣營與卡牌：
   - 國王陣營：1張「國王」卡、4張「平民」卡。
   - 奴隸陣營：1張「奴隸」卡、4張「平民」卡。
2. 卡牌勝負關係：
   - 國王 擊敗 平民
   - 平民 擊敗 奴隸
   - 奴隸 擊敗 國王（反制）
   - 平民 與 平民 則為 平手 (Tie)
3. 遊戲流程：
   - 每回合雙方各出一張牌，並同時翻牌。
   - 若雙方都出「平民」，此局平手，這兩張卡會移至棄牌區（平手區），雙方必須再從剩餘手牌中挑選出一張進行對決。
   - 一旦分出勝負（國王 vs 平民、平民 vs 奴隸、奴隸 vs 國王），該回合結束，獲勝方得一分。
   - 回合結束後，可重新選擇陣營並開始新的一輪。
"""

import pygame
import sys
import random
import math

# ==========================================
# 遊戲常數與設定
# ==========================================
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

# 卡牌類型
EMPEROR = "Emperor"
SLAVE = "Slave"
CITIZEN = "Citizen"

# 遊戲狀態定義
CHOOSE_ROLE = 0
PLAYING = 1
ANIMATING_PLAY = 2
REVEALING = 3
TIE_WAIT = 4
TIE_SLIDING = 5
ROUND_OVER = 6

# 全局遊戲變數
wins_player = 0
wins_cpu = 0
player_role = EMPEROR
cpu_role = SLAVE

player_hand = []
cpu_hand = []
player_played = None
cpu_played = None
tie_pile = []

game_phase = CHOOSE_ROLE
status_message = "請選擇您的陣營開始遊戲"
active_timer = 0
show_result_modal = False
round_winner = None
reset_btn_rect = pygame.Rect(0, 0, 0, 0)

# ==========================================
# 輔助渲染工具與函數
# ==========================================
def get_font(size, bold=False):
    """取得相容繁體中文的系統字型，若無則使用預設字型"""
    font_names = ["microsoftjhenghei", "pmingliu", "msgothic", "arial", "sans"]
    return pygame.font.SysFont(font_names, size, bold=bold)

def draw_rect_alpha(surface, color, rect, border_radius=0):
    """繪製支援透明度 (Alpha) 的矩形"""
    rect_obj = pygame.Rect(rect)
    temp_surf = pygame.Surface((rect_obj.width, rect_obj.height), pygame.SRCALPHA)
    pygame.draw.rect(temp_surf, color, (0, 0, rect_obj.width, rect_obj.height), border_radius=border_radius)
    surface.blit(temp_surf, (rect_obj.x, rect_obj.y))

def draw_glow(surface, rect, color, border_radius=8):
    """為指定矩形繪製多層次霓虹發光外框"""
    rect_obj = pygame.Rect(rect)
    for i in range(1, 5):
        g_rect = pygame.Rect(rect_obj.x - i, rect_obj.y - i, rect_obj.width + i * 2, rect_obj.height + i * 2)
        alpha = max(10, 100 - i * 20)
        draw_rect_alpha(surface, (color[0], color[1], color[2], alpha), g_rect, border_radius=border_radius + i)

def draw_gradient_background(surface, color1, color2):
    """繪製垂直漸層背景，增添畫面視覺質感"""
    h = surface.get_height()
    w = surface.get_width()
    for y in range(h):
        r = color1[0] + (color2[0] - color1[0]) * y // h
        g = color1[1] + (color2[1] - color1[1]) * y // h
        b = color1[2] + (color2[2] - color1[2]) * y // h
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))

def draw_button(surface, rect, text, bg_color, hover_color, text_color, is_hovered, font):
    """繪製通用按鈕，支援 Hover 效果與圓角陰影"""
    rect_obj = pygame.Rect(rect)
    # 按鈕陰影
    shadow_rect = pygame.Rect(rect_obj.x + 2, rect_obj.y + 2, rect_obj.width, rect_obj.height)
    draw_rect_alpha(surface, (10, 10, 15, 120), shadow_rect, border_radius=6)
    
    # 按鈕本體
    current_bg = hover_color if is_hovered else bg_color
    pygame.draw.rect(surface, current_bg, rect_obj, border_radius=6)
    pygame.draw.rect(surface, (255, 255, 255, 60), rect_obj, width=1, border_radius=6)
    
    # 按鈕文字
    text_surf = font.render(text, True, text_color)
    text_rect = text_surf.get_rect(center=rect_obj.center)
    surface.blit(text_surf, text_rect)

# ==========================================
# 圖示繪製工具（全向量繪製，不依賴外部圖片）
# ==========================================
def draw_crown_icon(surface, cx, cy, scale, color):
    """繪製精美黃金皇冠圖示 (國王)"""
    base_points = [
        (-20 * scale, 15 * scale),
        (20 * scale, 15 * scale),
        (25 * scale, -15 * scale),
        (10 * scale, -5 * scale),
        (0 * scale, -20 * scale),
        (-10 * scale, -5 * scale),
        (-25 * scale, -15 * scale)
    ]
    points = [(cx + px, cy + py) for px, py in base_points]
    pygame.draw.polygon(surface, color, points)
    # 皇冠尖端寶石
    pygame.draw.circle(surface, (255, 255, 255), (int(cx), int(cy - 20 * scale)), max(1, int(3 * scale)))
    pygame.draw.circle(surface, (255, 255, 255), (int(cx - 25 * scale), int(cy - 15 * scale)), max(1, int(3 * scale)))
    pygame.draw.circle(surface, (255, 255, 255), (int(cx + 25 * scale), int(cy - 15 * scale)), max(1, int(3 * scale)))

def draw_slave_icon(surface, cx, cy, scale, color):
    """繪製鐵鏈枷鎖圖示並帶有紅色警戒線 (奴隸)"""
    # 兩個枷鎖鐵環
    pygame.draw.circle(surface, color, (int(cx - 8 * scale), int(cy)), int(10 * scale), width=2)
    pygame.draw.circle(surface, color, (int(cx + 8 * scale), int(cy)), int(10 * scale), width=2)
    # 連結鐵條
    pygame.draw.line(surface, color, (int(cx - 4 * scale), int(cy)), (int(cx + 4 * scale), int(cy)), width=3)
    # 反抗警戒斜線 (暗紅)
    pygame.draw.line(surface, (220, 20, 60), (int(cx - 18 * scale), int(cy + 12 * scale)), (int(cx + 18 * scale), int(cy - 12 * scale)), width=2)

def draw_citizen_icon(surface, cx, cy, scale, color):
    """繪製簡約的人形圖示 (平民)"""
    # 頭部
    pygame.draw.circle(surface, color, (int(cx), int(cy - 12 * scale)), int(9 * scale))
    # 軀幹肩膀
    base_body = [
        (-12 * scale, 18 * scale),
        (12 * scale, 18 * scale),
        (8 * scale, 2 * scale),
        (-8 * scale, 2 * scale)
    ]
    body_points = [(cx + px, cy + py) for px, py in base_body]
    pygame.draw.polygon(surface, color, body_points)

# ==========================================
# 卡牌類別 (Card Class)
# ==========================================
class Card:
    def __init__(self, card_type, is_cpu, x=0.0, y=0.0):
        self.card_type = card_type
        self.is_cpu = is_cpu
        self.x = float(x)
        self.y = float(y)
        self.target_x = float(x)
        self.target_y = float(y)
        self.width = 90
        self.height = 140
        self.face_up = not is_cpu  # 玩家手牌預設正面向上，CPU 預設反面
        self.is_hovered = False
        self.is_played = False
        
        # 動態滑動速度
        self.slide_speed = 0.15
        
        # 翻牌動畫狀態
        self.is_flipping = False
        self.flip_timer = 0.0
        self.flip_duration = 350.0  # 毫秒
        self.draw_width_scale = 1.0
        self.midway_flipped = False
        
    def start_flip(self):
        """觸發翻牌動畫"""
        self.is_flipping = True
        self.flip_timer = 0.0
        self.midway_flipped = False
        self.draw_width_scale = 1.0
        
    def update(self, dt):
        """更新位置座標差值內插與翻牌狀態"""
        # 平滑滑動插值 (LERP)
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        
        if abs(dx) > 0.5:
            self.x += dx * self.slide_speed
        else:
            self.x = self.target_x
            
        if abs(dy) > 0.5:
            self.y += dy * self.slide_speed
        else:
            self.y = self.target_y
            
        # 翻牌旋轉插值 (利用餘弦模擬 3D 翻轉寬度縮放)
        if self.is_flipping:
            self.flip_timer += dt
            if self.flip_timer >= self.flip_duration:
                self.is_flipping = False
                self.flip_timer = self.flip_duration
                self.face_up = True
                self.draw_width_scale = 1.0
            else:
                progress = self.flip_timer / self.flip_duration
                angle = progress * math.pi
                self.draw_width_scale = abs(math.cos(angle))
                # 當寬度壓縮到最窄 (90度) 時切換正反面狀態
                if progress >= 0.5 and not self.midway_flipped:
                    self.face_up = True
                    self.midway_flipped = True

    def draw(self, surface):
        """渲染卡牌外觀，包含邊框、發光、圖示與文字"""
        w_val = int(self.width * self.draw_width_scale)
        x_offset = (self.width - w_val) // 2
        card_rect = pygame.Rect(self.x + x_offset, self.y, w_val, self.height)
        
        # 繪製卡牌底層陰影
        if self.draw_width_scale > 0.1:
            shadow_rect = pygame.Rect(self.x + x_offset + 3, self.y + 3, w_val, self.height)
            draw_rect_alpha(surface, (10, 10, 15, 80), shadow_rect, border_radius=8)
            
        # 根據正反面與類型決定色彩配置
        if self.face_up:
            if self.card_type == EMPEROR:
                bg_color = (35, 25, 10)       # 暗金背景
                border_color = (255, 215, 0)  # 純金邊框
                accent_color = (180, 140, 20) # 輔助描邊
            elif self.card_type == SLAVE:
                bg_color = (30, 12, 12)       # 暗紅背景
                border_color = (220, 20, 60)  # 緋紅邊框
                accent_color = (140, 25, 25)  # 輔助描邊
            else:  # Citizen
                bg_color = (20, 25, 35)       # 鐵灰藍背景
                border_color = (70, 130, 180) # 鋼青邊框
                accent_color = (40, 70, 100)  # 輔助描邊
        else:
            bg_color = (25, 22, 30)           # 卡背暗紫背景
            border_color = (147, 112, 219)    # 紫羅蘭邊框
            accent_color = (75, 0, 130)       # 靛藍中心

        # 繪製卡牌基底
        pygame.draw.rect(surface, bg_color, card_rect, border_radius=8)
        
        # 玩家選取懸停發光效果
        if self.is_hovered and not self.is_cpu and self.draw_width_scale > 0.5:
            draw_glow(surface, card_rect, (255, 255, 255), border_radius=8)
            
        # 繪製卡牌邊框
        pygame.draw.rect(surface, border_color, card_rect, width=2, border_radius=8)
        
        # 渲染卡牌內容（寬度大於一定閾值才進行繪製，避免翻轉時拉伸穿幫）
        if w_val > 20:
            center_x = self.x + x_offset + w_val // 2
            center_y = self.y + self.height // 2 - 10
            scale = self.draw_width_scale
            
            if self.face_up:
                # 內部裝飾框
                inner_rect = pygame.Rect(self.x + x_offset + 6, self.y + 6, w_val - 12, self.height - 12)
                pygame.draw.rect(surface, accent_color, inner_rect, width=1, border_radius=6)
                
                # 中文類型標籤
                font_title = get_font(16, bold=True)
                title_str = "國王" if self.card_type == EMPEROR else ("奴隸" if self.card_type == SLAVE else "平民")
                text_surf = font_title.render(title_str, True, border_color)
                text_rect = text_surf.get_rect(center=(center_x, self.y + self.height - 20))
                surface.blit(text_surf, text_rect)
                
                # 繪製對應向量圖示
                if self.card_type == EMPEROR:
                    draw_crown_icon(surface, center_x, center_y, scale * 0.9, border_color)
                elif self.card_type == SLAVE:
                    draw_slave_icon(surface, center_x, center_y, scale * 0.9, border_color)
                else:
                    draw_citizen_icon(surface, center_x, center_y, scale * 0.9, border_color)
            else:
                # 卡背花紋（神祕菱形與核心光球）
                base_diamond = [
                    (0, -25 * scale),
                    (18 * scale, 0),
                    (0, 25 * scale),
                    (-18 * scale, 0)
                ]
                diamond_points = [(center_x + px, center_y + py) for px, py in base_diamond]
                pygame.draw.polygon(surface, border_color, diamond_points, width=2)
                pygame.draw.circle(surface, accent_color, (int(center_x), int(center_y)), int(6 * scale))

# ==========================================
# 遊戲流程控制邏輯
# ==========================================
def init_round(p_role):
    """初始化全新的一局卡牌分配與排版"""
    global player_hand, cpu_hand, player_played, cpu_played, tie_pile
    global game_phase, status_message, player_role, cpu_role
    
    player_role = p_role
    cpu_role = SLAVE if p_role == EMPEROR else EMPEROR
    
    player_played = None
    cpu_played = None
    tie_pile = []
    player_hand = []
    cpu_hand = []
    
    # 根據陣營分配 5 張卡牌
    if player_role == EMPEROR:
        player_hand.append(Card(EMPEROR, False))
        for _ in range(4):
            player_hand.append(Card(CITIZEN, False))
            
        cpu_hand.append(Card(SLAVE, True))
        for _ in range(4):
            cpu_hand.append(Card(CITIZEN, True))
    else:
        player_hand.append(Card(SLAVE, False))
        for _ in range(4):
            player_hand.append(Card(CITIZEN, False))
            
        cpu_hand.append(Card(EMPEROR, True))
        for _ in range(4):
            cpu_hand.append(Card(CITIZEN, True))
            
    # 打亂初始排序，增加博弈不確定性
    random.shuffle(player_hand)
    random.shuffle(cpu_hand)
    
    # 計算並套用初始卡牌排列位置
    update_hand_layout(initial=True)
    
    game_phase = PLAYING
    status_message = "請點擊一張手牌，將其打出！"

def update_hand_layout(initial=False):
    """更新雙方賸餘手牌的排版位置 (置中排列)"""
    card_w = 90
    spacing = 20
    
    # 玩家手牌 (底部 Y=520)
    p_num = len(player_hand)
    if p_num > 0:
        total_p_w = p_num * card_w + (p_num - 1) * spacing
        start_p_x = (WINDOW_WIDTH - total_p_w) // 2
        for idx, card in enumerate(player_hand):
            card.target_x = float(start_p_x + idx * (card_w + spacing))
            card.target_y = 520.0
            if initial:
                card.x = card.target_x
                card.y = 750.0  # 從螢幕下方滑入動畫
                
    # 電腦手牌 (頂部 Y=50)
    c_num = len(cpu_hand)
    if c_num > 0:
        total_c_w = c_num * card_w + (c_num - 1) * spacing
        start_c_x = (WINDOW_WIDTH - total_c_w) // 2
        for idx, card in enumerate(cpu_hand):
            card.target_x = float(start_c_x + idx * (card_w + spacing))
            card.target_y = 50.0
            if initial:
                card.x = card.target_x
                card.y = -180.0  # 從螢幕上方滑入動畫

def play_card(p_card):
    """玩家出牌，並觸發電腦隨機出牌"""
    global player_played, cpu_played, game_phase, status_message
    
    # 玩家卡牌移出並設定目標點 (玩家出牌區)
    p_card.is_played = True
    p_card.is_hovered = False
    player_hand.remove(p_card)
    player_played = p_card
    p_card.target_x = 455.0
    p_card.target_y = 360.0
    
    # 電腦隨機選擇一張卡牌出牌 (電腦出牌區)
    cpu_card = random.choice(cpu_hand)
    cpu_card.is_played = True
    cpu_hand.remove(cpu_card)
    cpu_played = cpu_card
    cpu_played.target_x = 455.0
    cpu_played.target_y = 210.0
    
    # 進入出牌動畫階段
    game_phase = ANIMATING_PLAY
    status_message = "對決進行中，卡牌已配置..."

def evaluate_clash():
    """評估出牌對決勝負結果"""
    global game_phase, status_message, wins_player, wins_cpu, round_winner, active_timer
    
    p_type = player_played.card_type
    c_type = cpu_played.card_type
    
    if p_type == CITIZEN and c_type == CITIZEN:
        # 平民與平民平手
        status_message = "雙方皆為平民！判定平局。請準備出下一張牌..."
        game_phase = TIE_WAIT
        active_timer = 1500  # 等待 1.5 秒展示平局結果後再滑動
    else:
        # 決定勝負
        winner = None
        reason = ""
        
        if player_role == EMPEROR:
            # 玩家為國王陣營，電腦為奴隸陣營
            if p_type == EMPEROR and c_type == CITIZEN:
                winner = "Player"
                reason = "國王 駕崩平民！陛下取得了勝利。"
            elif p_type == CITIZEN and c_type == SLAVE:
                winner = "Player"
                reason = "平民 鎮壓奴隸！玩家防守成功。"
            elif p_type == EMPEROR and c_type == SLAVE:
                winner = "CPU"
                reason = "奴隸 逆襲國王！電腦反叛弒君成功。"
        else:
            # 玩家為奴隸陣營，電腦為國王陣營
            if p_type == SLAVE and c_type == EMPEROR:
                winner = "Player"
                reason = "奴隸 逆襲國王！玩家反叛弒君成功。"
            elif p_type == CITIZEN and c_type == EMPEROR:
                winner = "CPU"
                reason = "國王 駕崩平民！電腦取得了勝利。"
            elif p_type == SLAVE and c_type == CITIZEN:
                winner = "CPU"
                reason = "平民 鎮壓奴隸！電腦防守成功。"
                
        if winner == "Player":
            wins_player += 1
            round_winner = "Player"
            status_message = f"【勝利】{reason}"
        else:
            wins_cpu += 1
            round_winner = "CPU"
            status_message = f"【失敗】{reason}"
            
        # 回合結束，將電腦剩餘的手牌全部翻開展示，增加策略揭曉感
        for card in cpu_hand:
            card.start_flip()
            
        game_phase = ROUND_OVER
        active_timer = 1200  # 1.2 秒後彈出戰績結算視窗

def start_tie_slide():
    """將平局的兩張卡牌平滑移動至右側平局記錄存檔區"""
    global player_played, cpu_played, tie_pile, game_phase
    
    tie_index = len(tie_pile) // 2
    
    # 電腦卡牌飛往右側平手槽位上部，並確保顯示正面
    cpu_played.target_x = 790.0
    cpu_played.target_y = float(130 + tie_index * 45)
    cpu_played.face_up = True
    
    # 玩家卡牌飛往右側平手槽位下部
    player_played.target_x = 880.0
    player_played.target_y = float(130 + tie_index * 45)
    
    tie_pile.append(cpu_played)
    tie_pile.append(player_played)
    
    game_phase = TIE_SLIDING

def timer_expired():
    """計時器到期回呼函數，控制狀態流程切換"""
    global game_phase, show_result_modal
    if game_phase == TIE_WAIT:
        start_tie_slide()
    elif game_phase == ROUND_OVER:
        show_result_modal = True

# ==========================================
# 遊戲畫面更新與渲染引擎 (Update & Render)
# ==========================================
def update_game(dt, mouse_pos):
    """更新所有遊戲卡牌狀態與遊戲階段邏輯"""
    global game_phase, active_timer, player_played, cpu_played, status_message
    
    # 更新計時器
    if active_timer > 0:
        active_timer -= dt
        if active_timer <= 0:
            active_timer = 0
            timer_expired()
            
    # 更新所有卡牌位置與翻面動畫
    for card in player_hand:
        card.update(dt)
    for card in cpu_hand:
        card.update(dt)
    if player_played:
        player_played.update(dt)
    if cpu_played:
        cpu_played.update(dt)
    for card in tie_pile:
        card.update(dt)
        
    # 各階段的邏輯判斷
    if game_phase == PLAYING:
        # 偵測玩家滑鼠懸停手牌效果
        for card in player_hand:
            rect = pygame.Rect(card.x, card.y, card.width, card.height)
            if rect.collidepoint(mouse_pos):
                card.is_hovered = True
                card.target_y = 495.0  # 向上微微浮起
            else:
                card.is_hovered = False
                card.target_y = 520.0
                
    elif game_phase == ANIMATING_PLAY:
        # 確認出牌是否均已抵達對決區
        p_arrived = abs(player_played.x - player_played.target_x) < 1.0 and abs(player_played.y - player_played.target_y) < 1.0
        c_arrived = abs(cpu_played.x - cpu_played.target_x) < 1.0 and abs(cpu_played.y - cpu_played.target_y) < 1.0
        if p_arrived and c_arrived:
            player_played.x, player_played.y = player_played.target_x, player_played.target_y
            cpu_played.x, cpu_played.y = cpu_played.target_x, cpu_played.target_y
            
            # 開始翻開電腦的卡牌
            game_phase = REVEALING
            cpu_played.start_flip()
            
    elif game_phase == REVEALING:
        # 等待電腦卡片完成翻轉
        if not cpu_played.is_flipping:
            evaluate_clash()
            
    elif game_phase == TIE_SLIDING:
        # 等待平局卡牌抵達存檔槽位
        p_arrived = abs(player_played.x - player_played.target_x) < 1.0 and abs(player_played.y - player_played.target_y) < 1.0
        c_arrived = abs(cpu_played.x - cpu_played.target_x) < 1.0 and abs(cpu_played.y - cpu_played.target_y) < 1.0
        if p_arrived and c_arrived:
            player_played.x, player_played.y = player_played.target_x, player_played.target_y
            cpu_played.x, cpu_played.y = cpu_played.target_x, cpu_played.target_y
            
            player_played = None
            cpu_played = None
            
            # 若手牌仍有剩餘，繼續遊戲；否則平局結束（理論上五張牌必分勝負）
            if len(player_hand) > 0:
                game_phase = PLAYING
                status_message = "平局卡已存檔。請點擊下一張手牌打出。"
                update_hand_layout()
            else:
                status_message = "所有卡牌用罄，平局結束此輪。"
                game_phase = ROUND_OVER

def draw_header(surface, mouse_pos):
    """繪製上方控制列與即時比分"""
    pygame.draw.rect(surface, (15, 15, 20), pygame.Rect(0, 0, WINDOW_WIDTH, 50))
    pygame.draw.line(surface, (35, 35, 40), (0, 50), (WINDOW_WIDTH, 50), width=1)
    
    # 頂部小標題
    font_title = get_font(18, bold=True)
    title_text = font_title.render("E-CARD 國王與奴隸", True, (200, 180, 140))
    surface.blit(title_text, (20, 13))
    
    # 比分看板
    font_score = get_font(18, bold=True)
    score_str = f"戰績 — 玩家 {wins_player} : {wins_cpu} 電腦"
    score_text = font_score.render(score_str, True, (240, 240, 245))
    score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, 25))
    surface.blit(score_text, score_rect)
    
    # 重置分數按鈕
    global reset_btn_rect
    reset_btn_rect = pygame.Rect(870, 12, 110, 26)
    is_hovered = reset_btn_rect.collidepoint(mouse_pos)
    draw_button(surface, reset_btn_rect, "重置累計分數", (40, 40, 45), (100, 30, 30), (220, 220, 220), is_hovered, get_font(13))

def draw_placeholders(surface):
    """繪製卡牌對決空位與平手存檔槽框架"""
    # 電腦對決空槽
    cpu_spot = pygame.Rect(455, 210, 90, 140)
    pygame.draw.rect(surface, (35, 30, 45), cpu_spot, width=1, border_radius=8)
    font = get_font(14)
    lbl = font.render("電腦出牌槽", True, (65, 55, 75))
    lbl_rect = lbl.get_rect(center=cpu_spot.center)
    surface.blit(lbl, lbl_rect)
    
    # 玩家對決空槽
    p_spot = pygame.Rect(455, 360, 90, 140)
    pygame.draw.rect(surface, (25, 35, 45), p_spot, width=1, border_radius=8)
    lbl2 = font.render("玩家出牌槽", True, (55, 65, 75))
    lbl2_rect = lbl2.get_rect(center=p_spot.center)
    surface.blit(lbl2, lbl2_rect)
    
    # 右側平手歷史存檔外框
    tie_area = pygame.Rect(760, 120, 220, 380)
    pygame.draw.rect(surface, (20, 20, 25), tie_area, border_radius=10)
    pygame.draw.rect(surface, (38, 38, 44), tie_area, width=1, border_radius=10)
    
    font_sub = get_font(14, bold=True)
    tie_lbl = font_sub.render("平局對戰歷程 (Tie Logs)", True, (110, 110, 120))
    tie_lbl_rect = tie_lbl.get_rect(center=(870, 100))
    surface.blit(tie_lbl, tie_lbl_rect)

def draw_status_bar(surface):
    """渲染底部即時訊息通知列"""
    pygame.draw.rect(surface, (10, 10, 15), pygame.Rect(0, 665, WINDOW_WIDTH, 35))
    pygame.draw.line(surface, (30, 30, 35), (0, 665), (WINDOW_WIDTH, 665), width=1)
    
    font_msg = get_font(14)
    color = (220, 220, 225)
    if "勝利" in status_message:
        color = (255, 215, 0)
    elif "失敗" in status_message:
        color = (220, 20, 60)
    elif "平手" in status_message:
        color = (100, 180, 240)
        
    msg_surf = font_msg.render(status_message, True, color)
    msg_rect = msg_surf.get_rect(center=(WINDOW_WIDTH // 2, 682))
    surface.blit(msg_surf, msg_rect)

def draw_role_selection(surface, mouse_pos):
    """繪製選角畫面"""
    # 標題渲染 (E - C A R D)
    font_large = get_font(56, bold=True)
    title_text = font_large.render("E - C A R D", True, (240, 200, 120))
    title_rect = title_text.get_rect(center=(WINDOW_WIDTH // 2, 115))
    
    # 標題立體陰影
    title_shadow = font_large.render("E - C A R D", True, (15, 10, 5))
    surface.blit(title_shadow, (title_rect.x + 3, title_rect.y + 3))
    surface.blit(title_text, title_rect)
    
    # 副標題
    font_sub = get_font(20, bold=True)
    sub_text = font_sub.render("《賭博默示錄》— 國王與奴隸心理對決", True, (150, 150, 160))
    sub_rect = sub_text.get_rect(center=(WINDOW_WIDTH // 2, 175))
    surface.blit(sub_text, sub_rect)
    
    font_prompt = get_font(16)
    prompt_text = font_prompt.render("【請選擇您在本回合擔任的陣營】", True, (200, 200, 205))
    prompt_rect = prompt_text.get_rect(center=(WINDOW_WIDTH // 2, 220))
    surface.blit(prompt_text, prompt_rect)
    
    # 配置兩個選擇按鈕區
    emp_rect = pygame.Rect(180, 260, 260, 200)
    slave_rect = pygame.Rect(560, 260, 260, 200)
    
    emp_hover = emp_rect.collidepoint(mouse_pos)
    slave_hover = slave_rect.collidepoint(mouse_pos)
    
    # 皇帝陣營按鈕
    if emp_hover:
        draw_glow(surface, emp_rect, (255, 215, 0), border_radius=12)
    bg_emp = (45, 35, 15) if emp_hover else (30, 22, 10)
    pygame.draw.rect(surface, bg_emp, emp_rect, border_radius=12)
    border_emp = (255, 215, 0) if emp_hover else (180, 140, 40)
    pygame.draw.rect(surface, border_emp, emp_rect, width=2, border_radius=12)
    
    # 國王圖示
    draw_crown_icon(surface, emp_rect.centerx, emp_rect.y + 65, 1.2, border_emp)
    
    font_btn_title = get_font(24, bold=True)
    text_emp = font_btn_title.render("皇帝陣營", True, (255, 215, 0))
    surface.blit(text_emp, text_emp.get_rect(center=(emp_rect.centerx, emp_rect.y + 130)))
    
    font_btn_desc = get_font(13)
    desc_emp = font_btn_desc.render("執掌國王卡，壓制平民，但懼怕奴隸", True, (200, 190, 160))
    surface.blit(desc_emp, desc_emp.get_rect(center=(emp_rect.centerx, emp_rect.y + 165)))
    
    # 奴隸陣營按鈕
    if slave_hover:
        draw_glow(surface, slave_rect, (220, 20, 60), border_radius=12)
    bg_slave = (40, 15, 15) if slave_hover else (25, 10, 10)
    pygame.draw.rect(surface, bg_slave, slave_rect, border_radius=12)
    border_slave = (220, 20, 60) if slave_hover else (160, 30, 30)
    pygame.draw.rect(surface, border_slave, slave_rect, width=2, border_radius=12)
    
    # 奴隸圖示
    draw_slave_icon(surface, slave_rect.centerx, slave_rect.y + 65, 1.2, border_slave)
    
    text_slave = font_btn_title.render("奴隸陣營", True, (220, 20, 60))
    surface.blit(text_slave, text_slave.get_rect(center=(slave_rect.centerx, slave_rect.y + 130)))
    
    desc_slave = font_btn_desc.render("手握奴隸卡，伺機弒君，但懼怕平民", True, (200, 160, 160))
    surface.blit(desc_slave, desc_slave.get_rect(center=(slave_rect.centerx, slave_rect.y + 165)))
    
    # 底部規則說明面板
    rules_rect = pygame.Rect(180, 490, 640, 160)
    pygame.draw.rect(surface, (20, 20, 25), rules_rect, border_radius=10)
    pygame.draw.rect(surface, (38, 38, 44), rules_rect, width=1, border_radius=10)
    
    font_rules_title = get_font(15, bold=True)
    rules_title = font_rules_title.render("◆ 對決機制與規則說明 ◆", True, (180, 180, 190))
    surface.blit(rules_title, rules_title.get_rect(center=(WINDOW_WIDTH // 2, 515)))
    
    rules_text = [
        "1. 雙方各持 5 張卡。國王方為「1 國王 + 4 平民」；奴隸方為「1 奴隸 + 4 平民」。",
        "2. 克制鏈條：國王 > 平民，平民 > 奴隸，奴隸 > 國王。平民與平民出牌對決則判定平局。",
        "3. 兩張平民對決平手時，卡牌會移至右側歷程槽。雙方需繼續打出賸餘手牌進行下一輪交鋒。",
        "4. 電腦對手（CPU）將隨機選擇出牌。任何一方率先拿下決定性勝利即可獲得此回合積分。"
    ]
    for idx, line in enumerate(rules_text):
        line_surf = font_btn_desc.render(line, True, (135, 135, 145))
        surface.blit(line_surf, (205, 545 + idx * 24))

def draw_result_modal(surface, mouse_pos):
    """渲染回合結束的結果提示視窗"""
    # 模糊/變暗背景
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))
    
    modal_rect = pygame.Rect(320, 180, 360, 340)
    
    is_player_win = (round_winner == "Player")
    border_color = (255, 215, 0) if is_player_win else (220, 20, 60)
    
    # 彈窗底板與霓虹發光
    draw_glow(surface, modal_rect, border_color, border_radius=15)
    
    bg_modal = (30, 26, 20) if is_player_win else (28, 18, 18)
    pygame.draw.rect(surface, bg_modal, modal_rect, border_radius=15)
    pygame.draw.rect(surface, border_color, modal_rect, width=2, border_radius=15)
    
    # 勝利/敗北標題
    font_large_win = get_font(38, bold=True)
    win_title = "★ 獲 勝 ★" if is_player_win else "☠ 敗 北 ☠"
    title_color = (255, 215, 0) if is_player_win else (220, 20, 60)
    
    title_surf = font_large_win.render(win_title, True, title_color)
    surface.blit(title_surf, title_surf.get_rect(center=(modal_rect.centerx, modal_rect.y + 55)))
    
    # 細節描述 (如平民擊敗奴隸)
    font_mid_win = get_font(15, bold=True)
    detail_surf = font_mid_win.render(status_message, True, (240, 240, 240))
    surface.blit(detail_surf, detail_surf.get_rect(center=(modal_rect.centerx, modal_rect.y + 120)))
    
    # 分割線
    pygame.draw.line(surface, (80, 80, 90), (modal_rect.x + 40, modal_rect.y + 160), (modal_rect.right - 40, modal_rect.y + 160), width=1)
    
    # 比分面板
    font_score = get_font(15)
    score_lbl = font_score.render("累計比分", True, (160, 160, 170))
    surface.blit(score_lbl, score_lbl.get_rect(center=(modal_rect.centerx, modal_rect.y + 190)))
    
    font_score_num = get_font(28, bold=True)
    score_num_str = f"玩家 {wins_player} : {wins_cpu} 電腦"
    score_num_surf = font_score_num.render(score_num_str, True, (255, 255, 255))
    surface.blit(score_num_surf, score_num_surf.get_rect(center=(modal_rect.centerx, modal_rect.y + 235)))
    
    # 下一局按鈕
    btn_rect = pygame.Rect(380, 430, 240, 50)
    btn_hover = btn_rect.collidepoint(mouse_pos)
    
    btn_bg = (255, 215, 0) if is_player_win else (220, 20, 60)
    btn_hover_bg = (220, 180, 0) if is_player_win else (180, 15, 45)
    btn_text_color = (15, 15, 20) if is_player_win else (255, 255, 255)
    
    draw_button(surface, btn_rect, "開始下一局遊戲", btn_bg, btn_hover_bg, btn_text_color, btn_hover, get_font(18, bold=True))

def draw_game(surface, mouse_pos):
    """繪製遊戲當前場景的整體圖形介面"""
    # 渲染漸層背景
    draw_gradient_background(surface, (15, 16, 22), (25, 28, 38))
    
    # 渲染頂部控制列
    draw_header(surface, mouse_pos)
    
    if game_phase == CHOOSE_ROLE:
        draw_role_selection(surface, mouse_pos)
    else:
        # 繪製對決欄空位虛線框
        draw_placeholders(surface)
        
        # 繪製平手機制歷史存檔卡牌
        for card in tie_pile:
            card.draw(surface)
            
        # 繪製雙方剩餘手牌
        for card in cpu_hand:
            card.draw(surface)
        for card in player_hand:
            card.draw(surface)
            
        # 繪製正在出牌對決區的卡片（繪製於最上層）
        if cpu_played:
            cpu_played.draw(surface)
        if player_played:
            player_played.draw(surface)
            
        # 渲染底部提示列
        draw_status_bar(surface)
        
        # 若需要顯示彈窗結果
        if game_phase == ROUND_OVER and show_result_modal:
            draw_result_modal(surface, mouse_pos)

# ==========================================
# 遊戲主程式進入點 (Main Execution Entry)
# ==========================================
def main():
    global game_phase, status_message, wins_player, wins_cpu, player_role, show_result_modal, active_timer
    
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("賭博默示錄 — 國王與奴隸 (E-Card)")
    clock = pygame.time.Clock()
    
    running = True
    while running:
        # 取得自上一幀以來的毫秒數
        dt = clock.tick(FPS)
        mouse_pos = pygame.mouse.get_pos()
        
        # 事件迴圈偵測
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 點擊頂部重置按鈕
                if reset_btn_rect.collidepoint(mouse_pos):
                    wins_player = 0
                    wins_cpu = 0
                    game_phase = CHOOSE_ROLE
                    show_result_modal = False
                    status_message = "分數已重置。請重新選擇陣營開始遊戲。"
                    continue
                
                # 選角畫面點擊處理
                if game_phase == CHOOSE_ROLE:
                    emp_rect = pygame.Rect(180, 260, 260, 200)
                    slave_rect = pygame.Rect(560, 260, 260, 200)
                    
                    if emp_rect.collidepoint(mouse_pos):
                        init_round(EMPEROR)
                    elif slave_rect.collidepoint(mouse_pos):
                        init_round(SLAVE)
                
                # 遊戲進行中出牌點擊處理
                elif game_phase == PLAYING:
                    for card in player_hand:
                        if not card.is_played and card.is_hovered:
                            play_card(card)
                            break
                
                # 彈窗結算畫面按鈕點擊處理
                elif game_phase == ROUND_OVER and show_result_modal:
                    modal_btn = pygame.Rect(380, 430, 240, 50)
                    if modal_btn.collidepoint(mouse_pos):
                        game_phase = CHOOSE_ROLE
                        show_result_modal = False
                        status_message = "請選擇您的陣營開始新的一局"
                        
        # 狀態更新與畫面渲染
        update_game(dt, mouse_pos)
        draw_game(screen, mouse_pos)
        
        # 雙緩衝翻轉輸出
        pygame.display.flip()
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
