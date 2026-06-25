# filepath: C:\Users\ethan\Desktop\Project\main.py
"""
E-Game Center 遊戲娛樂大廳 - 主程序入口
=====================================

負責大廳 UI 渲染、Socket 連線測試與管理，以及子遊戲的生命週期管理與事件分流。
本大廳支援 E-Card (國王與奴隸) 與 Restricted RPS (限定剪刀石頭布)。
各遊戲實例與繪圖代碼完全模組化分開。
"""

import pygame
import sys
import threading
import socket

# 匯入邏輯、視覺元件與各遊戲模組
from src.ecard import ecard_logic
from src.common import ui_components
from src.common import network_manager
from src.restricted_rps import restricted_rps_game
from src.ecard import ecard_ui
from src.common.ui_components import get_font, draw_rect_alpha, draw_glow, draw_button, draw_input_box, draw_gradient_background

# ==========================================
# 初始化全域變數與常數
# ==========================================
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

# 大廳與子遊戲狀態常數
LOBBY = -1
RPS_GAME = 10

# 遊戲物件實例化
game = ecard_logic.EcardGame()
net_manager = network_manager.NetworkManager()
rps_game_instance = None
ecard_game_instance = None

# 大廳文字輸入與連線設定
server_ip = "127.0.0.1"
server_port = "8888"
player_name = "Player"  # 玩家設定的暱稱
connection_mode = "OFFLINE"  # 預設為離線單機 (AI 對戰)；支援 "OFFLINE", "HOST", "CLIENT"
is_waiting_connection = False # 主機開房等待對手連線狀態
active_input_field = None  # 當前聚焦輸入框 ("IP", "PORT", "NAME" 或 None)

connection_status_msg = "目前為單機離線模式，可直接啟動對決"
connection_status_color = (150, 150, 160)

# 各按鈕的點擊感應區
toggle_mode_rect = pygame.Rect(280, 250, 180, 35)
test_conn_rect = pygame.Rect(540, 250, 180, 35)
ip_input_rect = pygame.Rect(200, 190, 180, 30)       # 寬度調整並向左移
port_input_rect = pygame.Rect(410, 190, 80, 30)      # 向左移
name_input_rect = pygame.Rect(520, 190, 180, 30)      # 新增名字輸入框區
game_ecard_rect = pygame.Rect(200, 390, 280, 160)
game_locked_rect = pygame.Rect(520, 390, 280, 160)
exit_btn_rect = pygame.Rect(400, 590, 200, 45)

# ==========================================
# 網路連線非同步回呼處理 (Network Callbacks)
# ==========================================
def on_net_connected():
    """與伺服器成功連線時的回呼"""
    global connection_status_msg, connection_status_color
    connection_status_msg = "成功與遊戲伺服器建立連線！"
    connection_status_color = (100, 255, 100)

def on_net_disconnected(reason):
    """與伺服器斷線時的回呼"""
    global connection_status_msg, connection_status_color, game, ecard_game_instance, rps_game_instance
    connection_status_msg = f"連線已中斷: {reason}"
    connection_status_color = (255, 100, 100)
    
    # 若在對決過程中斷線，將強制返回大廳
    if game.game_phase != LOBBY:
        game.reset_scores()
        game.game_phase = LOBBY
        if ecard_game_instance is not None:
            ecard_game_instance.cleanup()
            ecard_game_instance = None
        if rps_game_instance is not None:
            rps_game_instance.cleanup()
            rps_game_instance = None

def on_net_error(err_msg):
    """網路通訊遭遇異常時的回呼"""
    global connection_status_msg, connection_status_color
    connection_status_msg = f"通訊錯誤: {err_msg}"
    connection_status_color = (255, 100, 100)

# 註冊網路大廳回呼函數
net_manager.on_connected = on_net_connected
net_manager.on_disconnected = on_net_disconnected
net_manager.on_error = on_net_error

# ==========================================
# 網路連線測試背景執行緒
# ==========================================
def run_connection_test():
    """執行非同步 Socket 連線測試，防止 UI 渲染執行緒凍結"""
    global connection_status_msg, connection_status_color
    connection_status_msg = "伺服器測試連線中..."
    connection_status_color = (200, 200, 100)
    
    success, msg = net_manager.connect(server_ip, server_port)
    if success:
        connection_status_msg = "伺服器測試連線成功！"
        connection_status_color = (100, 255, 100)
        net_manager.disconnect()
    else:
        connection_status_msg = f"伺服器測試連線失敗: {msg}"
        connection_status_color = (255, 100, 100)

def test_connection_async():
    threading.Thread(target=run_connection_test, daemon=True).start()

# ==========================================
# 遊戲大廳介面繪製 (Lobby Render)
# ==========================================
def draw_lobby_scene(surface, mouse_pos):
    """繪製遊戲大廳首頁"""
    draw_gradient_background(surface, (12, 14, 20), (22, 24, 30))
    
    # 頂部霓虹標題
    font_title = get_font(42, bold=True)
    title_surf = font_title.render("E - GAME LOBBY 遊戲大廳", True, (220, 200, 160))
    title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 70))
    
    title_shadow = font_title.render("E - GAME LOBBY 遊戲大廳", True, (5, 5, 8))
    surface.blit(title_shadow, (title_rect.x + 3, title_rect.y + 3))
    surface.blit(title_surf, title_rect)
    
    # ------------------------------------------
    # 1. 網路設定看板 (配置 IP/Port / 離線連線開關)
    # ------------------------------------------
    settings_area = pygame.Rect(180, 130, 640, 185)
    pygame.draw.rect(surface, (22, 22, 28), settings_area, border_radius=10)
    pygame.draw.rect(surface, (40, 40, 48), settings_area, width=1, border_radius=10)
    
    # 繪製輸入框
    font_input = get_font(16)
    if connection_mode == "HOST":
        display_ip = "0.0.0.0 (本機監聽)"
        draw_input_box(surface, ip_input_rect, display_ip, False, "主機 IP 位址 (Host)", font_input)
    else:
        draw_input_box(surface, ip_input_rect, server_ip, (active_input_field == "IP" and connection_mode == "CLIENT"), "伺服器 IP 位址 (Host)", font_input)
        
    draw_input_box(surface, port_input_rect, server_port, (active_input_field == "PORT" and connection_mode != "OFFLINE"), "連接埠 (Port)", font_input)
    draw_input_box(surface, name_input_rect, player_name, (active_input_field == "NAME"), "您的名字 (Name)", font_input)
    
    # 模式切換按鈕
    toggle_hover = toggle_mode_rect.collidepoint(mouse_pos)
    if connection_mode == "OFFLINE":
        mode_text = "模式: 離線單機 (AI)"
        mode_bg = (30, 50, 80)
        mode_hover_bg = (40, 65, 105)
        mode_txt_color = (255, 255, 255)
    elif connection_mode == "HOST":
        mode_text = "模式: 網路連線 (開房 Host)"
        mode_bg = (20, 120, 80)
        mode_hover_bg = (25, 150, 100)
        mode_txt_color = (255, 255, 255)
    else:
        mode_text = "模式: 網路連線 (加入 Client)"
        mode_bg = (200, 160, 20)
        mode_hover_bg = (170, 130, 15)
        mode_txt_color = (15, 15, 20)
        
    draw_button(surface, toggle_mode_rect, mode_text, mode_bg, mode_hover_bg, mode_txt_color, toggle_hover, get_font(14, bold=True))
    
    # 測試連線按鈕 (僅在 CLIENT 模式下啟用/非變灰)
    test_enabled = (connection_mode == "CLIENT")
    test_hover = test_conn_rect.collidepoint(mouse_pos) and test_enabled
    test_bg = (50, 50, 55) if test_enabled else (30, 30, 32)
    test_hover_bg = (70, 70, 78) if test_enabled else (30, 30, 32)
    test_txt_color = (220, 220, 220) if test_enabled else (90, 90, 95)
    draw_button(surface, test_conn_rect, "測試連線", test_bg, test_hover_bg, test_txt_color, test_hover, get_font(14))
    
    # 顯示連線狀態提示
    font_status = get_font(13)
    status_surf = font_status.render(connection_status_msg, True, connection_status_color)
    status_rect = status_surf.get_rect(center=(WINDOW_WIDTH // 2, 292))
    surface.blit(status_surf, status_rect)
    
    # ------------------------------------------
    # 2. 遊戲選擇卡牌
    # ------------------------------------------
    # 2.1 國王與奴隸遊戲按鈕
    ecard_hover = game_ecard_rect.collidepoint(mouse_pos)
    if ecard_hover:
        draw_glow(surface, game_ecard_rect, (200, 180, 130), border_radius=12)
    bg_ec = (35, 30, 25) if ecard_hover else (24, 20, 16)
    border_ec = (200, 180, 130) if ecard_hover else (80, 70, 60)
    pygame.draw.rect(surface, bg_ec, game_ecard_rect, border_radius=12)
    pygame.draw.rect(surface, border_ec, game_ecard_rect, width=2, border_radius=12)
    
    # 遊戲小圖示
    ui_components.draw_crown_icon(surface, game_ecard_rect.x + 60, game_ecard_rect.y + 60, 0.7, (255, 215, 0))
    ui_components.draw_slave_icon(surface, game_ecard_rect.right - 60, game_ecard_rect.y + 60, 0.7, (220, 20, 60))
    
    title_ec = get_font(22, bold=True).render("國王與奴隸 (E-Card)", True, (240, 240, 245))
    desc_ec = get_font(13).render("經典心理博弈卡牌", True, (150, 150, 160))
    surface.blit(title_ec, title_ec.get_rect(center=(game_ecard_rect.centerx, game_ecard_rect.y + 115)))
    surface.blit(desc_ec, desc_ec.get_rect(center=(game_ecard_rect.centerx, game_ecard_rect.y + 140)))
    
    # 2.2 限定剪刀石頭布遊戲按鈕
    rps_hover = game_locked_rect.collidepoint(mouse_pos)
    if rps_hover:
        draw_glow(surface, game_locked_rect, (100, 180, 255), border_radius=12)
    bg_rps = (20, 26, 36) if rps_hover else (16, 20, 28)
    border_rps = (100, 180, 255) if rps_hover else (60, 80, 110)
    pygame.draw.rect(surface, bg_rps, game_locked_rect, border_radius=12)
    pygame.draw.rect(surface, border_rps, game_locked_rect, width=2, border_radius=12)
    
    # 繪製星星與卡牌向量圖示
    cx, cy = game_locked_rect.centerx, game_locked_rect.y + 55
    restricted_rps_game.draw_star(surface, cx, cy - 5, 14, (255, 215, 0))
    # 兩側畫小手牌
    pygame.draw.rect(surface, (220, 80, 80), pygame.Rect(cx - 55, cy - 15, 22, 32), border_radius=3, width=1) # 紅色
    pygame.draw.rect(surface, (130, 130, 140), pygame.Rect(cx + 33, cy - 15, 22, 32), border_radius=3, width=1) # 灰色
    
    title_rps = get_font(22, bold=True).render("限定剪刀石頭布", True, (240, 240, 245))
    desc_rps = get_font(13).render("2D RPG 探索與卡牌交易心理對決", True, (150, 150, 160))
    surface.blit(title_rps, title_rps.get_rect(center=(game_locked_rect.centerx, game_locked_rect.y + 115)))
    surface.blit(desc_rps, desc_rps.get_rect(center=(game_locked_rect.centerx, game_locked_rect.y + 140)))
    
    # ------------------------------------------
    # 3. 離開程式按鈕
    # ------------------------------------------
    exit_hover = exit_btn_rect.collidepoint(mouse_pos)
    draw_button(surface, exit_btn_rect, "離開遊戲程式", (60, 20, 20), (120, 20, 25), (240, 220, 220), exit_hover, get_font(16, bold=True))

def draw_game_scene(surface, mouse_pos):
    """主渲染派發器：選擇渲染大廳"""
    if game.game_phase == LOBBY:
        draw_lobby_scene(surface, mouse_pos)

# ==========================================
# 主程式執行迴圈 (Event Loop Entry)
# ==========================================
def main():
    global game, rps_game_instance, ecard_game_instance
    global server_ip, server_port, connection_mode, active_input_field, is_waiting_connection
    global connection_status_msg, connection_status_color, player_name
    
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("E-Game Center 遊戲娛樂大廳")
    clock = pygame.time.Clock()
    
    # 預設啟動先進入遊戲大廳
    game.game_phase = LOBBY
    
    running = True
    while running:
        dt = clock.tick(FPS)
        mouse_pos = pygame.mouse.get_pos()
        
        # 全域輪詢網路通訊
        net_manager.poll()
        
        # 主機開房連線完成後，自動跳轉進入遊戲介面
        if connection_mode == "HOST" and is_waiting_connection and net_manager.is_connected:
            is_waiting_connection = False
            if getattr(net_manager, "game_type", "ecard") == "rps":
                game.game_phase = RPS_GAME
                rps_game_instance = restricted_rps_game.RestrictedRPSGame(screen, game, net_manager, is_offline=False)
            else:
                ecard_game_instance = ecard_ui.EcardGameUI(screen, game, net_manager, is_offline=False)
            connection_status_msg = "對手已連入！遊戲啟動中。"
            connection_status_color = (100, 255, 100)
            
        # 偵測輸入事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            elif game.game_phase == RPS_GAME and rps_game_instance is not None:
                # 轉交輸入事件予限定剪刀石頭布模組
                rps_game_instance.handle_event(event, mouse_pos)
                
            elif 0 <= game.game_phase <= 6 and ecard_game_instance is not None:
                # 轉交輸入事件予 E-Card 模組
                ecard_game_instance.handle_event(event, mouse_pos)
                
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # ------------------------------------------
                # 大廳狀態下的點擊偵測
                # ------------------------------------------
                if game.game_phase == LOBBY:
                    # 點擊 IP 輸入框 (僅在 CLIENT 模式下啟用)
                    if ip_input_rect.collidepoint(mouse_pos) and connection_mode == "CLIENT":
                        active_input_field = "IP"
                    # 點擊 Port 輸入框 (非離線模式下啟用)
                    elif port_input_rect.collidepoint(mouse_pos) and connection_mode != "OFFLINE":
                        active_input_field = "PORT"
                    # 點擊 名字 輸入框 (任何模式皆可點選)
                    elif name_input_rect.collidepoint(mouse_pos):
                        active_input_field = "NAME"
                    else:
                        active_input_field = None
                        
                    # 點擊模式切換按鈕
                    if toggle_mode_rect.collidepoint(mouse_pos):
                        is_waiting_connection = False
                        net_manager.disconnect()
                        
                        if connection_mode == "OFFLINE":
                            connection_mode = "HOST"
                            connection_status_msg = "切換為開房模式，啟動遊戲時將啟動本機伺服器等待連線"
                            connection_status_color = (200, 200, 100)
                        elif connection_mode == "HOST":
                            connection_mode = "CLIENT"
                            connection_status_msg = "切換為聯機模式，啟動遊戲時將連線至指定主機 IP"
                            connection_status_color = (200, 200, 100)
                        else:
                            connection_mode = "OFFLINE"
                            connection_status_msg = "目前為單機離線模式，可直接啟動對決"
                            connection_status_color = (150, 150, 160)
                            
                    # 點擊測試連線按鈕 (僅在 CLIENT 模式下啟用)
                    elif test_conn_rect.collidepoint(mouse_pos) and connection_mode == "CLIENT":
                        test_connection_async()
                        
                    # 點擊啟動「國王與奴隸」遊戲
                    elif game_ecard_rect.collidepoint(mouse_pos):
                        # 同步玩家名字到 net_manager 供連線層調用
                        net_manager.player_name = player_name
                        if connection_mode == "OFFLINE":
                            # 進入離線模式 E-Card
                            ecard_game_instance = ecard_ui.EcardGameUI(screen, game, net_manager, is_offline=True)
                        elif connection_mode == "HOST":
                            # 網路連線模式下 - Host 開房監聽
                            connection_status_msg = "開房監聽中，等待對手連入..."
                            connection_status_color = (200, 200, 100)
                            net_manager.game_type = "ecard"
                            success, msg = net_manager.host(server_port)
                            if success:
                                is_waiting_connection = True
                            else:
                                connection_status_msg = f"開房失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                        elif connection_mode == "CLIENT":
                            # 網路連線模式下 - Client 連線
                            connection_status_msg = "嘗試與主機連線中..."
                            connection_status_color = (200, 200, 100)
                            net_manager.game_type = "ecard"
                            success, msg = net_manager.connect(server_ip, server_port)
                            if success:
                                ecard_game_instance = ecard_ui.EcardGameUI(screen, game, net_manager, is_offline=False)
                            else:
                                connection_status_msg = f"連線失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                                
                    # 點擊啟動「限定剪刀石頭布」遊戲
                    elif game_locked_rect.collidepoint(mouse_pos):
                        net_manager.player_name = player_name
                        if connection_mode == "OFFLINE":
                            game.game_phase = RPS_GAME
                            rps_game_instance = restricted_rps_game.RestrictedRPSGame(screen, game, net_manager, is_offline=True)
                        elif connection_mode == "HOST":
                            connection_status_msg = "開房監聽中，等待對手連入..."
                            connection_status_color = (200, 200, 100)
                            net_manager.game_type = "rps"
                            success, msg = net_manager.host(server_port)
                            if success:
                                is_waiting_connection = True
                            else:
                                connection_status_msg = f"開房失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                        elif connection_mode == "CLIENT":
                            connection_status_msg = "嘗試與主機連線中..."
                            connection_status_color = (200, 200, 100)
                            net_manager.game_type = "rps"
                            success, msg = net_manager.connect(server_ip, server_port)
                            if success:
                                game.game_phase = RPS_GAME
                                rps_game_instance = restricted_rps_game.RestrictedRPSGame(screen, game, net_manager, is_offline=False)
                            else:
                                connection_status_msg = f"連線失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                                
                    # 點擊離開程式
                    elif exit_btn_rect.collidepoint(mouse_pos):
                        running = False
                
            # 大廳設定文字輸入處理
            elif event.type == pygame.KEYDOWN:
                if game.game_phase == LOBBY and active_input_field:
                    if event.key == pygame.K_BACKSPACE:
                        if active_input_field == "IP":
                            server_ip = server_ip[:-1]
                        elif active_input_field == "PORT":
                            server_port = server_port[:-1]
                        elif active_input_field == "NAME":
                            player_name = player_name[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        active_input_field = None
                    else:
                        char = event.unicode
                        if char and char.isprintable():
                            if active_input_field == "IP":
                                # 限制 IP 長度為 15
                                if len(server_ip) < 15:
                                    server_ip += char
                            elif active_input_field == "PORT":
                                # 限制 Port 長度為 5 且限為數字
                                if len(server_port) < 5 and char.isdigit():
                                    server_port += char
                            elif active_input_field == "NAME":
                                # 限制名字長度為 12
                                if len(player_name) < 12:
                                    player_name += char
                                    
        # 位置更新與畫面渲染
        if game.game_phase == RPS_GAME and rps_game_instance is not None:
            rps_game_instance.update(dt, mouse_pos)
            rps_game_instance.draw(screen, mouse_pos)
        elif 0 <= game.game_phase <= 6 and ecard_game_instance is not None:
            ecard_game_instance.update(dt, mouse_pos)
            ecard_game_instance.draw(screen, mouse_pos)
        else:
            # 大廳狀態下釋放子遊戲實例，釋放記憶體並重置狀態
            if rps_game_instance is not None:
                rps_game_instance.cleanup()
            ecard_game_instance = None
            rps_game_instance = None
            
            # 渲染大廳
            draw_game_scene(screen, mouse_pos)
        
        pygame.display.flip()
        
    # 安全斷開網路並關閉視窗
    net_manager.disconnect()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
