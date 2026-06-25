# filepath: C:\Users\ethan\Desktop\Project\src\common\ui_components.py
"""
E-Card (國王與奴隸) - UI與向量渲染元件模組
=====================================

此模組封裝所有 Pygame 繪圖、向量圖示渲染、按鈕以及 UICard 動畫元件。
完全隔離底層渲染技術細節，使主程式與邏輯架構保持精簡。

專案架構 (Architecture Tree)
--------------------------
C:\\Users\\ethan\\Desktop\\Project\\
├── main.py (程式進入點)
└── src\\
    ├── common\\
    │   ├── ui_components.py  (負責共用 UI 渲染與繪製元件)
    │   └── network_manager.py (負責 Socket 與 DLL 連線管理器)
    ├── ecard\\
    │   ├── ecard_logic.py     (E-Card 核心遊戲邏輯)
    │   └── ecard_ui.py        (E-Card UI 渲染與操作視覺)
    └── restricted_rps\\
        └── restricted_rps_game.py (限定剪刀石頭布 2D RPG 遊戲)
"""

import pygame
import math

# 卡牌類型
EMPEROR = "Emperor"
SLAVE = "Slave"
CITIZEN = "Citizen"

# ==========================================
# 輔助渲染工具與函數
# ==========================================
def get_font(size, bold=False):
    """取得相容繁體中文的系統字型，若無則使用預設字型"""
    font_names = ["microsoftjhenghei", "pmingliu", "msgothic", "arial", "sans"]
    return pygame.font.SysFont(font_names, size, bold=bold)

def draw_rect_alpha(surface, color, rect, border_radius=0):
    """繪製支援透明度 (Alpha 255) 的矩形"""
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

def draw_input_box(surface, rect, text, is_active, label_text, font):
    """繪製大廳文字輸入框，支援焦點高亮與閃爍輸入游標"""
    rect_obj = pygame.Rect(rect)
    
    # 繪製上方提示文字
    font_lbl = get_font(13)
    lbl_surf = font_lbl.render(label_text, True, (150, 150, 160))
    surface.blit(lbl_surf, (rect_obj.x, rect_obj.y - 18))
    
    # 輸入框主體背景與邊框
    bg_color = (25, 25, 30) if is_active else (18, 18, 22)
    border_color = (255, 215, 0) if is_active else (55, 55, 65)
    
    # 焦點發光
    if is_active:
        draw_glow(surface, rect_obj, (255, 215, 0), border_radius=4)
        
    pygame.draw.rect(surface, bg_color, rect_obj, border_radius=4)
    pygame.draw.rect(surface, border_color, rect_obj, width=1, border_radius=4)
    
    # 渲染輸入文字
    txt_surf = font.render(text, True, (255, 255, 255))
    txt_w, txt_h = txt_surf.get_size()
    max_w = rect_obj.width - 16
    if txt_w > max_w:
        try:
            txt_surf = pygame.transform.smoothscale(txt_surf, (max_w, int(txt_h * max_w / txt_w)))
        except Exception:
            txt_surf = pygame.transform.scale(txt_surf, (max_w, int(txt_h * max_w / txt_w)))
            
    surface.blit(txt_surf, (rect_obj.x + 8, rect_obj.y + (rect_obj.height - txt_surf.get_height()) // 2))
    
    # 閃爍游標邏輯 (500 毫秒切換狀態)
    if is_active and (pygame.time.get_ticks() // 500) % 2 == 0:
        cursor_x = rect_obj.x + 8 + txt_surf.get_width() + 2
        pygame.draw.line(surface, (255, 255, 255), (cursor_x, rect_obj.y + 6), (cursor_x, rect_obj.bottom - 6), width=2)

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
# UI 卡牌類別 (UICard Class)
# ==========================================
class UICard:
    def __init__(self, card_data, x=0.0, y=0.0):
        self.card_data = card_data
        self.card_id = card_data.card_id
        self.card_type = card_data.card_type
        self.is_cpu = card_data.is_cpu
        
        self.x = float(x)
        self.y = float(y)
        self.target_x = float(x)
        self.target_y = float(y)
        self.width = 90
        self.height = 140
        self.face_up = not self.is_cpu  # 玩家手牌預設正面向上，CPU 預設反面
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
