# filepath: C:\Users\ethan\Desktop\Project\src\restricted_rps\restricted_rps_game.py
"""
Restricted Rock-Paper-Scissors (限定剪刀石頭布) - 2D RPG 拓展模組
=============================================================

本模組提供「星之船」限定剪刀石頭布對戰場景，包含：
1. 2D RPG 俯視視角地圖探索（鍵盤 WASD / 鍵盤方向鍵控制角色移動）。
2. 相機平滑跟隨 (Scrolling Camera) 與障礙物碰撞體 (AABB Collision)。
3. NPC 漫遊 AI、隨機交談、NPC間的離線對戰與交易模擬日誌。
4. 深度交易評估系統 (NPC 智慧估值 AI)：根據卡牌分佈方差與星星需求評估交易提案。
5. 獨立的卡牌對決介面 (Rock, Paper, Scissors) 及輸贏動畫。
"""

import pygame
import sys
import random
import math
from typing import Any
from src.common.ui_components import get_font, draw_rect_alpha, draw_glow, draw_button, draw_gradient_background

# ==========================================
# 局部狀態常數 (RPG 專用子狀態)
# ==========================================
SETUP = 0
RPG_WALK = 1
DIALOGUE = 2
TRADE = 3
BATTLE = 4
SUMMARY = 5

# 角色半徑
CHAR_RADIUS = 18

class RPGObstacle:
    """RPG 地圖碰撞體障礙物"""
    def __init__(self, rect, color, label=""):
        self.rect = rect
        self.color = color
        self.label = label

    def draw(self, surface, camera_x, camera_y):
        draw_rect = self.rect.move(-camera_x, -camera_y)
        pygame.draw.rect(surface, self.color, draw_rect, border_radius=6)
        pygame.draw.rect(surface, (self.color[0]+30, self.color[1]+30, self.color[2]+30), draw_rect, width=1, border_radius=6)
        if self.label:
            font = get_font(12)
            lbl = font.render(self.label, True, (130, 130, 140))
            surface.blit(lbl, lbl.get_rect(center=draw_rect.center))

class RestrictedRPSGame:
    def __init__(self, surface, game_manager, net_manager=None, is_offline=True):
        self.surface = surface
        self.game_manager = game_manager  # 外部主狀態機 EcardGame 的引用
        self.net_manager: Any = net_manager
        self.is_offline = is_offline
        
        # 遊戲初始化設定
        self.player_count = 8  # 預設自選人數為 8 人
        
        # 鍵盤按鍵狀態追蹤
        self.keys_pressed = set()
        
        # 玩家手牌與星星
        self.player_stars = 3
        self.player_cards = {"rock": 4, "paper": 4, "scissors": 4}
        
        # 玩家與對手名字
        self.player_name = self.net_manager.player_name if (self.net_manager and hasattr(self.net_manager, "player_name")) else "主角 (Player)"
        if self.is_offline:
            self.opponent_name = "對手"
        else:
            self.opponent_name = self.net_manager.opponent_name if (self.net_manager and hasattr(self.net_manager, "opponent_name") and self.net_manager.opponent_name not in ("Opponent", "")) else "對手"
        
        # RPG 地圖大小
        self.world_width = 1600
        self.world_height = 1200
        
        # 玩家座標與速度
        self.player_x = 800.0
        self.player_y = 1000.0
        self.player_speed = 220.0
        
        # 相機座標
        self.camera_x = 0
        self.camera_y = 0
        
        # 障礙物列表
        self.obstacles = []
        self._init_map_obstacles()
        
        # NPC 列表
        self.npcs = []
        self.npc_pool = [
            {"name": "船井", "color": (220, 80, 80), "desc": "狡猾的欺詐者。喜歡出石頭。"},
            {"name": "古畑", "color": (80, 200, 120), "desc": "尋求平等的盟友。樂意平衡手牌。"},
            {"name": "石田", "color": (150, 150, 150), "desc": "焦慮的中年人。極度缺星，哀求交易。"},
            {"name": "安藤", "color": (220, 130, 180), "desc": "不可信任的小人。會提出貪婪的條件。"},
            {"name": "佐原", "color": (220, 200, 60), "desc": "熱血的賭徒。喜歡對戰多於交易。"},
            {"name": "北見", "color": (160, 100, 220), "desc": "冷靜的戰略家。會計算對手出牌規律。"},
            {"name": "高尾", "color": (240, 150, 50), "desc": "隨性的玩家。容易進行卡牌等值交換。"},
            {"name": "三好", "color": (60, 170, 170), "desc": "膽小的追隨者。不太願意主動對戰。"},
            {"name": "光山", "color": (50, 120, 200), "desc": "見風轉舵的人。手牌好時會非常自滿。"},
            {"name": "前田", "color": (100, 100, 160), "desc": "沈穩的旁觀者。行為中規中矩。"}
        ]
        
        # 控制是否顯示日誌面板
        self.show_logs = True

        # 動態提示日誌
        self.logs = ["遊戲開始！目前置身於『希望之船埃斯波瓦爾』大廳。"]
        self.log_timer = 0.0
        
        # 當前互動對象
        self.active_npc: Any = None
        self.dialogue_index = 0
        
        # 對戰狀態變數
        self.battle_phase = "select"  # "select", "reveal", "result"
        self.player_selected_card: Any = None
        self.npc_selected_card: Any = None
        self.battle_result_msg = ""
        self.battle_result_color = (255, 255, 255)
        self.battle_anim_timer = 0
        
        # 交易狀態變數
        # 玩家準備提供的卡牌/星星，以及向NPC要求的卡牌/星星
        self.trade_offer = {
            "give_rock": 0, "give_paper": 0, "give_scissors": 0, "give_star": 0,
            "want_rock": 0, "want_paper": 0, "want_scissors": 0, "want_star": 0
        }
        self.trade_message = "請在下方調整交易的卡牌或星星數量。"
        self.trade_msg_color = (180, 180, 190)
        
        # 按鈕感應區暫存
        self.btn_rects = {}
        
        # 卡牌縮放比例
        self.card_w = 120
        self.card_h = 180
        
        # 對手資產 (聯機模式用)
        self.opponent_stars = 3
        self.opponent_cards = {"rock": 4, "paper": 4, "scissors": 4}
        self.opponent_x = 800.0
        self.opponent_y = 1000.0
        self.opponent_selected_card: Any = None
        
        self.pending_request: Any = None # {"type": "battle" | "trade", "sender": name}
        self.sent_request: Any = None # "battle" | "trade"
        
        self.trade_self_ready = False
        self.trade_opp_ready = False
        
        if self.net_manager and not self.is_offline:
            self.net_manager.on_receive_message = self.on_net_receive
            # 同步名字
            self.net_manager.send_data({"action": "handshake", "name": self.player_name})
            
        # 若是聯機模式，直接跳過設定畫面進入 RPGwalk
        if not self.is_offline:
            self.state = RPG_WALK
        else:
            self.state = SETUP

    def cleanup(self):
        if self.net_manager:
            self.net_manager.on_receive_message = None

    def _get_interactable_opponent(self):
        if self.is_offline:
            return False
        dist = math.hypot(self.player_x - self.opponent_x, self.player_y - self.opponent_y)
        if dist < 65:
            return True
        return False

    def _send_interact_request(self, req_type):
        if self.sent_request:
            return
        self.sent_request = req_type
        self.net_manager.send_data({
            "action": "interact_req",
            "type": req_type
        })
        self.add_log(f"已向 {self.opponent_name} 發送 {req_type} 邀請...")

    def on_net_receive(self, data):
        action = data.get("action")
        
        if action == "sync_names":
            self.opponent_name = data.get("player_name", self.opponent_name)
            
        elif action == "sync_pos":
            self.opponent_x = data.get("x", self.opponent_x)
            self.opponent_y = data.get("y", self.opponent_y)
            
        elif action == "interact_req":
            req_type = data.get("type")
            self.pending_request = {"type": req_type, "sender": self.opponent_name}
            
        elif action == "interact_resp":
            req_type = data.get("type")
            accepted = data.get("accepted", False)
            if self.sent_request == req_type:
                self.sent_request = None
                if accepted:
                    self.add_log(f"{self.opponent_name} 接受了您的邀請！")
                    if req_type == "battle":
                        self._start_battle_mode()
                    elif req_type == "trade":
                        self._start_trade_mode()
                else:
                    self.add_log(f"{self.opponent_name} 拒絕了您的邀請。")
                    
        elif action == "play_card":
            self.opponent_selected_card = data.get("card_type")
            if self.battle_phase == "waiting" and self.opponent_selected_card:
                self._resolve_online_battle()
                
        elif action == "sync_trade":
            opp_offer = data.get("offer")
            if opp_offer:
                self.trade_offer["want_rock"] = opp_offer["give_rock"]
                self.trade_offer["want_paper"] = opp_offer["give_paper"]
                self.trade_offer["want_scissors"] = opp_offer["give_scissors"]
                self.trade_offer["want_star"] = opp_offer["give_star"]
                
                self.trade_offer["give_rock"] = opp_offer["want_rock"]
                self.trade_offer["give_paper"] = opp_offer["want_paper"]
                self.trade_offer["give_scissors"] = opp_offer["want_scissors"]
                self.trade_offer["give_star"] = opp_offer["want_star"]
                
                self.trade_self_ready = False
                self.trade_opp_ready = False
                self.trade_message = "對手調整了提案，請重新確認。"
                self.trade_msg_color = (180, 180, 190)
                
        elif action == "confirm_trade":
            self.trade_opp_ready = True
            self.trade_message = f"{self.opponent_name} 已同意此提案，請您確認以完成交易。"
            self.trade_msg_color = (100, 200, 100)
            if self.trade_self_ready and self.trade_opp_ready:
                self._execute_online_trade()
                
        elif action == "cancel_trade":
            self.add_log(f"[交易] {self.opponent_name} 取消了交易。")
            self.state = RPG_WALK

    def _resolve_online_battle(self):
        self.battle_phase = "result"
        self.player_cards[self.player_selected_card] -= 1
        self.opponent_cards[self.opponent_selected_card] -= 1
        
        p = self.player_selected_card
        o = self.opponent_selected_card
        
        if p == o:
            self.battle_result_msg = "雙方平手！卡牌消耗但星數不變。"
            self.battle_result_color = (130, 160, 240)
            log_msg = f"[對戰] 玩家與 {self.opponent_name} 出現平局 ({self._trans_card(p)})！"
        elif (p == "rock" and o == "scissors") or (p == "paper" and o == "rock") or (p == "scissors" and o == "paper"):
            self.battle_result_msg = f"您獲勝了！奪得 1 顆星星！"
            self.battle_result_color = (255, 215, 0)
            self.player_stars += 1
            self.opponent_stars -= 1
            log_msg = f"[對戰] 玩家擊敗 {self.opponent_name}，贏取 1 顆星星！"
        else:
            self.battle_result_msg = f"您輸了... 失去 1 顆星星。"
            self.battle_result_color = (240, 50, 50)
            self.player_stars -= 1
            self.opponent_stars += 1
            log_msg = f"[對戰] {self.opponent_name} 擊敗玩家，贏取 1 顆星星！"
            
        self.add_log(log_msg)

    def _execute_online_trade(self):
        self.player_cards["rock"] += self.trade_offer["want_rock"] - self.trade_offer["give_rock"]
        self.player_cards["paper"] += self.trade_offer["want_paper"] - self.trade_offer["give_paper"]
        self.player_cards["scissors"] += self.trade_offer["want_scissors"] - self.trade_offer["give_scissors"]
        self.player_stars += self.trade_offer["want_star"] - self.trade_offer["give_star"]
        
        self.opponent_cards["rock"] += self.trade_offer["give_rock"] - self.trade_offer["want_rock"]
        self.opponent_cards["paper"] += self.trade_offer["give_paper"] - self.trade_offer["want_paper"]
        self.opponent_cards["scissors"] += self.trade_offer["give_scissors"] - self.trade_offer["want_scissors"]
        self.opponent_stars += self.trade_offer["give_star"] - self.trade_offer["want_star"]
        
        self.add_log(f"[交易] 玩家與 {self.opponent_name} 完成交易！")
        self.state = RPG_WALK

    def _draw_request_popup(self, surface, mouse_pos):
        draw_rect_alpha(surface, (10, 10, 15, 180), pygame.Rect(0, 0, 1000, 700))
        box = pygame.Rect(300, 250, 400, 200)
        pygame.draw.rect(surface, (25, 25, 35), box, border_radius=10)
        pygame.draw.rect(surface, (100, 180, 255), box, width=2, border_radius=10)
        
        req_type = self.pending_request["type"]
        req_type_zh = "對決 (Battle)" if req_type == "battle" else ("交易 (Trade)" if req_type == "trade" else "對話 (Dialogue)")
        txt1 = get_font(16, bold=True).render(f"來自 {self.opponent_name} 的邀請", True, (255, 215, 0))
        txt2 = get_font(14).render(f"對方邀請您進行 {req_type_zh}", True, (220, 220, 230))
        surface.blit(txt1, txt1.get_rect(center=(500, 290)))
        surface.blit(txt2, txt2.get_rect(center=(500, 330)))
        
        btn_accept = pygame.Rect(340, 380, 140, 40)
        ah = btn_accept.collidepoint(mouse_pos)
        draw_button(surface, btn_accept, "接受 (Accept)", (50, 150, 50), (70, 180, 70), (255, 255, 255), ah, get_font(13, bold=True))
        self.btn_rects["btn_req_accept"] = btn_accept
        
        btn_reject = pygame.Rect(520, 380, 140, 40)
        rh = btn_reject.collidepoint(mouse_pos)
        draw_button(surface, btn_reject, "拒絕 (Reject)", (150, 50, 50), (180, 70, 70), (255, 255, 255), rh, get_font(13, bold=True))
        self.btn_rects["btn_req_reject"] = btn_reject
        
    def _init_map_obstacles(self):
        """初始化 2D 地圖障礙物"""
        # 地圖四周外框牆壁
        thickness = 40
        self.obstacles.append(RPGObstacle(pygame.Rect(0, 0, self.world_width, thickness), (28, 30, 38), "北側封閉牆"))
        self.obstacles.append(RPGObstacle(pygame.Rect(0, self.world_height - thickness, self.world_width, thickness), (28, 30, 38), "南側出入口"))
        self.obstacles.append(RPGObstacle(pygame.Rect(0, 0, thickness, self.world_height), (28, 30, 38)))
        self.obstacles.append(RPGObstacle(pygame.Rect(self.world_width - thickness, 0, thickness, self.world_height), (28, 30, 38)))
        
        # 大廳中央柱子
        self.obstacles.append(RPGObstacle(pygame.Rect(400, 300, 80, 80), (45, 48, 58), "鋼鐵立柱 A"))
        self.obstacles.append(RPGObstacle(pygame.Rect(1120, 300, 80, 80), (45, 48, 58), "鋼鐵立柱 B"))
        self.obstacles.append(RPGObstacle(pygame.Rect(400, 820, 80, 80), (45, 48, 58), "鋼鐵立柱 C"))
        self.obstacles.append(RPGObstacle(pygame.Rect(1120, 820, 80, 80), (45, 48, 58), "鋼鐵立柱 D"))
        
        # 吧檯櫃檯
        self.obstacles.append(RPGObstacle(pygame.Rect(950, 100, 350, 70), (35, 30, 45), "奢華吧檯區"))
        
        # 中央長椅桌案
        self.obstacles.append(RPGObstacle(pygame.Rect(650, 560, 300, 80), (22, 28, 40), "對決交涉桌 (長)"))
        
        # 安全房間分隔牆 (左上角安全區)
        self.obstacles.append(RPGObstacle(pygame.Rect(40, 260, 240, 20), (35, 35, 40), "星之別館護欄"))
        self.obstacles.append(RPGObstacle(pygame.Rect(280, 40, 20, 150), (35, 35, 40)))
        
    def _spawn_npcs(self):
        """根據選擇的總人數動態生成 NPC 並隨機放置於大廳"""
        self.npcs = []
        # 可生成 NPC 數量 = 總人數 - 1
        spawn_count = min(self.player_count - 1, len(self.npc_pool))
        
        # 隨機打亂候選 NPC 池
        pool = list(self.npc_pool)
        random.shuffle(pool)
        
        for i in range(spawn_count):
            meta = pool[i]
            # 隨機位置避開障礙物
            valid = False
            nx, ny = 0.0, 0.0
            while not valid:
                nx = float(random.randint(100, self.world_width - 100))
                ny = float(random.randint(100, self.world_height - 100))
                if not self._check_collision_any(nx, ny, CHAR_RADIUS):
                    valid = True
                    
            npc_obj = {
                "name": meta["name"],
                "color": meta["color"],
                "desc": meta["desc"],
                "x": nx,
                "y": ny,
                "vx": float(random.choice([-1, 1]) * random.randint(30, 60)),
                "vy": float(random.choice([-1, 1]) * random.randint(30, 60)),
                "stars": 3,
                "cards": {"rock": 4, "paper": 4, "scissors": 4},
                "status": "WANDERING",  # "WANDERING", "IDLE", "SAFE", "LOSE"
                "timer": random.uniform(2.0, 5.0),
                "is_hovered": False
            }
            self.npcs.append(npc_obj)

    def _check_collision_any(self, x, y, radius):
        """判斷是否與任何障礙物碰撞"""
        for obs in self.obstacles:
            # 圓形 vs AABB 碰撞檢測
            cx = max(obs.rect.left, min(x, obs.rect.right))
            cy = max(obs.rect.top, min(y, obs.rect.bottom))
            dx = x - cx
            dy = y - cy
            if (dx*dx + dy*dy) < radius*radius:
                return True
        return False

    def add_log(self, text):
        """寫入即時對決日誌"""
        self.logs.append(text)
        if len(self.logs) > 30:
            self.logs.pop(0)

    # ==========================================
    # 事件處理 (Event Handling)
    # ==========================================
    def handle_event(self, event, mouse_pos):
        # 追蹤按鍵狀態
        if event.type == pygame.KEYDOWN:
            self.keys_pressed.add(event.key)
        elif event.type == pygame.KEYUP:
            if event.key in self.keys_pressed:
                self.keys_pressed.remove(event.key)
                
        if self.state == SETUP:
            self._handle_setup_events(event, mouse_pos)
        elif self.state == RPG_WALK:
            self._handle_rpg_events(event, mouse_pos)
        elif self.state == DIALOGUE:
            self._handle_dialogue_events(event, mouse_pos)
        elif self.state == TRADE:
            self._handle_trade_events(event, mouse_pos)
        elif self.state == BATTLE:
            self._handle_battle_events(event, mouse_pos)
        elif self.state == SUMMARY:
            self._handle_summary_events(event, mouse_pos)

    def _handle_setup_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 自選人數按鈕
            for count in [4, 8, 12, 16]:
                rect_name = f"btn_count_{count}"
                if rect_name in self.btn_rects and self.btn_rects[rect_name].collidepoint(mouse_pos):
                    self.player_count = count
            
            # 開始遊戲按鈕
            if "btn_start" in self.btn_rects and self.btn_rects["btn_start"].collidepoint(mouse_pos):
                # 重新初始化數據
                self.player_stars = 3
                self.player_cards = {"rock": 4, "paper": 4, "scissors": 4}
                self.player_x = 800.0
                self.player_y = 1000.0
                self.logs = ["遊戲開始！目前置身於『希望之船埃斯波瓦爾』大廳。"]
                self._spawn_npcs()
                self.state = RPG_WALK
                
            # 返回大廳按鈕
            if "btn_back_lobby" in self.btn_rects and self.btn_rects["btn_back_lobby"].collidepoint(mouse_pos):
                self.game_manager.game_phase = -1  # LOBBY

    def _handle_rpg_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 處理連線邀請點擊
            if self.pending_request:
                if "btn_req_accept" in self.btn_rects and self.btn_rects["btn_req_accept"].collidepoint(mouse_pos):
                    req_type = self.pending_request["type"]
                    self.net_manager.send_data({
                        "action": "interact_resp",
                        "type": req_type,
                        "accepted": True
                    })
                    self.pending_request = None
                    if req_type == "battle":
                        self._start_battle_mode()
                    elif req_type == "trade":
                        self._start_trade_mode()
                    return
                elif "btn_req_reject" in self.btn_rects and self.btn_rects["btn_req_reject"].collidepoint(mouse_pos):
                    req_type = self.pending_request["type"]
                    self.net_manager.send_data({
                        "action": "interact_resp",
                        "type": req_type,
                        "accepted": False
                    })
                    self.pending_request = None
                    return

            # 點擊頭部返回大廳按鈕
            if "btn_back_lobby" in self.btn_rects and self.btn_rects["btn_back_lobby"].collidepoint(mouse_pos):
                self.game_manager.game_phase = -1  # LOBBY
                return
                
            # 點擊日誌切換按鈕
            if "btn_toggle_logs" in self.btn_rects and self.btn_rects["btn_toggle_logs"].collidepoint(mouse_pos):
                self.show_logs = not self.show_logs
                return
            
            # 滑鼠點擊靠近的 NPC 也可以觸發選單
            for npc in self.npcs:
                if npc["status"] in ("SAFE", "LOSE"):
                    continue
                # 計算與玩家距離
                dist = math.hypot(npc["x"] - self.player_x, npc["y"] - self.player_y)
                if dist < 65:  # 當靠近且點擊 NPC 時
                    # 換算畫面點擊點
                    screen_npc_x = npc["x"] - self.camera_x
                    screen_npc_y = npc["y"] - self.camera_y
                    click_dist = math.hypot(mouse_pos[0] - screen_npc_x, mouse_pos[1] - screen_npc_y)
                    if click_dist < CHAR_RADIUS + 10:
                        self.active_npc = npc
                        self.state = DIALOGUE
                        self.dialogue_index = 0
                        break

        elif event.type == pygame.KEYDOWN:
            if self.pending_request:
                if event.key == pygame.K_y:
                    req_type = self.pending_request["type"]
                    self.net_manager.send_data({
                        "action": "interact_resp",
                        "type": req_type,
                        "accepted": True
                    })
                    self.pending_request = None
                    if req_type == "battle":
                        self._start_battle_mode()
                    elif req_type == "trade":
                        self._start_trade_mode()
                    return
                elif event.key == pygame.K_n:
                    req_type = self.pending_request["type"]
                    self.net_manager.send_data({
                        "action": "interact_resp",
                        "type": req_type,
                        "accepted": False
                    })
                    self.pending_request = None
                    return

            # 快捷鍵切換日誌顯示
            if event.key == pygame.K_l:
                self.show_logs = not self.show_logs
                return
                
            # 優先處理連線玩家互動
            if not self.is_offline and self._get_interactable_opponent():
                if event.key == pygame.K_b:
                    self._send_interact_request("battle")
                elif event.key == pygame.K_t:
                    self._send_interact_request("trade")
                elif event.key in (pygame.K_e, pygame.K_RETURN):
                    self._send_interact_request("battle")
                return

            # 使用快捷鍵進行靠近 NPC 互動
            closest_npc = self._get_closest_active_npc()
            if closest_npc:
                if event.key == pygame.K_e or event.key == pygame.K_RETURN:
                    self.active_npc = closest_npc
                    self.state = DIALOGUE
                    self.dialogue_index = 0
                elif event.key == pygame.K_b:
                    self.active_npc = closest_npc
                    self._start_battle_mode()
                elif event.key == pygame.K_t:
                    self.active_npc = closest_npc
                    self._start_trade_mode()

    def _handle_dialogue_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 點擊對話框關閉
            if "btn_dlg_close" in self.btn_rects and self.btn_rects["btn_dlg_close"].collidepoint(mouse_pos):
                self.state = RPG_WALK
                return
            
            # 對戰按鈕
            if "btn_dlg_battle" in self.btn_rects and self.btn_rects["btn_dlg_battle"].collidepoint(mouse_pos):
                self._start_battle_mode()
                return
                
            # 交易按鈕
            if "btn_dlg_trade" in self.btn_rects and self.btn_rects["btn_dlg_trade"].collidepoint(mouse_pos):
                self._start_trade_mode()
                return
                
            # 點擊任意對話區域切換台詞或關閉
            dlg_box = pygame.Rect(100, 480, 800, 160)
            if dlg_box.collidepoint(mouse_pos):
                self.state = RPG_WALK

    def _handle_trade_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 取消與返回
            if "btn_trade_cancel" in self.btn_rects and self.btn_rects["btn_trade_cancel"].collidepoint(mouse_pos):
                if not self.is_offline:
                    self.net_manager.send_data({
                        "action": "cancel_trade"
                    })
                self.state = RPG_WALK
                return
            
            if self.is_offline:
                # 調節我方提供的物件 (give)
                self._adjust_trade("give_rock", 1, self.player_cards["rock"], mouse_pos)
                self._adjust_trade("give_paper", 1, self.player_cards["paper"], mouse_pos)
                self._adjust_trade("give_scissors", 1, self.player_cards["scissors"], mouse_pos)
                self._adjust_trade("give_star", 1, self.player_stars - 1, mouse_pos)  # 保留至少一顆星，防自殺
                
                # 調節對方提供的物件 (want)
                self._adjust_trade("want_rock", 1, self.active_npc["cards"]["rock"], mouse_pos)
                self._adjust_trade("want_paper", 1, self.active_npc["cards"]["paper"], mouse_pos)
                self._adjust_trade("want_scissors", 1, self.active_npc["cards"]["scissors"], mouse_pos)
                self._adjust_trade("want_star", 1, self.active_npc["stars"] - 1, mouse_pos)
                
                # 點擊確認發起交易
                if "btn_trade_confirm" in self.btn_rects and self.btn_rects["btn_trade_confirm"].collidepoint(mouse_pos):
                    self._execute_npc_trade()
            else:
                # Online mode
                old_offer = self.trade_offer.copy()
                self._adjust_trade("give_rock", 1, self.player_cards["rock"], mouse_pos)
                self._adjust_trade("give_paper", 1, self.player_cards["paper"], mouse_pos)
                self._adjust_trade("give_scissors", 1, self.player_cards["scissors"], mouse_pos)
                self._adjust_trade("give_star", 1, self.player_stars - 1, mouse_pos)
                
                self._adjust_trade("want_rock", 1, self.opponent_cards["rock"], mouse_pos)
                self._adjust_trade("want_paper", 1, self.opponent_cards["paper"], mouse_pos)
                self._adjust_trade("want_scissors", 1, self.opponent_cards["scissors"], mouse_pos)
                self._adjust_trade("want_star", 1, self.opponent_stars - 1, mouse_pos)
                
                if self.trade_offer != old_offer:
                    self.net_manager.send_data({
                        "action": "sync_trade",
                        "offer": self.trade_offer
                    })
                    self.trade_self_ready = False
                    self.trade_opp_ready = False
                    self.trade_message = "請在下方調整交易的卡牌或星星數量。"
                    self.trade_msg_color = (180, 180, 190)
                    
                if "btn_trade_confirm" in self.btn_rects and self.btn_rects["btn_trade_confirm"].collidepoint(mouse_pos):
                    self.trade_self_ready = True
                    self.net_manager.send_data({
                        "action": "confirm_trade"
                    })
                    self.trade_message = "已確認提案，等待對手確認..."
                    self.trade_msg_color = (100, 200, 100)
                    
                    if self.trade_self_ready and self.trade_opp_ready:
                        self._execute_online_trade()

    def _handle_battle_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.battle_phase == "select":
                # 選擇卡牌
                for card_type in ["rock", "paper", "scissors"]:
                    rect_name = f"btn_card_{card_type}"
                    if rect_name in self.btn_rects and self.btn_rects[rect_name].collidepoint(mouse_pos):
                        if self.player_cards[card_type] > 0:
                            self.player_selected_card = card_type
                
                # 確定出牌
                if "btn_battle_confirm" in self.btn_rects and self.btn_rects["btn_battle_confirm"].collidepoint(mouse_pos):
                    if self.player_selected_card:
                        if not self.is_offline:
                            self.battle_phase = "waiting"
                            self.net_manager.send_data({
                                "action": "play_card",
                                "card_type": self.player_selected_card
                            })
                            if self.opponent_selected_card:
                                self._resolve_online_battle()
                        else:
                            self._resolve_battle_clash()
                            
            elif self.battle_phase == "result":
                # 返回地圖按鈕
                if "btn_battle_finish" in self.btn_rects and self.btn_rects["btn_battle_finish"].collidepoint(mouse_pos):
                    self.state = RPG_WALK
                    self.player_selected_card = None
                    self.opponent_selected_card = None
                    self._check_game_over_conditions()

    def _handle_summary_events(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if "btn_back_lobby" in self.btn_rects and self.btn_rects["btn_back_lobby"].collidepoint(mouse_pos):
                self.game_manager.game_phase = -1  # LOBBY

    # ==========================================
    # 邏輯與評估 (Logic & Evaluation)
    # ==========================================
    def _get_closest_active_npc(self):
        """尋找距離玩家最近且活躍的 NPC"""
        closest = None
        min_dist = 60.0
        for npc in self.npcs:
            if npc["status"] in ("SAFE", "LOSE"):
                continue
            dist = math.hypot(npc["x"] - self.player_x, npc["y"] - self.player_y)
            if dist < min_dist:
                min_dist = dist
                closest = npc
        return closest

    def _start_battle_mode(self):
        """進入對決介面"""
        self.state = BATTLE
        self.battle_phase = "select"
        self.player_selected_card = None
        self.npc_selected_card = None
        self.battle_result_msg = ""
        self.battle_anim_timer = 0
        
    def _start_trade_mode(self):
        """進入交易板介面"""
        self.state = TRADE
        self.trade_offer = {
            "give_rock": 0, "give_paper": 0, "give_scissors": 0, "give_star": 0,
            "want_rock": 0, "want_paper": 0, "want_scissors": 0, "want_star": 0
        }
        self.trade_message = "請在下方調整交易的卡牌或星星數量。"
        self.trade_msg_color = (180, 180, 190)

    def _adjust_trade(self, field, value, max_limit, mouse_pos):
        """微調交易的數字"""
        plus_btn = f"btn_trade_plus_{field}"
        minus_btn = f"btn_trade_minus_{field}"
        
        if plus_btn in self.btn_rects and self.btn_rects[plus_btn].collidepoint(mouse_pos):
            if self.trade_offer[field] < max_limit:
                self.trade_offer[field] += value
                
        elif minus_btn in self.btn_rects and self.btn_rects[minus_btn].collidepoint(mouse_pos):
            if self.trade_offer[field] > 0:
                self.trade_offer[field] -= value

    def _execute_npc_trade(self):
        """【智慧估值 AI】NPC 評估是否接受玩家提出的交易提案"""
        # 1. 安全檢查：防止空手套白狼或無效交易
        give_total = sum([self.trade_offer["give_rock"], self.trade_offer["give_paper"], self.trade_offer["give_scissors"]]) + self.trade_offer["give_star"]
        want_total = sum([self.trade_offer["want_rock"], self.trade_offer["want_paper"], self.trade_offer["want_scissors"]]) + self.trade_offer["want_star"]
        
        if give_total == 0 and want_total == 0:
            self.trade_message = "無法進行空的交易！"
            self.trade_msg_color = (220, 80, 80)
            return
            
        # 2. 估值核心邏輯
        # 卡牌基本點值為 1，星星基本點值為 3.5 (因為星星直接與生存挂鉤，更為昂貴)
        card_val = 1.0
        star_val = 3.5
        
        # 玩家拿出的價值
        val_player_gives = (
            sum([self.trade_offer["give_rock"], self.trade_offer["give_paper"], self.trade_offer["give_scissors"]]) * card_val
            + self.trade_offer["give_star"] * star_val
        )
        # 玩家索取的價值
        val_player_wants = (
            sum([self.trade_offer["want_rock"], self.trade_offer["want_paper"], self.trade_offer["want_scissors"]]) * card_val
            + self.trade_offer["want_star"] * star_val
        )
        
        # 3. 計算方差與卡牌平衡改善程度 (NPC 不希望手牌失衡)
        # 取出 NPC 當前手牌分佈
        c = self.active_npc["cards"]
        npc_rock_count = c["rock"]
        npc_paper_count = c["paper"]
        npc_scissors_count = c["scissors"]
        
        # 原始標準差 (用來衡量手牌平衡度，標準差大代表失衡，如 [5,0,0])
        orig_mean = (npc_rock_count + npc_paper_count + npc_scissors_count) / 3.0
        orig_var = ((npc_rock_count - orig_mean)**2 + (npc_paper_count - orig_mean)**2 + (npc_scissors_count - orig_mean)**2) / 3.0
        
        # 交易後手牌分佈
        new_rock = npc_rock_count + self.trade_offer["give_rock"] - self.trade_offer["want_rock"]
        new_paper = npc_paper_count + self.trade_offer["give_paper"] - self.trade_offer["want_paper"]
        new_scis = npc_scissors_count + self.trade_offer["give_scissors"] - self.trade_offer["want_scissors"]
        
        new_mean = (new_rock + new_paper + new_scis) / 3.0
        new_var = ((new_rock - new_mean)**2 + (new_paper - new_mean)**2 + (new_scis - new_mean)**2) / 3.0
        
        # 平衡改善係數：若交易後方差變小，說明卡牌分佈變平衡了，NPC 會更傾向接受
        balance_improvement = orig_var - new_var  # 正數代表平衡得到改善
        
        # 4. NPC 迫切度修飾
        # 如果 NPC 星星 < 3 (生死危機)，星星的價值對他而言上升到極致，極難交出星星。
        # 如果 NPC 累計卡牌數太多但時間迫近，他渴望送出卡牌。
        urgency_multiplier = 1.0
        if self.active_npc["stars"] <= 2 and self.trade_offer["want_star"] > 0:
            # 玩家想要拿走瀕死 NPC 的星星：需要極高的對應價值才肯換
            urgency_multiplier = 1.8
            
        # 計算 NPC 的接受度分數
        # NPC 獲得價值 = val_player_gives + 平衡改善點數
        # NPC 失去價值 = val_player_wants * 迫切度修飾
        npc_gain = val_player_gives + (balance_improvement * 0.4)
        npc_loss = val_player_wants * urgency_multiplier
        
        # 基於個性做微調
        name = self.active_npc["name"]
        if name == "安藤":
            # 貪婪的人：要求 NPC_GAIN 必須比 NPC_LOSS 多至少 1.5 價值
            threshold = 1.5
        elif name == "古畑":
            # 平等的人：只要基本上差不多 (誤差 0.2 內) 就願意
            threshold = -0.2
        elif name == "石田":
            # 焦慮者：如果玩家給星，他會大方接受大幅度的卡牌交易
            if self.trade_offer["give_star"] > 0:
                threshold = -0.8
            else:
                threshold = 0.5
        else:
            threshold = 0.1  # 正常门槛
            
        # 5. 判定結果
        if npc_gain - npc_loss >= threshold:
            # 執行扣除與轉移
            # 扣除玩家
            self.player_cards["rock"] += self.trade_offer["want_rock"] - self.trade_offer["give_rock"]
            self.player_cards["paper"] += self.trade_offer["want_paper"] - self.trade_offer["give_paper"]
            self.player_cards["scissors"] += self.trade_offer["want_scissors"] - self.trade_offer["give_scissors"]
            self.player_stars += self.trade_offer["want_star"] - self.trade_offer["give_star"]
            
            # 更新 NPC
            self.active_npc["cards"]["rock"] += self.trade_offer["give_rock"] - self.trade_offer["want_rock"]
            self.active_npc["cards"]["paper"] += self.trade_offer["give_paper"] - self.trade_offer["want_paper"]
            self.active_npc["cards"]["scissors"] += self.trade_offer["give_scissors"] - self.trade_offer["want_scissors"]
            self.active_npc["stars"] += self.trade_offer["give_star"] - self.trade_offer["want_star"]
            
            self.add_log(f"[交易] 玩家與 {self.active_npc['name']} 完成交易！")
            self.state = RPG_WALK
        else:
            # 拒絕交易
            if name == "安藤":
                self.trade_message = "安藤說：『這點甜頭想騙我？除非你再多給我點星星！』"
            elif name == "石田":
                self.trade_message = "石田搖搖頭：『不...我現在不能再失去星星了，真的。』"
            else:
                self.trade_message = f"{name}拒絕了交易，對方認為此提案對其不利。"
            self.trade_msg_color = (240, 80, 80)

    def _resolve_battle_clash(self):
        """執行出牌對戰勝負判定"""
        self.battle_phase = "reveal"
        
        # NPC 出牌決策 AI
        # 基本決策：從手牌中擁有的卡隨機選一張，但受個性傾向影響
        c = self.active_npc["cards"]
        available_types = [t for t in ["rock", "paper", "scissors"] if c[t] > 0]
        
        if not available_types:
            # NPC 沒牌了，判定玩家直落獲勝 (防呆，實務上沒牌會離場)
            self.npc_selected_card = "rock" 
        else:
            # 個性修正
            name = self.active_npc["name"]
            if name == "船井" and "rock" in available_types and random.random() < 0.6:
                # 船井喜歡出石頭
                self.npc_selected_card = "rock"
            elif name == "北見":
                # 戰略家：高概率出克制玩家上一張卡或偏好的牌，此處隨機出 NPC 優勢牌
                self.npc_selected_card = random.choice(available_types)
            else:
                self.npc_selected_card = random.choice(available_types)
                
        # 扣除雙方手牌
        self.player_cards[self.player_selected_card] -= 1
        self.active_npc["cards"][self.npc_selected_card] -= 1
        
        # 判定勝負
        p = self.player_selected_card
        n = self.npc_selected_card
        
        if p == n:
            result = "TIE"
            self.battle_result_msg = "雙方平手！卡牌消耗但星數不變。"
            self.battle_result_color = (130, 160, 240)
            log_msg = f"[對戰] 玩家與 {self.active_npc['name']} 出現平局 ({self._trans_card(p)})！"
        elif (p == "rock" and n == "scissors") or (p == "paper" and n == "rock") or (p == "scissors" and n == "paper"):
            result = "PLAYER_WIN"
            self.battle_result_msg = f"您獲勝了！奪得 1 顆星星！"
            self.battle_result_color = (255, 215, 0)
            self.player_stars += 1
            self.active_npc["stars"] -= 1
            log_msg = f"[對戰] 玩家擊敗 {self.active_npc['name']}，贏取 1 顆星星！"
        else:
            result = "NPC_WIN"
            self.battle_result_msg = f"您輸了... 失去 1 顆星星。"
            self.battle_result_color = (240, 50, 50)
            self.player_stars -= 1
            self.active_npc["stars"] += 1
            log_msg = f"[對戰] {self.active_npc['name']} 擊敗玩家，贏取 1 顆星星！"
            
        self.add_log(log_msg)
        self.battle_phase = "result"

    def _trans_card(self, ctype):
        if ctype == "rock": return "石頭 (Rock)"
        if ctype == "paper": return "布 (Paper)"
        return "剪刀 (Scissors)"

    def _check_game_over_conditions(self):
        """檢查玩家是否達成了終局條件"""
        total_player_cards = sum(self.player_cards.values())
        
        # 1. 失去所有星星 -> 失敗 (前往地下暗室)
        if self.player_stars <= 0:
            self.state = SUMMARY
            return
            
        # 2. 消耗所有卡牌 -> 進行檢算
        if total_player_cards == 0:
            self.state = SUMMARY

    # ==========================================
    # 更新循環 (Update Loops)
    # ==========================================
    def update(self, dt, mouse_pos):
        if self.state == RPG_WALK:
            self._update_rpg_exploration(dt, mouse_pos)
        else:
            self.keys_pressed.clear()

    def _update_rpg_exploration(self, dt, mouse_pos):
        # 1. 玩家鍵盤控制移動 (支援 WASD & 方向鍵)
        vx, vy = 0.0, 0.0
        if pygame.K_w in self.keys_pressed or pygame.K_UP in self.keys_pressed:
            vy = -self.player_speed
        if pygame.K_s in self.keys_pressed or pygame.K_DOWN in self.keys_pressed:
            vy = self.player_speed
        if pygame.K_a in self.keys_pressed or pygame.K_LEFT in self.keys_pressed:
            vx = -self.player_speed
        if pygame.K_d in self.keys_pressed or pygame.K_RIGHT in self.keys_pressed:
            vx = self.player_speed
            
        # 對角線速度修正
        if vx != 0.0 and vy != 0.0:
            vx *= 0.7071
            vy *= 0.7071
            
        # 執行帶有碰撞滑動機制的 X/Y 移動
        if vx != 0.0:
            new_x = self.player_x + vx * (dt / 1000.0)
            if not self._check_collision_any(new_x, self.player_y, CHAR_RADIUS):
                self.player_x = new_x
        if vy != 0.0:
            new_y = self.player_y + vy * (dt / 1000.0)
            if not self._check_collision_any(self.player_x, new_y, CHAR_RADIUS):
                self.player_y = new_y
                
        # 2. 限制玩家不能超出地圖邊緣
        self.player_x = max(CHAR_RADIUS, min(self.player_x, self.world_width - CHAR_RADIUS))
        self.player_y = max(CHAR_RADIUS, min(self.player_y, self.world_height - CHAR_RADIUS))

        # 聯機模式下，若玩家位置移動，則同步給對手
        if not self.is_offline and self.net_manager:
            if not hasattr(self, "last_sent_x") or not hasattr(self, "last_sent_y") or abs(self.player_x - self.last_sent_x) > 1.0 or abs(self.player_y - self.last_sent_y) > 1.0:
                self.net_manager.send_data({
                    "action": "sync_pos",
                    "x": self.player_x,
                    "y": self.player_y
                })
                self.last_sent_x = self.player_x
                self.last_sent_y = self.player_y
        
        # 3. 相機跟隨玩家，並夾逼在世界範圍內
        self.camera_x = int(self.player_x - 1000 // 2)
        self.camera_y = int(self.player_y - 700 // 2)
        self.camera_x = max(0, min(self.camera_x, self.world_width - 1000))
        self.camera_y = max(0, min(self.camera_y, self.world_height - 700))
        
        # 4. NPC 行為更新與漫遊模擬
        for npc in self.npcs:
            if npc["status"] in ("SAFE", "LOSE"):
                # 如果已經安全通關或出局，就不再漫遊，移至特定安全點
                if npc["status"] == "SAFE":
                    npc["x"], npc["y"] = 150.0, 150.0  # 安全區
                continue
                
            # 更新計時器以隨機轉向
            npc["timer"] -= (dt / 1000.0)
            if npc["timer"] <= 0:
                npc["timer"] = random.uniform(2.0, 5.0)
                npc["vx"] = float(random.choice([-1, 1]) * random.randint(30, 60))
                npc["vy"] = float(random.choice([-1, 1]) * random.randint(30, 60))
                
            # 移動並執行障礙物碰撞反彈
            n_new_x = npc["x"] + npc["vx"] * (dt / 1000.0)
            if not self._check_collision_any(n_new_x, npc["y"], CHAR_RADIUS):
                npc["x"] = n_new_x
            else:
                npc["vx"] = -npc["vx"]
                
            n_new_y = npc["y"] + npc["vy"] * (dt / 1000.0)
            if not self._check_collision_any(npc["x"], n_new_y, CHAR_RADIUS):
                npc["y"] = n_new_y
            else:
                npc["vy"] = -npc["vy"]
                
            # 確保不出地圖界限
            npc["x"] = max(CHAR_RADIUS, min(npc["x"], self.world_width - CHAR_RADIUS))
            npc["y"] = max(CHAR_RADIUS, min(npc["y"], self.world_height - CHAR_RADIUS))
            
            # 定時檢查 NPC 的完賽狀態
            npc_total_cards = sum(npc["cards"].values())
            if npc["stars"] <= 0:
                npc["status"] = "LOSE"
                self.add_log(f"[出局] NPC {npc['name']} 失去了所有星星，被黑衣人拖至地獄！")
            elif npc_total_cards == 0:
                if npc["stars"] >= 3:
                    npc["status"] = "SAFE"
                    self.add_log(f"[通關] NPC {npc['name']} 卡牌已用罄且持有 {npc['stars']} 顆星，順利清債通關！")
                else:
                    npc["status"] = "LOSE"
                    self.add_log(f"[出局] NPC {npc['name']} 卡牌已用罄但星數不足，被黑衣人拖至地下暗室！")

        # 5. 背景 NPC 對戰與交易離線模擬 (每 5-6 秒隨機觸發一次，讓星之船活起來)
        self.log_timer += (dt / 1000.0)
        if self.log_timer >= 5.5:
            self.log_timer = 0.0
            self._simulate_npc_clash_log()

    def _simulate_npc_clash_log(self):
        """在活躍的 NPC 之間隨機模擬一場交易或卡牌對決"""
        active_candidates = [n for n in self.npcs if n["status"] == "WANDERING"]
        if len(active_candidates) < 2:
            return
            
        n1, n2 = random.sample(active_candidates, 2)
        action = random.choice(["battle", "trade"])
        
        if action == "battle":
            # 隨機挑選手牌
            types1 = [t for t in ["rock", "paper", "scissors"] if n1["cards"][t] > 0]
            types2 = [t for t in ["rock", "paper", "scissors"] if n2["cards"][t] > 0]
            
            if types1 and types2:
                c1 = random.choice(types1)
                c2 = random.choice(types2)
                
                n1["cards"][c1] -= 1
                n2["cards"][c2] -= 1
                
                # 判定
                if c1 == c2:
                    self.add_log(f"[對戰模擬] {n1['name']} 與 {n2['name']} 進行對決，雙方出 {self._trans_card(c1)} 平手。")
                elif (c1=="rock" and c2=="scissors") or (c1=="paper" and c2=="rock") or (c1=="scissors" and c2=="paper"):
                    n1["stars"] += 1
                    n2["stars"] -= 1
                    self.add_log(f"[對戰模擬] {n1['name']} 出 {self._trans_card(c1)} 擊敗 {n2['name']} 出 {self._trans_card(c2)}，奪取 1 顆星！")
                else:
                    n1["stars"] -= 1
                    n2["stars"] += 1
                    self.add_log(f"[對戰模擬] {n2['name']} 出 {self._trans_card(c2)} 擊敗 {n1['name']} 出 {self._trans_card(c1)}，奪取 1 顆星！")
        else:
            # 模擬交換手牌平衡
            t1_excess = [t for t in ["rock", "paper", "scissors"] if n1["cards"][t] >= 2]
            t2_lack = [t for t in ["rock", "paper", "scissors"] if n2["cards"][t] == 0]
            
            if t1_excess and t2_lack:
                give_t = random.choice(t1_excess)
                take_t = random.choice(t2_lack)
                
                if n2["cards"][take_t] > 0:  # n2 拿出來換
                    n1["cards"][give_t] -= 1
                    n1["cards"][take_t] += 1
                    n2["cards"][take_t] -= 1
                    n2["cards"][give_t] += 1
                    self.add_log(f"[交易模擬] {n1['name']} 以 {self._trans_card(give_t)} 與 {n2['name']} 交換了 {self._trans_card(take_t)}。")

    # ==========================================
    # 渲染方法 (Drawing / Rendering)
    # ==========================================
    def draw(self, surface, mouse_pos):
        self.btn_rects = {}  # 每次繪製清空按鈕熱區
        
        if self.state == SETUP:
            self._draw_setup(surface, mouse_pos)
        elif self.state == RPG_WALK:
            self._draw_rpg_walk(surface, mouse_pos)
            if self.state == RPG_WALK and self.pending_request:
                self._draw_request_popup(surface, mouse_pos)
        elif self.state == DIALOGUE:
            self._draw_dialogue(surface, mouse_pos)
        elif self.state == TRADE:
            self._draw_trade(surface, mouse_pos)
        elif self.state == BATTLE:
            self._draw_battle(surface, mouse_pos)
        elif self.state == SUMMARY:
            self._draw_summary(surface, mouse_pos)

    def _draw_setup(self, surface, mouse_pos):
        """渲染自選人數設定頁面"""
        draw_gradient_background(surface, (18, 16, 26), (28, 25, 42))
        
        # 標題
        title_font = get_font(36, bold=True)
        title_s = title_font.render("希望之船：限定剪刀石頭布", True, (240, 200, 110))
        surface.blit(title_s, title_s.get_rect(center=(500, 120)))
        
        desc_font = get_font(15)
        desc_s = desc_font.render("此遊戲為《賭博默示錄》核心規則，自選場上人數進入 2D RPG 社交大廳，進行對決與交易。", True, (150, 150, 165))
        surface.blit(desc_s, desc_s.get_rect(center=(500, 180)))
        
        # 人數選單看板
        board = pygame.Rect(200, 240, 600, 280)
        pygame.draw.rect(surface, (25, 22, 35), board, border_radius=12)
        pygame.draw.rect(surface, (45, 40, 60), board, width=1, border_radius=12)
        
        lbl_font = get_font(18, bold=True)
        lbl_s = lbl_font.render("◆ 設定遊玩人數 (自選總人數) ◆", True, (200, 200, 210))
        surface.blit(lbl_s, lbl_s.get_rect(center=(500, 280)))
        
        # 四個選擇按鈕
        btn_y = 350
        counts = [4, 8, 12, 16]
        for idx, count in enumerate(counts):
            btn_rect = pygame.Rect(250 + idx * 130, btn_y, 100, 45)
            is_hover = btn_rect.collidepoint(mouse_pos)
            is_active = (self.player_count == count)
            
            bg = (200, 160, 30) if is_active else ((40, 35, 55) if is_hover else (30, 25, 40))
            fg = (15, 15, 20) if is_active else (210, 210, 220)
            
            draw_button(surface, btn_rect, f"{count} 人", bg, bg, fg, False, get_font(16, bold=True))
            self.btn_rects[f"btn_count_{count}"] = btn_rect
            
        # 规则摘要
        rule_s1 = get_font(13).render("・初始手牌：剪刀、石頭、布 各 4 張 (共 12 張)，消耗完且星星數 >= 3 即為成功過關。", True, (160, 160, 170))
        rule_s2 = get_font(13).render("・每位角色初始擁有 3 顆 ⭐，對戰勝利奪星、平手不變，失去所有星星即被黑衣人逮捕。", True, (160, 160, 170))
        surface.blit(rule_s1, (240, 430))
        surface.blit(rule_s2, (240, 460))
        
        # 開始對戰與返回大廳按鈕
        start_rect = pygame.Rect(320, 560, 160, 45)
        start_hover = start_rect.collidepoint(mouse_pos)
        draw_button(surface, start_rect, "進入遊戲", (220, 180, 40), (190, 150, 30), (15, 15, 20), start_hover, get_font(16, bold=True))
        self.btn_rects["btn_start"] = start_rect
        
        back_rect = pygame.Rect(520, 560, 160, 45)
        back_hover = back_rect.collidepoint(mouse_pos)
        draw_button(surface, back_rect, "返回大廳", (45, 45, 50), (65, 65, 75), (220, 220, 220), back_hover, get_font(16))
        self.btn_rects["btn_back_lobby"] = back_rect

    def _draw_rpg_walk(self, surface, mouse_pos):
        """渲染 2D RPG 探索主畫面"""
        # 1. 繪製精細鋼鐵地板結構 (以相機座標偏移)
        floor_color = (20, 22, 28)
        grid_color = (28, 30, 38)
        surface.fill(floor_color)
        
        # 繪製地圖網格
        grid_size = 80
        start_grid_x = -(self.camera_x % grid_size)
        start_grid_y = -(self.camera_y % grid_size)
        for gx in range(start_grid_x, 1000, grid_size):
            pygame.draw.line(surface, grid_color, (gx, 0), (gx, 700))
        for gy in range(start_grid_y, 700, grid_size):
            pygame.draw.line(surface, grid_color, (0, gy), (1000, gy))
            
        # 2. 繪製所有障礙物
        for obs in self.obstacles:
            obs.draw(surface, self.camera_x, self.camera_y)
            
        # 3. 繪製 NPC 角色
        for npc in self.npcs:
            if npc["status"] == "LOSE":
                # 已出局的 NPC 不繪製在現場
                continue
                
            scr_x = int(npc["x"] - self.camera_x)
            scr_y = int(npc["y"] - self.camera_y)
            
            # 若滑鼠懸停於 NPC 上，加亮並顯示互動環
            dist_mouse = math.hypot(mouse_pos[0] - scr_x, mouse_pos[1] - scr_y)
            npc["is_hovered"] = (dist_mouse < CHAR_RADIUS + 5)
            
            # 繪製玩家與 NPC 的距離標線 (靠近時亮起)
            dist_player = math.hypot(npc["x"] - self.player_x, npc["y"] - self.player_y)
            is_near = (dist_player < 65)
            
            if npc["status"] == "SAFE":
                color_to_draw = (100, 100, 110) # 灰色已完賽
            else:
                color_to_draw = npc["color"]
                
            if is_near and npc["status"] == "WANDERING":
                # 繪製綠色虛線範圍圈
                pygame.draw.circle(surface, (100, 255, 100), (scr_x, scr_y), CHAR_RADIUS + 8, width=1)
                
            if npc["is_hovered"]:
                pygame.draw.circle(surface, (255, 255, 255), (scr_x, scr_y), CHAR_RADIUS + 4, width=2)
                
            # 本體
            pygame.draw.circle(surface, color_to_draw, (scr_x, scr_y), CHAR_RADIUS)
            pygame.draw.circle(surface, (10, 10, 15), (scr_x, scr_y), CHAR_RADIUS, width=1)
            
            # 名字標記
            lbl_n = get_font(11, bold=True).render(npc["name"], True, (240, 240, 240))
            surface.blit(lbl_n, lbl_n.get_rect(center=(scr_x, scr_y - CHAR_RADIUS - 12)))
            
            # 狀態指示 (星星數量與狀態)
            if npc["status"] == "SAFE":
                status_txt = "SAFE"
                color_st = (100, 255, 100)
            else:
                status_txt = f"⭐ {npc['stars']}"
                color_st = (245, 220, 90)
            lbl_st = get_font(10).render(status_txt, True, color_st)
            surface.blit(lbl_st, lbl_st.get_rect(center=(scr_x, scr_y + CHAR_RADIUS + 12)))

        # 4. 繪製對手玩家 (如果不是離線模式)
        if not self.is_offline:
            opp_scr_x = int(self.opponent_x - self.camera_x)
            opp_scr_y = int(self.opponent_y - self.camera_y)
            
            # 判斷滑鼠是否懸停於對手
            dist_mouse = math.hypot(mouse_pos[0] - opp_scr_x, mouse_pos[1] - opp_scr_y)
            opp_hovered = (dist_mouse < CHAR_RADIUS + 5)
            
            # 靠近時亮起互動提示圈
            dist_player = math.hypot(self.opponent_x - self.player_x, self.opponent_y - self.player_y)
            is_near_opp = (dist_player < 65)
            
            if is_near_opp:
                pygame.draw.circle(surface, (100, 255, 100), (opp_scr_x, opp_scr_y), CHAR_RADIUS + 8, width=1)
                
            if opp_hovered:
                pygame.draw.circle(surface, (255, 255, 255), (opp_scr_x, opp_scr_y), CHAR_RADIUS + 4, width=2)
                
            # 本體
            pygame.draw.circle(surface, (100, 180, 255), (opp_scr_x, opp_scr_y), CHAR_RADIUS)
            pygame.draw.circle(surface, (10, 10, 15), (opp_scr_x, opp_scr_y), CHAR_RADIUS, width=1)
            
            # 名字與星星
            lbl_opp = get_font(12, bold=True).render(self.opponent_name, True, (100, 180, 255))
            surface.blit(lbl_opp, lbl_opp.get_rect(center=(opp_scr_x, opp_scr_y - CHAR_RADIUS - 12)))
            
            lbl_opp_st = get_font(10).render(f"⭐ {self.opponent_stars}", True, (245, 220, 90))
            surface.blit(lbl_opp_st, lbl_opp_st.get_rect(center=(opp_scr_x, opp_scr_y + CHAR_RADIUS + 12)))

        # 5. 繪製玩家主角
        p_scr_x = int(self.player_x - self.camera_x)
        p_scr_y = int(self.player_y - self.camera_y)
        pygame.draw.circle(surface, (255, 215, 0), (p_scr_x, p_scr_y), CHAR_RADIUS + 2, width=2)
        pygame.draw.circle(surface, (22, 28, 45), (p_scr_x, p_scr_y), CHAR_RADIUS)
        # 繪製主角名字
        lbl_p = get_font(12, bold=True).render("YOU", True, (255, 215, 0))
        surface.blit(lbl_p, lbl_p.get_rect(center=(p_scr_x, p_scr_y)))
        
        # 6. 繪製快捷互動按鈕提示 (若靠近某 NPC 或對手玩家)
        if not self.is_offline and self._get_interactable_opponent():
            tip_rect = pygame.Rect(350, 440, 300, 32)
            pygame.draw.rect(surface, (15, 15, 20), tip_rect, border_radius=6)
            pygame.draw.rect(surface, (100, 255, 100), tip_rect, width=1, border_radius=6)
            
            if self.sent_request:
                t_s = get_font(13).render(f"已發送 {self.sent_request} 邀請，等待對手回應...", True, (220, 255, 220))
            else:
                t_s = get_font(13).render(f"靠近 {self.opponent_name}！按 [B]對決 | [T]交易", True, (220, 255, 220))
            surface.blit(t_s, t_s.get_rect(center=tip_rect.center))
        else:
            closest_npc = self._get_closest_active_npc()
            if closest_npc:
                tip_rect = pygame.Rect(350, 440, 300, 32)
                pygame.draw.rect(surface, (15, 15, 20), tip_rect, border_radius=6)
                pygame.draw.rect(surface, (100, 255, 100), tip_rect, width=1, border_radius=6)
                
                t_s = get_font(13).render(f"靠近 {closest_npc['name']}！按 [ENTER/E]對話 | [B]對戰 | [T]交易", True, (220, 255, 220))
                surface.blit(t_s, t_s.get_rect(center=tip_rect.center))
            
        # 6. 右下角即時對決動態日誌面板 (可被切換隱藏以避免阻擋玩家視野)
        if self.show_logs:
            log_panel = pygame.Rect(650, 480, 330, 160)
            pygame.draw.rect(surface, (15, 15, 22), log_panel, border_radius=8)
            pygame.draw.rect(surface, (42, 45, 55), log_panel, width=1, border_radius=8)
            
            log_title = get_font(12, bold=True).render("希望之船 - 即時資訊傳播 (Espoir Logs)", True, (140, 140, 150))
            surface.blit(log_title, (665, 490))
            
            # 顯示最後 5 筆日誌
            show_logs = self.logs[-5:]
            for idx, log in enumerate(show_logs):
                log_s = get_font(11).render(log, True, (190, 195, 210) if idx == len(show_logs)-1 else (120, 125, 135))
                surface.blit(log_s, (665, 515 + idx * 22))
            
        # 7. 左上角玩家手牌狀態面板 (調整高度為 280 以容納全船資源統計)
        status_panel = pygame.Rect(20, 70, 220, 280)
        pygame.draw.rect(surface, (20, 20, 28), status_panel, border_radius=8)
        pygame.draw.rect(surface, (255, 215, 0), status_panel, width=1, border_radius=8)
        
        # 繪製星星與卡牌
        lbl_p_st = get_font(14, bold=True).render("我的資產狀態 (Assets)", True, (255, 215, 0))
        surface.blit(lbl_p_st, (35, 82))
        
        # 星星
        star_y = 115
        draw_star(surface, 50, star_y, 12, (255, 215, 0))
        star_txt = get_font(15, bold=True).render(f"擁有星星數 :  {self.player_stars} 顆", True, (255, 215, 0))
        surface.blit(star_txt, (75, star_y - 8))
        
        # 手牌數
        tot_cards = sum(self.player_cards.values())
        card_txt = get_font(13).render(f"剩餘手牌數 :  x {tot_cards}", True, (220, 220, 230))
        surface.blit(card_txt, (35, 140))
        
        detail_txt = get_font(12).render(f"石頭: {self.player_cards['rock']} 張 | 布: {self.player_cards['paper']} 張 | 剪刀: {self.player_cards['scissors']} 張", True, (160, 160, 170))
        surface.blit(detail_txt, (35, 168))

        # 全船流通資源餘量統計 (隨雙方出牌對決動態遞減)
        pygame.draw.line(surface, (45, 45, 55), (30, 195), (230, 195), width=1)
        lbl_cir = get_font(12, bold=True).render("全船流通餘量 (Circulating)", True, (100, 180, 255))
        surface.blit(lbl_cir, (35, 205))
        
        cir_stars = self.player_stars
        cir_rock = self.player_cards["rock"]
        cir_paper = self.player_cards["paper"]
        cir_scissors = self.player_cards["scissors"]
        for npc in self.npcs:
            if npc["status"] == "WANDERING":
                cir_stars += npc["stars"]
                cir_rock += npc["cards"]["rock"]
                cir_paper += npc["cards"]["paper"]
                cir_scissors += npc["cards"]["scissors"]
        if not self.is_offline:
            cir_stars += self.opponent_stars
            cir_rock += self.opponent_cards["rock"]
            cir_paper += self.opponent_cards["paper"]
            cir_scissors += self.opponent_cards["scissors"]
                
        lbl_cir_stars = get_font(11).render(f"流通星星總數: {cir_stars} 顆", True, (245, 220, 90))
        lbl_cir_cards = get_font(11).render(f"石頭: {cir_rock} 張 | 布: {cir_paper} 張 | 剪刀: {cir_scissors} 張", True, (200, 200, 210))
        surface.blit(lbl_cir_stars, (35, 230))
        surface.blit(lbl_cir_cards, (35, 252))
        
        # 8. 頂部導航欄 (同 Emperor & Slave)
        pygame.draw.rect(surface, (15, 15, 20), pygame.Rect(0, 0, 1000, 50))
        pygame.draw.line(surface, (35, 35, 40), (0, 50), (1000, 50), width=1)
        
        back_btn_rect = pygame.Rect(20, 12, 110, 26)
        is_back_hover = back_btn_rect.collidepoint(mouse_pos)
        draw_button(surface, back_btn_rect, "返回遊戲大廳", (40, 40, 45), (60, 60, 70), (220, 220, 220), is_back_hover, get_font(13))
        self.btn_rects["btn_back_lobby"] = back_btn_rect
        
        title_text = get_font(18, bold=True).render("希望之船 - 限定剪刀石頭布 2D 大廳", True, (240, 195, 80))
        surface.blit(title_text, (150, 13))
        
        # 切換日誌顯示按鈕 (L)
        log_btn_rect = pygame.Rect(700, 12, 120, 26)
        is_log_hover = log_btn_rect.collidepoint(mouse_pos)
        log_text = "隱藏日誌 [L]" if self.show_logs else "顯示日誌 [L]"
        draw_button(surface, log_btn_rect, log_text, (40, 40, 45), (60, 60, 70), (220, 220, 220), is_log_hover, get_font(13))
        self.btn_rects["btn_toggle_logs"] = log_btn_rect
        
        # 總人數與在場殘留人數
        rem_count = sum([1 for n in self.npcs if n["status"] == "WANDERING"]) + 1
        cnt_text = get_font(14).render(f"在場人數: {rem_count} / {self.player_count} 人", True, (170, 170, 180))
        surface.blit(cnt_text, (840, 17))

    def _draw_dialogue(self, surface, mouse_pos):
        """渲染對話互動面板"""
        self._draw_rpg_walk(surface, mouse_pos)
        
        # 對話框罩層
        draw_rect_alpha(surface, (10, 10, 15, 180), pygame.Rect(0, 0, 1000, 700))
        
        # 對話主視窗
        dlg_rect = pygame.Rect(100, 360, 800, 240)
        pygame.draw.rect(surface, (20, 22, 30), dlg_rect, border_radius=12)
        pygame.draw.rect(surface, (255, 215, 0), dlg_rect, width=1, border_radius=12)
        
        # NPC 頭像 (彩色大圈)
        pygame.draw.circle(surface, self.active_npc["color"], (180, 440), 45)
        # 繪製頭像內文字
        lbl_head = get_font(26, bold=True).render(self.active_npc["name"][0], True, (255, 255, 255))
        surface.blit(lbl_head, lbl_head.get_rect(center=(180, 440)))
        
        # 名字
        lbl_n = get_font(20, bold=True).render(self.active_npc["name"], True, (255, 215, 0))
        surface.blit(lbl_n, (250, 390))
        
        # 台詞文字
        lines = [
            f"『{self.active_npc['desc']}』",
            f"「我身上還有 {sum(self.active_npc['cards'].values())} 張牌與 {self.active_npc['stars']} 顆星星。你打算怎麼做？」"
        ]
        
        for idx, line in enumerate(lines):
            line_s = get_font(14).render(line, True, (160, 160, 170) if idx == 0 else (240, 240, 245))
            surface.blit(line_s, (250, 435 + idx * 26))
            
        # 操作按鈕
        btn_battle = pygame.Rect(250, 520, 130, 42)
        bh = btn_battle.collidepoint(mouse_pos)
        draw_button(surface, btn_battle, "進行對決", (200, 60, 60), (170, 45, 45), (255, 255, 255), bh, get_font(14, bold=True))
        self.btn_rects["btn_dlg_battle"] = btn_battle
        
        btn_trade = pygame.Rect(400, 520, 130, 42)
        th = btn_trade.collidepoint(mouse_pos)
        draw_button(surface, btn_trade, "進行交易", (45, 120, 200), (35, 100, 170), (255, 255, 255), th, get_font(14, bold=True))
        self.btn_rects["btn_dlg_trade"] = btn_trade
        
        btn_close = pygame.Rect(750, 380, 32, 32)
        ch = btn_close.collidepoint(mouse_pos)
        draw_button(surface, btn_close, "X", (50, 50, 55), (80, 40, 40), (220, 220, 220), ch, get_font(14, bold=True))
        self.btn_rects["btn_dlg_close"] = btn_close

    def _draw_trade(self, surface, mouse_pos):
        """渲染限定剪刀石頭布「星之船交易面板」"""
        draw_gradient_background(surface, (15, 16, 22), (25, 28, 38))
        
        if not self.is_offline:
            opp_name = self.opponent_name
            opp_stars = self.opponent_stars
            opp_cards = self.opponent_cards
        else:
            opp_name = self.active_npc["name"]
            opp_stars = self.active_npc["stars"]
            opp_cards = self.active_npc["cards"]

        # 標題
        title_s = get_font(26, bold=True).render(f"與 {opp_name} 的交涉交易", True, (100, 200, 255))
        surface.blit(title_s, title_s.get_rect(center=(500, 60)))
        
        # 說明
        info_s = get_font(13).render(self.trade_message, True, self.trade_msg_color)
        surface.blit(info_s, info_s.get_rect(center=(500, 100)))
        
        card_types = ["rock", "paper", "scissors", "star"]
        y_start = 170
        y_spacing = 65
        
        # 左面板 (我方給出)
        give_panel = pygame.Rect(80, 130, 400, 340)
        pygame.draw.rect(surface, (22, 22, 28), give_panel, border_radius=10)
        pygame.draw.rect(surface, (80, 140, 220), give_panel, width=1, border_radius=10)
        lbl_give = get_font(16, bold=True).render("我方提供給對方的資源 (Give)", True, (100, 160, 240))
        surface.blit(lbl_give, (110, 145))
        
        for idx, t in enumerate(card_types):
            cy = y_start + 30 + idx * y_spacing
            
            # 圖示
            if t == "star":
                draw_star(surface, 130, cy + 12, 10, (255, 215, 0))
                txt_lbl = "星星 (Star)"
                curr_own = self.player_stars
            else:
                txt_lbl = self._trans_card(t)
                curr_own = self.player_cards[t]
                
            lbl_res = get_font(14).render(f"{txt_lbl} (擁:{curr_own})", True, (220, 220, 225))
            surface.blit(lbl_res, (160, cy))
            
            # 增減按鈕與數值
            field = f"give_{t}"
            val = self.trade_offer[field]
            
            # Minus
            btn_m = pygame.Rect(320, cy - 4, 26, 26)
            mh = btn_m.collidepoint(mouse_pos)
            draw_button(surface, btn_m, "-", (40, 40, 45), (60, 60, 70), (220, 220, 220), mh, get_font(14, bold=True))
            self.btn_rects[f"btn_trade_minus_{field}"] = btn_m
            
            # Val
            val_s = get_font(15, bold=True).render(str(val), True, (255, 215, 0) if val > 0 else (120, 120, 130))
            surface.blit(val_s, val_s.get_rect(center=(365, cy + 8)))
            
            # Plus
            btn_p = pygame.Rect(390, cy - 4, 26, 26)
            ph = btn_p.collidepoint(mouse_pos)
            draw_button(surface, btn_p, "+", (40, 40, 45), (60, 60, 70), (220, 220, 220), ph, get_font(14, bold=True))
            self.btn_rects[f"btn_trade_plus_{field}"] = btn_p

        # 右面板 (要求對方給出)
        want_panel = pygame.Rect(520, 130, 400, 340)
        pygame.draw.rect(surface, (22, 22, 28), want_panel, border_radius=10)
        pygame.draw.rect(surface, (220, 140, 80), want_panel, width=1, border_radius=10)
        lbl_want = get_font(16, bold=True).render("向對方要求得到的資源 (Want)", True, (240, 150, 100))
        surface.blit(lbl_want, (550, 145))
        
        for idx, t in enumerate(card_types):
            cy = y_start + 30 + idx * y_spacing
            
            # 圖示
            if t == "star":
                draw_star(surface, 570, cy + 12, 10, (255, 215, 0))
                txt_lbl = "星星 (Star)"
                curr_own = opp_stars
            else:
                txt_lbl = self._trans_card(t)
                curr_own = opp_cards[t]
                
            lbl_res = get_font(14).render(f"{txt_lbl} (持:{curr_own})", True, (220, 220, 225))
            surface.blit(lbl_res, (600, cy))
            
            # 增減按鈕與數值
            field = f"want_{t}"
            val = self.trade_offer[field]
            
            # Minus
            btn_m = pygame.Rect(760, cy - 4, 26, 26)
            mh = btn_m.collidepoint(mouse_pos)
            draw_button(surface, btn_m, "-", (40, 40, 45), (60, 60, 70), (220, 220, 220), mh, get_font(14, bold=True))
            self.btn_rects[f"btn_trade_minus_{field}"] = btn_m
            
            # Val
            val_s = get_font(15, bold=True).render(str(val), True, (255, 215, 0) if val > 0 else (120, 120, 130))
            surface.blit(val_s, val_s.get_rect(center=(805, cy + 8)))
            
            # Plus
            btn_p = pygame.Rect(830, cy - 4, 26, 26)
            ph = btn_p.collidepoint(mouse_pos)
            draw_button(surface, btn_p, "+", (40, 40, 45), (60, 60, 70), (220, 220, 220), ph, get_font(14, bold=True))
            self.btn_rects[f"btn_trade_plus_{field}"] = btn_p

        # 底部確定交易 / 返回按鈕
        confirm_rect = pygame.Rect(320, 520, 160, 45)
        ch = confirm_rect.collidepoint(mouse_pos)
        draw_button(surface, confirm_rect, "確認提出交易", (100, 220, 100), (80, 190, 80), (15, 15, 20), ch, get_font(16, bold=True))
        self.btn_rects["btn_trade_confirm"] = confirm_rect
        
        cancel_rect = pygame.Rect(520, 520, 160, 45)
        cnh = cancel_rect.collidepoint(mouse_pos)
        draw_button(surface, cancel_rect, "取消交易並返回", (55, 55, 60), (75, 75, 85), (220, 220, 220), cnh, get_font(16))
        self.btn_rects["btn_trade_cancel"] = cancel_rect
        
        # 智慧型對話氣泡提示 NPC 目前的動態心聲 / 雙方聯機確認狀態
        bubble_rect = pygame.Rect(180, 590, 640, 55)
        pygame.draw.rect(surface, (20, 20, 28), bubble_rect, border_radius=6)
        pygame.draw.rect(surface, (45, 45, 55), bubble_rect, width=1, border_radius=6)
        
        if not self.is_offline:
            quote = f"雙方確認狀態：您: {'[已確認]' if self.trade_self_ready else '[未確認]'} | 對手: {'[已確認]' if self.trade_opp_ready else '[未確認]'}"
        else:
            name = self.active_npc["name"]
            quote = f"{name} 目前心聲：『我手裡多餘的牌是 {', '.join([self._trans_card(k) for k,v in self.active_npc['cards'].items() if v >= 2]) or '無'}，我需要星數至少高於 3 顆...』"
            
        lbl_q = get_font(12).render(quote, True, (160, 160, 175))
        surface.blit(lbl_q, lbl_q.get_rect(center=bubble_rect.center))

    def _draw_battle(self, surface, mouse_pos):
        """渲染經典卡牌對戰 clash 畫面"""
        draw_gradient_background(surface, (15, 15, 25), (30, 25, 40))
        
        if not self.is_offline:
            opp_name = self.opponent_name
            opp_stars = self.opponent_stars
            opp_tot_cards = sum(self.opponent_cards.values())
        else:
            opp_name = self.active_npc["name"]
            opp_stars = self.active_npc["stars"]
            opp_tot_cards = sum(self.active_npc["cards"].values())

        # 標題
        lbl_title = get_font(26, bold=True).render(f"與 {opp_name} 進行限定對決", True, (255, 215, 0))
        surface.blit(lbl_title, lbl_title.get_rect(center=(500, 60)))
        
        # 雙方資產
        lbl_npc_ast = get_font(14).render(f"對手資產: ⭐ x {opp_stars}  | 剩餘牌數: {opp_tot_cards}張", True, (180, 180, 190))
        surface.blit(lbl_npc_ast, lbl_npc_ast.get_rect(center=(500, 100)))
        
        # 桌面上發牌卡槽
        npc_slot = pygame.Rect(440, 150, self.card_w, self.card_h)
        pygame.draw.rect(surface, (30, 25, 40), npc_slot, width=1, border_radius=8)
        lbl_n_slot = get_font(13).render("對手出牌", True, (80, 80, 100))
        surface.blit(lbl_n_slot, lbl_n_slot.get_rect(center=npc_slot.center))
        
        player_slot = pygame.Rect(440, 380, self.card_w, self.card_h)
        pygame.draw.rect(surface, (30, 25, 40), player_slot, width=1, border_radius=8)
        lbl_p_slot = get_font(13).render("我的出牌", True, (80, 80, 100))
        surface.blit(lbl_p_slot, lbl_p_slot.get_rect(center=player_slot.center))
        
        # 繪製卡牌內容
        if self.battle_phase in ("select", "waiting"):
            # 繪製背面圖示在 NPC 卡槽
            pygame.draw.rect(surface, (40, 35, 55), npc_slot, border_radius=8)
            pygame.draw.rect(surface, (255, 215, 0), npc_slot, width=2, border_radius=8)
            lbl_back = get_font(16, bold=True).render("ESPOIR", True, (255, 215, 0))
            surface.blit(lbl_back, lbl_back.get_rect(center=npc_slot.center))
            
            # 如果玩家已經選擇了卡片，繪製在玩家出牌槽
            if self.player_selected_card:
                self._draw_single_card(surface, player_slot, self.player_selected_card, face_up=True)
                
            if self.battle_phase == "select":
                lbl_sel = get_font(15, bold=True).render("◆ 請從剩餘手牌中挑選一張打出 ◆", True, (200, 200, 210))
                surface.blit(lbl_sel, lbl_sel.get_rect(center=(500, 580)))
                
                card_types = ["rock", "paper", "scissors"]
                for idx, ctype in enumerate(card_types):
                    btn_card = pygame.Rect(260 + idx * 160, 605, 120, 42)
                    ch = btn_card.collidepoint(mouse_pos)
                    is_selected = (self.player_selected_card == ctype)
                    cnt = self.player_cards[ctype]
                    
                    if cnt == 0:
                        bg = (30, 30, 35)
                        fg = (80, 80, 85)
                    else:
                        bg = (255, 215, 0) if is_selected else ((50, 45, 65) if ch else (35, 30, 45))
                        fg = (15, 15, 20) if is_selected else (220, 220, 230)
                        
                    draw_button(surface, btn_card, f"{self._trans_card(ctype)} ({cnt})", bg, bg, fg, False, get_font(13, bold=True))
                    self.btn_rects[f"btn_card_{ctype}"] = btn_card
                    
                # 確定按鈕
                if self.player_selected_card:
                    btn_ok = pygame.Rect(750, 450, 140, 45)
                    okh = btn_ok.collidepoint(mouse_pos)
                    draw_button(surface, btn_ok, "確定出牌", (100, 220, 100), (80, 190, 80), (15, 15, 20), okh, get_font(15, bold=True))
                    self.btn_rects["btn_battle_confirm"] = btn_ok
            else:
                lbl_wait = get_font(16, bold=True).render("◆ 已出牌，等待對手出牌... ◆", True, (100, 200, 255))
                surface.blit(lbl_wait, lbl_wait.get_rect(center=(500, 580)))
                
        elif self.battle_phase == "result":
            # 雙方皆揭牌
            opp_card = self.opponent_selected_card if not self.is_offline else self.npc_selected_card
            self._draw_single_card(surface, npc_slot, opp_card, face_up=True)
            self._draw_single_card(surface, player_slot, self.player_selected_card, face_up=True)
            
            # 中間顯示勝負結果與特效
            res_box = pygame.Rect(180, 280, 640, 90)
            pygame.draw.rect(surface, (20, 20, 25), res_box, border_radius=8)
            pygame.draw.rect(surface, self.battle_result_color, res_box, width=2, border_radius=8)
            
            lbl_res = get_font(20, bold=True).render(self.battle_result_msg, True, self.battle_result_color)
            surface.blit(lbl_res, lbl_res.get_rect(center=res_box.center))
            
            # 返回對戰大廳按鈕
            btn_finish = pygame.Rect(420, 580, 160, 45)
            fh = btn_finish.collidepoint(mouse_pos)
            draw_button(surface, btn_finish, "返回大廳", (255, 215, 0), (220, 180, 0), (15, 15, 20), fh, get_font(15, bold=True))
            self.btn_rects["btn_battle_finish"] = btn_finish

    def _draw_single_card(self, surface, rect, card_type, face_up=True):
        """繪製單張精美卡牌"""
        pygame.draw.rect(surface, (24, 25, 32), rect, border_radius=8)
        
        if card_type == "rock":
            border_color = (130, 130, 140)
            lbl_txt = "ROCK 石頭"
        elif card_type == "paper":
            border_color = (100, 180, 220)
            lbl_txt = "PAPER 布"
        else:
            border_color = (220, 80, 80)
            lbl_txt = "SCISSORS 剪刀"
            
        pygame.draw.rect(surface, border_color, rect, width=3, border_radius=8)
        
        # 繪製對應向量圖示
        cx, cy = rect.centerx, rect.centery - 15
        if card_type == "rock":
            pygame.draw.circle(surface, (100, 100, 105), (cx, cy), 28)
            pygame.draw.circle(surface, (130, 130, 135), (cx, cy), 28, width=2)
        elif card_type == "paper":
            w, h = 45, 55
            pygame.draw.rect(surface, (230, 230, 235), pygame.Rect(cx - w/2, cy - h/2, w, h), border_radius=2)
            pygame.draw.rect(surface, (120, 170, 200), pygame.Rect(cx - w/2, cy - h/2, w, h), width=2, border_radius=2)
        else:
            pygame.draw.line(surface, (200, 200, 210), (cx - 20, cy + 20), (cx + 20, cy - 20), width=4)
            pygame.draw.line(surface, (200, 200, 210), (cx - 20, cy - 20), (cx + 20, cy + 20), width=4)
            pygame.draw.circle(surface, (220, 60, 60), (cx - 20, cy - 20), 10, width=3)
            pygame.draw.circle(surface, (220, 60, 60), (cx - 20, cy + 20), 10, width=3)
            
        # 底部標題
        lbl_s = get_font(12, bold=True).render(lbl_txt, True, border_color)
        surface.blit(lbl_s, lbl_s.get_rect(center=(rect.centerx, rect.bottom - 22)))

    def _draw_summary(self, surface, mouse_pos):
        """渲染結算與通關面板"""
        draw_gradient_background(surface, (12, 10, 18), (24, 20, 32))
        
        is_win = (self.player_stars >= 3)
        
        # 標題
        title_font = get_font(42, bold=True)
        color = (255, 215, 0) if is_win else (220, 40, 40)
        title_txt = "★ 順 利 通 關 ★" if is_win else "☠ 負 債 敗 北 ☠"
        
        title_s = title_font.render(title_txt, True, color)
        surface.blit(title_s, title_s.get_rect(center=(500, 150)))
        
        # 結算細項看板
        board = pygame.Rect(250, 240, 500, 260)
        pygame.draw.rect(surface, (20, 18, 28), board, border_radius=12)
        pygame.draw.rect(surface, color, board, width=1, border_radius=12)
        
        lbl_st = get_font(16).render(f"最終擁有星星數量: ⭐  x {self.player_stars}", True, (255, 215, 0))
        surface.blit(lbl_st, (300, 280))
        
        res_text = "恭喜你！在希望之船埃斯波瓦爾上順利生存下來，債務一筆勾銷，贏回了人生自由。" if is_win else "遺憾... 星星數不足，你已失去一切，將被送往地下設施進行強制勞動。"
        # 自動折行
        words = res_text
        font_res = get_font(13)
        # 簡單切半繪製
        mid = len(words) // 2
        line1 = words[:mid]
        line2 = words[mid:]
        
        lbl_l1 = font_res.render(line1, True, (160, 160, 175))
        lbl_l2 = font_res.render(line2, True, (160, 160, 175))
        surface.blit(lbl_l1, (300, 340))
        surface.blit(lbl_l2, (300, 365))
        
        # 戰績評估
        if not self.is_offline:
            opp_win = (self.opponent_stars >= 3)
            opp_res_str = "順利通關" if opp_win else "負債敗北"
            eval_str = f"本場聯機對決中，您的對手 {self.opponent_name} 最終狀態為：{opp_res_str} (⭐ x {self.opponent_stars})。"
        else:
            total_npc_lose = sum([1 for n in self.npcs if n["status"] == "LOSE"])
            eval_str = f"本場對局中，共有 {total_npc_lose} 名 NPC 出局並被拖入地下暗室。"
            
        lbl_npc_cnt = get_font(12).render(eval_str, True, (130, 130, 140))
        surface.blit(lbl_npc_cnt, (300, 420))
        
        # 返回遊戲大廳
        btn_back = pygame.Rect(400, 540, 200, 45)
        bh = btn_back.collidepoint(mouse_pos)
        draw_button(surface, btn_back, "返回遊戲大廳", (255, 215, 0), (220, 180, 0), (15, 15, 20), bh, get_font(16, bold=True))
        self.btn_rects["btn_back_lobby"] = btn_back


def draw_star(surface, x, y, size, color=(255, 215, 0)):
    """繪製向量五角星"""
    points = []
    for i in range(10):
        r = size if i % 2 == 0 else size / 2.5
        angle = i * math.pi / 5 - math.pi / 2
        points.append((x + r * math.cos(angle), y + r * math.sin(angle)))
    pygame.draw.polygon(surface, color, points)
