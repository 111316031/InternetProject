# filepath: C:\Users\ethan\Desktop\Project-Combine\main.py
"""
E-Game Center 遊戲娛樂大廳 - 主程序入口
=====================================

負責大廳 UI 渲染、Socket 連線測試與管理，以及子遊戲的生命週期管理與事件分流。
本大廳支援 E-Card (國王與奴隸) 與 Restricted RPS (限定剪刀石頭布)。
各遊戲實例與繪圖代碼完全模組化分開。

重構亮點：
1. 房主 Host 點擊開房時，自動在背景啟動中央伺服器，雙方都連線至伺服器。
2. 支援大廳多人 Slot 動態渲染。
3. 只要有人斷線退出，大廳直接解散。
"""

import pygame
import sys
import threading
import socket
import json

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
ROOM_LOBBY = -2  # 房間大廳狀態
LOBBY = -1       # 首頁大廳狀態
RPS_GAME = 10    # 石頭布遊戲狀態

# 遊戲物件實例化
game = ecard_logic.EcardGame()
net_manager = network_manager.NetworkManager()
rps_game_instance = None
ecard_game_instance = None

# 大廳文字輸入與連線設定
server_ip = "127.0.0.1"
server_port = "8888"
player_name = "Player"        # 玩家設定的暱稱
connection_mode = "OFFLINE"   # 預設為離線單機；支援 "OFFLINE", "HOST", "CLIENT"
is_waiting_connection = False # 連線等待狀態
active_input_field = None     # 當前聚焦輸入框

connection_status_msg = "目前為單機離線模式，可直接啟動對決"
connection_status_color = (150, 150, 160)

# 各按鈕的點擊感應區 (首頁大廳)
toggle_mode_rect = pygame.Rect(280, 250, 180, 35)
test_conn_rect = pygame.Rect(540, 250, 180, 35)
ip_input_rect = pygame.Rect(200, 190, 180, 30)
port_input_rect = pygame.Rect(410, 190, 80, 30)
name_input_rect = pygame.Rect(520, 190, 180, 30)
game_ecard_rect = pygame.Rect(200, 390, 280, 160)
game_locked_rect = pygame.Rect(520, 390, 280, 160)
exit_btn_rect = pygame.Rect(400, 590, 200, 45)

# 各按鈕的點擊感應區 (房間大廳 ROOM_LOBBY)
room_add_bot_rect = pygame.Rect(540, 200, 240, 45)
room_start_game_rect = pygame.Rect(540, 270, 240, 45)
room_remove_bot_rect = pygame.Rect(540, 340, 240, 45)
room_leave_rect = pygame.Rect(540, 440, 240, 45)

# ==========================================
# 網路連線非同步回呼處理 (Network Callbacks)
# ==========================================
def on_net_connected():
    """與中央伺服器成功連線時的回呼"""
    global connection_status_msg, connection_status_color
    connection_status_msg = "已成功連入中央伺服器！"
    connection_status_color = (100, 255, 100)

def on_net_disconnected(reason):
    """與伺服器斷線時的回呼"""
    global connection_status_msg, connection_status_color, game, ecard_game_instance, rps_game_instance
    connection_status_msg = f"連線已中斷: {reason}"
    connection_status_color = (255, 100, 100)
    
    # 強制返回首頁大廳
    if game.game_phase != LOBBY:
        game.reset_scores() if hasattr(game, "reset_scores") else None
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

# 註冊基本網路回呼
net_manager.on_connected = on_net_connected
net_manager.on_disconnected = on_net_disconnected
net_manager.on_error = on_net_error

# ==========================================
# 網路連線測試背景執行緒
# ==========================================
def run_connection_test():
    """執行非同步 Port 連線測試"""
    global connection_status_msg, connection_status_color
    connection_status_msg = "測試連線中..."
    connection_status_color = (200, 200, 100)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        sock.connect((server_ip, int(server_port)))
        connection_status_msg = "伺服器可成功連線！"
        connection_status_color = (100, 255, 100)
        sock.close()
    except Exception as e:
        connection_status_msg = f"連線失敗: {str(e)}"
        connection_status_color = (255, 100, 100)

def test_connection_async():
    threading.Thread(target=run_connection_test, daemon=True).start()

# ==========================================
# 遊戲大廳首頁繪製 (Lobby Render)
# ==========================================
def draw_lobby_scene(surface, mouse_pos):
    """繪製遊戲大廳首頁"""
    draw_gradient_background(surface, (12, 14, 20), (22, 24, 30))
    
    font_title = get_font(42, bold=True)
    title_surf = font_title.render("E - GAME LOBBY 遊戲大廳", True, (220, 200, 160))
    title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 70))
    
    title_shadow = font_title.render("E - GAME LOBBY 遊戲大廳", True, (5, 5, 8))
    surface.blit(title_shadow, (title_rect.x + 3, title_rect.y + 3))
    surface.blit(title_surf, title_rect)
    
    settings_area = pygame.Rect(180, 130, 640, 185)
    pygame.draw.rect(surface, (22, 22, 28), settings_area, border_radius=10)
    pygame.draw.rect(surface, (40, 40, 48), settings_area, width=1, border_radius=10)
    
    # 繪製輸入框
    font_input = get_font(16)
    if connection_mode == "HOST":
        display_ip = "一鍵啟用伺服器 (Host)"
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
        mode_text = "模式: 網路大廳 (房主 Host)"
        mode_bg = (20, 120, 80)
        mode_hover_bg = (25, 150, 100)
        mode_txt_color = (255, 255, 255)
    else:
        mode_text = "模式: 網路大廳 (加入 Client)"
        mode_bg = (200, 160, 20)
        mode_hover_bg = (170, 130, 15)
        mode_txt_color = (15, 15, 20)
        
    draw_button(surface, toggle_mode_rect, mode_text, mode_bg, mode_hover_bg, mode_txt_color, toggle_hover, get_font(14, bold=True))
    
    test_enabled = (connection_mode == "CLIENT")
    test_hover = test_conn_rect.collidepoint(mouse_pos) and test_enabled
    test_bg = (50, 50, 55) if test_enabled else (30, 30, 32)
    test_hover_bg = (70, 70, 78) if test_enabled else (30, 30, 32)
    test_txt_color = (220, 220, 220) if test_enabled else (90, 90, 95)
    draw_button(surface, test_conn_rect, "測試連線", test_bg, test_hover_bg, test_txt_color, test_hover, get_font(14))
    
    font_status = get_font(13)
    status_surf = font_status.render(connection_status_msg, True, connection_status_color)
    status_rect = status_surf.get_rect(center=(WINDOW_WIDTH // 2, 292))
    surface.blit(status_surf, status_rect)
    
    # 2. 遊戲選擇卡牌
    ecard_hover = game_ecard_rect.collidepoint(mouse_pos)
    if ecard_hover:
        draw_glow(surface, game_ecard_rect, (200, 180, 130), border_radius=12)
    bg_ec = (35, 30, 25) if ecard_hover else (24, 20, 16)
    border_ec = (200, 180, 130) if ecard_hover else (80, 70, 60)
    pygame.draw.rect(surface, bg_ec, game_ecard_rect, border_radius=12)
    pygame.draw.rect(surface, border_ec, game_ecard_rect, width=2, border_radius=12)
    
    ui_components.draw_crown_icon(surface, game_ecard_rect.x + 60, game_ecard_rect.y + 60, 0.7, (255, 215, 0))
    ui_components.draw_slave_icon(surface, game_ecard_rect.right - 60, game_ecard_rect.y + 60, 0.7, (220, 20, 60))
    
    title_ec = get_font(22, bold=True).render("國王與奴隸 (E-Card)", True, (240, 240, 245))
    desc_ec = get_font(13).render("經典心理博弈卡牌", True, (150, 150, 160))
    surface.blit(title_ec, title_ec.get_rect(center=(game_ecard_rect.centerx, game_ecard_rect.y + 115)))
    surface.blit(desc_ec, desc_ec.get_rect(center=(game_ecard_rect.centerx, game_ecard_rect.y + 140)))
    
    rps_hover = game_locked_rect.collidepoint(mouse_pos)
    if rps_hover:
        draw_glow(surface, game_locked_rect, (100, 180, 255), border_radius=12)
    bg_rps = (20, 26, 36) if rps_hover else (16, 20, 28)
    border_rps = (100, 180, 255) if rps_hover else (60, 80, 110)
    pygame.draw.rect(surface, bg_rps, game_locked_rect, border_radius=12)
    pygame.draw.rect(surface, border_rps, game_locked_rect, width=2, border_radius=12)
    
    cx, cy = game_locked_rect.centerx, game_locked_rect.y + 55
    restricted_rps_game.draw_star(surface, cx, cy - 5, 14, (255, 215, 0))
    pygame.draw.rect(surface, (220, 80, 80), pygame.Rect(cx - 55, cy - 15, 22, 32), border_radius=3, width=1)
    pygame.draw.rect(surface, (130, 130, 140), pygame.Rect(cx + 33, cy - 15, 22, 32), border_radius=3, width=1)
    
    title_rps = get_font(22, bold=True).render("限定剪刀石頭布", True, (240, 240, 245))
    desc_rps = get_font(13).render("2D RPG 探索與卡牌交易心理對決", True, (150, 150, 160))
    surface.blit(title_rps, title_rps.get_rect(center=(game_locked_rect.centerx, game_locked_rect.y + 115)))
    surface.blit(desc_rps, desc_rps.get_rect(center=(game_locked_rect.centerx, game_locked_rect.y + 140)))
    
    exit_hover = exit_btn_rect.collidepoint(mouse_pos)
    draw_button(surface, exit_btn_rect, "離開遊戲程式", (60, 20, 20), (120, 20, 25), (240, 220, 220), exit_hover, get_font(16, bold=True))


# ==========================================
# 房間大廳介面繪製 (Room Lobby Render)
# ==========================================
def draw_room_lobby_scene(surface, mouse_pos):
    """繪製玩家已進入之房間大廳"""
    draw_gradient_background(surface, (10, 15, 25), (20, 25, 35))
    
    font_title = get_font(36, bold=True)
    game_name = "國王與奴隸 (E-Card)" if net_manager.game_type == "ecard" else "限定剪刀石頭布"
    lobby_title = f"{game_name} - 大廳 (Room: {net_manager.room_id or '建立中'})"
    title_surf = font_title.render(lobby_title, True, (220, 200, 160))
    title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 70))
    surface.blit(title_surf, title_rect)
    
    lobby_area = pygame.Rect(150, 130, 700, 420)
    pygame.draw.rect(surface, (22, 24, 30), lobby_area, border_radius=12)
    pygame.draw.rect(surface, (50, 55, 70), lobby_area, width=2, border_radius=12)
    
    font_section = get_font(18, bold=True)
    sec_surf = font_section.render("房間成員列表", True, (180, 180, 200))
    surface.blit(sec_surf, (180, 155))
    
    # 支援最多 4 個插槽動態顯示
    max_visible_slots = 4
    for idx in range(max_visible_slots):
        slot_rect = pygame.Rect(180, 195 + idx * 80, 320, 70)
        pygame.draw.rect(surface, (30, 32, 40), slot_rect, border_radius=8)
        pygame.draw.rect(surface, (60, 65, 80), slot_rect, width=1, border_radius=8)
        
        if idx < len(net_manager.room_players):
            player_info = net_manager.room_players[idx]
            p_name = player_info["name"]
            is_bot = player_info.get("is_bot", False)
            is_room_host = (p_name == net_manager.room_host)
            
            font_name = get_font(18, bold=True)
            name_color = (255, 215, 0) if is_room_host else (240, 240, 250)
            
            disp_name = p_name
            if is_bot:
                disp_name += " (虛擬 AI)"
                
            name_surf = font_name.render(disp_name, True, name_color)
            surface.blit(name_surf, (slot_rect.x + 20, slot_rect.y + 12))
            
            font_role = get_font(12)
            role_str = "【房主】👑" if is_room_host else "【挑戰者】"
            if is_bot:
                role_str = "【陪玩機器人】🤖"
            role_surf = font_role.render(role_str, True, (150, 150, 170))
            surface.blit(role_surf, (slot_rect.x + 20, slot_rect.y + 40))
        else:
            font_empty = get_font(14)
            empty_surf = font_empty.render("等待玩家加入...", True, (80, 80, 90))
            surface.blit(empty_surf, (slot_rect.x + 20, slot_rect.y + 25))
            
    is_me_host = (net_manager.player_name == net_manager.room_host)
    total_players = len(net_manager.room_players)
    
    # 2.1 新增機器人按鈕 (限房主且人數未滿上限)
    # E-Card 上限為 2，RPS 上限為 4
    bot_limit = 4 if net_manager.game_type == "rps" else 2
    bot_enabled = is_me_host and (total_players < bot_limit)
    bot_hover = room_add_bot_rect.collidepoint(mouse_pos) and bot_enabled
    bot_bg = (40, 90, 150) if bot_enabled else (35, 40, 45)
    bot_hover_bg = (50, 110, 180) if bot_enabled else (35, 40, 45)
    bot_txt = (240, 240, 250) if bot_enabled else (110, 115, 120)
    draw_button(surface, room_add_bot_rect, "新增機器人 (Add Bot)", bot_bg, bot_hover_bg, bot_txt, bot_hover, get_font(15, bold=True))
    
    # 2.1.2 移除機器人按鈕 (限房主且房間內有機器人)
    has_bots = any(p.get("is_bot", False) for p in net_manager.room_players)
    remove_bot_enabled = is_me_host and has_bots
    remove_bot_hover = room_remove_bot_rect.collidepoint(mouse_pos) and remove_bot_enabled
    remove_bot_bg = (150, 90, 40) if remove_bot_enabled else (35, 40, 45)
    remove_bot_hover_bg = (180, 110, 50) if remove_bot_enabled else (35, 40, 45)
    remove_bot_txt = (240, 240, 250) if remove_bot_enabled else (110, 115, 120)
    draw_button(surface, room_remove_bot_rect, "刪除機器人 (Remove Bot)", remove_bot_bg, remove_bot_hover_bg, remove_bot_txt, remove_bot_hover, get_font(15, bold=True))
    
    # 2.2 開始遊戲按鈕 (RPS 至少需要 2 人，E-Card 必須剛好 2 人)
    if net_manager.game_type == "rps":
        start_enabled = is_me_host and (total_players >= 2)
    else:
        start_enabled = is_me_host and (total_players == 2)
        
    start_hover = room_start_game_rect.collidepoint(mouse_pos) and start_enabled
    start_bg = (20, 140, 80) if start_enabled else (35, 40, 45)
    start_hover_bg = (30, 180, 100) if start_enabled else (35, 40, 45)
    start_txt = (240, 240, 250) if start_enabled else (110, 115, 120)
    draw_button(surface, room_start_game_rect, "開始遊戲對決 (Start)", start_bg, start_hover_bg, start_txt, start_hover, get_font(15, bold=True))
    
    if not is_me_host:
        font_tip = get_font(16)
        tip_surf = font_tip.render("請等待房主開始遊戲...", True, (200, 200, 100))
        surface.blit(tip_surf, (540, 230))
    
    leave_hover = room_leave_rect.collidepoint(mouse_pos)
    draw_button(surface, room_leave_rect, "退出房間 (Leave)", (120, 40, 40), (160, 50, 50), (250, 240, 240), leave_hover, get_font(15, bold=True))

def draw_game_scene(surface, mouse_pos):
    if game.game_phase == LOBBY:
        draw_lobby_scene(surface, mouse_pos)
    elif game.game_phase == ROOM_LOBBY:
        draw_room_lobby_scene(surface, mouse_pos)


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
    
    game.game_phase = LOBBY
    
    # 房間大廳非同步事件掛鉤
    def on_lobby_net_receive(data):
        global ecard_game_instance, rps_game_instance, connection_status_msg, connection_status_color
        action = data.get("action")
        
        if action == "ROOM_INFO_UPDATE":
            if net_manager.game_type == "ecard":
                connection_status_msg = "已開房，等待對手加入..." if net_manager.is_host else "已連線，等待對手加入..."
                connection_status_color = (200, 200, 100)
            else:
                if game.game_phase == LOBBY:
                    game.game_phase = ROOM_LOBBY
                    connection_status_msg = "已進入大廳房間"
                    connection_status_color = (100, 255, 100)
                
        elif action == "GAME_START":
            # 遊戲啟動，跳轉進入遊戲對局畫面
            opps = data.get("opponents", [])
            opp_name = data.get("opponent_name", "對手")
            if opps:
                net_manager.opponent_name = opps[0]
            else:
                net_manager.opponent_name = opp_name
                
            print(f"[Lobby] Received GAME_START. Opponents list: {opps or opp_name}")
            
            game.wins_player = 0
            game.wins_cpu = 0
            
            if net_manager.game_type == "rps":
                game.game_phase = RPS_GAME
                # 多人模式下皆連線中央伺服器，is_offline 為 False
                rps_game_instance = restricted_rps_game.RestrictedRPSGame(screen, game, net_manager, is_offline=False)
            else:
                game.game_phase = 0
                ecard_game_instance = ecard_ui.EcardGameUI(screen, game, net_manager, is_offline=False)
                
        elif action == "error":
            connection_status_msg = data.get("message", "連線錯誤")
            connection_status_color = (255, 100, 100)

    net_manager.on_receive_message = on_lobby_net_receive
    
    running = True
    while running:
        dt = clock.tick(FPS)
        mouse_pos = pygame.mouse.get_pos()
        
        # 全域輪詢網路通訊
        net_manager.poll()
        
        # 斷線後自動安全跳回首頁
        if not net_manager.is_connected and connection_mode != "OFFLINE" and game.game_phase == ROOM_LOBBY:
            game.game_phase = LOBBY
            connection_status_msg = "連線已中斷，大廳已解散"
            connection_status_color = (255, 100, 100)
            
        # 若回到大廳，自動重設 Lobby 訊息接收處理器
        if game.game_phase == LOBBY and net_manager.on_receive_message != on_lobby_net_receive:
            net_manager.on_receive_message = on_lobby_net_receive
            
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
                    if ip_input_rect.collidepoint(mouse_pos) and connection_mode == "CLIENT":
                        active_input_field = "IP"
                    elif port_input_rect.collidepoint(mouse_pos) and connection_mode != "OFFLINE":
                        active_input_field = "PORT"
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
                            connection_status_msg = "切換為大廳房主模式，啟動時背景將自動開啟中央伺服器"
                            connection_status_color = (200, 200, 100)
                        elif connection_mode == "HOST":
                            connection_mode = "CLIENT"
                            connection_status_msg = "切換為大廳客機模式，啟動時將連線加入對方大廳"
                            connection_status_color = (200, 200, 100)
                        else:
                            connection_mode = "OFFLINE"
                            connection_status_msg = "目前為單機離線模式，可直接啟動對決"
                            connection_status_color = (150, 150, 160)
                            
                    # 點擊測試連線按鈕 (僅在 CLIENT 模式下啟用)
                    elif test_conn_rect.collidepoint(mouse_pos) and connection_mode == "CLIENT":
                        if not net_manager.is_connecting and not net_manager.is_connected:
                            test_connection_async()
                        
                    # 點擊啟動「國王與奴隸」遊戲
                    elif game_ecard_rect.collidepoint(mouse_pos):
                        net_manager.player_name = player_name
                        net_manager.game_type = "ecard"
                        if connection_mode == "OFFLINE":
                            ecard_game_instance = ecard_ui.EcardGameUI(screen, game, net_manager, is_offline=True)
                        elif connection_mode == "HOST":
                            connection_status_msg = "正在建立並連線本地中央伺服器..."
                            connection_status_color = (200, 200, 100)
                            success, msg = net_manager.host(server_port)
                            if not success:
                                connection_status_msg = f"開房失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                        elif connection_mode == "CLIENT":
                            if not net_manager.is_connecting and not net_manager.is_connected:
                                connection_status_msg = "正在連線加入房主的中央伺服器..."
                                connection_status_color = (200, 200, 100)
                                success, msg = net_manager.connect(server_ip, server_port)
                                if not success:
                                    connection_status_msg = f"連線加入失敗: {msg}"
                                    connection_status_color = (255, 100, 100)
                                
                    # 點擊啟動「限定剪刀石頭布」遊戲
                    elif game_locked_rect.collidepoint(mouse_pos):
                        net_manager.player_name = player_name
                        net_manager.game_type = "rps"
                        if connection_mode == "OFFLINE":
                            game.game_phase = RPS_GAME
                            rps_game_instance = restricted_rps_game.RestrictedRPSGame(screen, game, net_manager, is_offline=True)
                        elif connection_mode == "HOST":
                            connection_status_msg = "正在建立並連線本地中央伺服器..."
                            connection_status_color = (200, 200, 100)
                            success, msg = net_manager.host(server_port)
                            if not success:
                                connection_status_msg = f"開房失敗: {msg}"
                                connection_status_color = (255, 100, 100)
                        elif connection_mode == "CLIENT":
                            if not net_manager.is_connecting and not net_manager.is_connected:
                                connection_status_msg = "正在連線加入房主的中央伺服器..."
                                connection_status_color = (200, 200, 100)
                                success, msg = net_manager.connect(server_ip, server_port)
                                if not success:
                                    connection_status_msg = f"連線加入失敗: {msg}"
                                    connection_status_color = (255, 100, 100)
                                
                    # 點擊離開程式
                    elif exit_btn_rect.collidepoint(mouse_pos):
                        running = False
                        
                # ------------------------------------------
                # 房間大廳 (ROOM_LOBBY) 狀態下的點擊偵測
                # ------------------------------------------
                elif game.game_phase == ROOM_LOBBY:
                    is_me_host = (net_manager.player_name == net_manager.room_host)
                    total_players = len(net_manager.room_players)
                    
                    # 房主新增機器人
                    bot_limit = 4 if net_manager.game_type == "rps" else 2
                    if room_add_bot_rect.collidepoint(mouse_pos) and is_me_host and total_players < bot_limit:
                        net_manager.send_data({"action": "ADD_BOT"})
                        
                    # 房主移除機器人
                    elif room_remove_bot_rect.collidepoint(mouse_pos) and is_me_host and any(p.get("is_bot", False) for p in net_manager.room_players):
                        net_manager.send_data({"action": "REMOVE_BOT"})
                        
                    # 房主啟動遊戲 (直接送出 START_GAME_REQ 到中央伺服器)
                    elif room_start_game_rect.collidepoint(mouse_pos):
                        if net_manager.game_type == "rps":
                            click_start_enabled = is_me_host and (total_players >= 2)
                        else:
                            click_start_enabled = is_me_host and (total_players == 2)
                        if click_start_enabled:
                            net_manager.send_data({"action": "START_GAME_REQ"})
                        
                    # 退出房間
                    elif room_leave_rect.collidepoint(mouse_pos):
                        net_manager.disconnect()
                        game.game_phase = LOBBY
                        connection_status_msg = "已離開房間並中斷連線"
                        connection_status_color = (150, 150, 160)
                
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
                                if len(server_ip) < 15:
                                    server_ip += char
                            elif active_input_field == "PORT":
                                if len(server_port) < 5 and char.isdigit():
                                    server_port += char
                            elif active_input_field == "NAME":
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
            if rps_game_instance is not None:
                rps_game_instance.cleanup()
            ecard_game_instance = None
            rps_game_instance = None
            
            draw_game_scene(screen, mouse_pos)
        
        pygame.display.flip()
        
    net_manager.disconnect()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
