# filepath: C:\Users\ethan\Desktop\Project\src\ecard\ecard_ui.py
"""
E-Card (國王與奴隸) - 遊戲視覺與操作模組
======================================

本模組封裝了 E-Card 的核心視覺效果、發牌動畫、出牌槽定位、結果彈窗，
並與伺服器或離線 AI 裁判邏輯進行串接。
從 main.py 中完全解耦，使程式主大廳保持純淨。
"""

import pygame
import sys
from src.ecard import ecard_logic
from src.common import ui_components
from src.common.ui_components import UICard, get_font, draw_rect_alpha, draw_glow, draw_button, draw_gradient_background

class EcardGameUI:
    def __init__(self, surface, game_manager, net_manager, is_offline):
        self.surface = surface
        self.game_manager = game_manager  # 指向 main.py 中實例化的 EcardGame
        self.net_manager = net_manager
        self.is_offline = is_offline
        
        # 遊戲內卡牌動畫管理列表
        self.uicards_player = []
        self.uicards_cpu = []
        self.uicards_tie_pile = []
        
        self.uicard_played_player = None
        self.uicard_played_cpu = None
        
        self.active_timer = 0
        self.show_result_modal = False
        
        # 註冊網路管理器回呼函數以進行事件驅動
        self.net_manager.on_receive_message = self.on_net_receive
        
        # 根據模式進行初始提示
        if self.is_offline:
            self.game_manager.game_phase = 0  # CHOOSE_ROLE
            self.game_manager.status_message = "離線模式：請選擇您的陣營開始遊戲"
        else:
            # 連線模式
            self.game_manager.game_phase = 0  # CHOOSE_ROLE
            self.game_manager.status_message = "連線成功！請選擇您的陣營開始連線對決"

    def cleanup(self):
        """退出遊戲時清理網路回呼，避免記憶體洩漏與衝突"""
        self.net_manager.on_receive_message = None

    def on_net_receive(self, data):
        """連線模式下，接收來自伺服器的自定義封包"""
        action = data.get("action")
        
        if action == "opponent_played":
            opp_type = data.get("card_type")
            opp_id = data.get("card_id")
            self.handle_opponent_play_network(opp_type, opp_id)
            
        elif action == "game_start":
            role = data.get("role")
            self.start_new_round(role)
            
        elif action == "round_result":
            winner = data.get("winner")
            reason = data.get("reason", "")
            
            self.game_manager.wins_player = data.get("wins_player", self.game_manager.wins_player)
            self.game_manager.wins_cpu = data.get("wins_cpu", self.game_manager.wins_cpu)
            self.game_manager.round_winner = winner
            self.game_manager.status_message = reason

    def start_new_round(self, role):
        """初始化新一輪遊戲並生成卡牌視覺物件"""
        self.game_manager.init_round(role)
        
        self.uicards_player = [UICard(c) for c in self.game_manager.player_hand]
        self.uicards_cpu = [UICard(c) for c in self.game_manager.cpu_hand]
        self.uicards_tie_pile = []
        
        self.uicard_played_player = None
        self.uicard_played_cpu = None
        self.show_result_modal = False
        
        self.sync_hand_layouts(initial=True)

    def sync_hand_layouts(self, initial=False):
        """計算賸餘手牌坐標並套用滑動動畫"""
        card_w = 90
        spacing = 20
        
        # 玩家手牌 (Y=520)
        p_num = len(self.uicards_player)
        if p_num > 0:
            total_w = p_num * card_w + (p_num - 1) * spacing
            start_x = (1000 - total_w) // 2
            for idx, card in enumerate(self.uicards_player):
                card.target_x = float(start_x + idx * (card_w + spacing))
                card.target_y = 520.0
                if initial:
                    card.x = card.target_x
                    card.y = 750.0  # 從底部滑入
                    
        # 電腦手牌 (Y=50)
        c_num = len(self.uicards_cpu)
        if c_num > 0:
            total_w = c_num * card_w + (c_num - 1) * spacing
            start_x = (1000 - total_w) // 2
            for idx, card in enumerate(self.uicards_cpu):
                card.target_x = float(start_x + idx * (card_w + spacing))
                card.target_y = 50.0
                if initial:
                    card.x = card.target_x
                    card.y = -180.0  # 從頂部滑入

    def play_ui_card(self, uicard):
        """處理玩家出牌操作"""
        if self.is_offline:
            p_data, c_data = self.game_manager.play_card(uicard.card_id)
            if not p_data:
                return
                
            self.uicards_player.remove(uicard)
            uicard.is_played = True
            uicard.is_hovered = False
            self.uicard_played_player = uicard
            self.uicard_played_player.target_x = 455.0
            self.uicard_played_player.target_y = 360.0
            
            # 配對電腦的卡牌
            cpu_target = None
            for uc in self.uicards_cpu:
                if uc.card_id == c_data.card_id:
                    cpu_target = uc
                    break
            if cpu_target:
                self.uicards_cpu.remove(cpu_target)
                cpu_target.is_played = True
                self.uicard_played_cpu = cpu_target
                self.uicard_played_cpu.target_x = 455.0
                self.uicard_played_cpu.target_y = 210.0
        else:
            # 連線模式
            self.uicards_player.remove(uicard)
            uicard.is_played = True
            uicard.is_hovered = False
            self.uicard_played_player = uicard
            self.uicard_played_player.target_x = 455.0
            self.uicard_played_player.target_y = 360.0
            
            self.net_manager.send_data({
                "action": "play_card",
                "card_id": uicard.card_id,
                "card_type": uicard.card_type
            })
            self.game_manager.game_phase = 2  # ANIMATING_PLAY

    def handle_opponent_play_network(self, opp_type, opp_id):
        """連線模式下對手出牌動畫橋接"""
        c_data = ecard_logic.CardData(opp_type, True, opp_id)
        self.game_manager.cpu_played = c_data
        
        if len(self.uicards_cpu) > 0:
            cpu_card = self.uicards_cpu.pop(0)
            cpu_card.card_data = c_data
            cpu_card.card_id = opp_id
            cpu_card.card_type = opp_type
            cpu_card.is_played = True
            
            self.uicard_played_cpu = cpu_card
            self.uicard_played_cpu.target_x = 455.0
            self.uicard_played_cpu.target_y = 210.0
            
            self.game_manager.game_phase = 2  # ANIMATING_PLAY

    def trigger_evaluation(self):
        """結算勝負並執行翻牌計時"""
        result, details = self.game_manager.evaluate_clash()
        if result == "TIE":
            self.active_timer = 1500
        else:
            for uc in self.uicards_cpu:
                uc.start_flip()
            self.active_timer = 1200

    def start_ui_tie_slide(self):
        """觸發平手卡滑動移動"""
        self.game_manager.resolve_tie()
        tie_index = len(self.uicards_tie_pile) // 2
        
        self.uicard_played_cpu.target_x = 790.0
        self.uicard_played_cpu.target_y = float(130 + tie_index * 45)
        self.uicard_played_cpu.face_up = True
        
        self.uicard_played_player.target_x = 880.0
        self.uicard_played_player.target_y = float(130 + tie_index * 45)
        
        self.uicards_tie_pile.append(self.uicard_played_cpu)
        self.uicards_tie_pile.append(self.uicard_played_player)
        self.game_manager.game_phase = 5  # TIE_SLIDING

    def handle_timer_expiration(self):
        """處理延遲定時器到期"""
        if self.game_manager.game_phase == 4:  # TIE_WAIT
            self.start_ui_tie_slide()
        elif self.game_manager.game_phase == 6:  # ROUND_OVER
            self.show_result_modal = True

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 頂部返回大廳按鈕
            back_btn_rect = pygame.Rect(20, 12, 110, 26)
            if back_btn_rect.collidepoint(mouse_pos):
                self.net_manager.disconnect()
                self.game_manager.reset_scores()
                self.cleanup()
                self.game_manager.game_phase = -1  # LOBBY
                return
                
            # 點擊頂部重置比分
            reset_btn_rect = pygame.Rect(870, 12, 110, 26)
            if reset_btn_rect.collidepoint(mouse_pos):
                self.game_manager.reset_scores()
                self.show_result_modal = False
                self.uicards_player = []
                self.uicards_cpu = []
                self.uicards_tie_pile = []
                self.uicard_played_player = None
                self.uicard_played_cpu = None
                if self.is_offline:
                    self.game_manager.game_phase = 0  # CHOOSE_ROLE
                return
                
            # 選角狀態點擊
            if self.game_manager.game_phase == 0:  # CHOOSE_ROLE
                emp_rect = pygame.Rect(180, 260, 260, 200)
                slave_rect = pygame.Rect(560, 260, 260, 200)
                
                if emp_rect.collidepoint(mouse_pos):
                    if self.is_offline:
                        self.start_new_round(ecard_logic.EMPEROR)
                    else:
                        self.net_manager.send_data({
                            "action": "select_role",
                            "role": ecard_logic.EMPEROR
                        })
                        self.game_manager.status_message = "已發送陣營選擇 (皇帝)，等待伺服器同步開局..."
                elif slave_rect.collidepoint(mouse_pos):
                    if self.is_offline:
                        self.start_new_round(ecard_logic.SLAVE)
                    else:
                        self.net_manager.send_data({
                            "action": "select_role",
                            "role": ecard_logic.SLAVE
                        })
                        self.game_manager.status_message = "已發送陣營選擇 (奴隸)，等待伺服器同步開局..."
            
            # 出牌階段點擊
            elif self.game_manager.game_phase == 1:  # PLAYING
                for uc in self.uicards_player:
                    if not uc.is_played and uc.is_hovered:
                        self.play_ui_card(uc)
                        break
                        
            # 結算視窗按鈕點擊
            elif self.game_manager.game_phase == 6 and self.show_result_modal:
                modal_btn = pygame.Rect(380, 430, 240, 50)
                if modal_btn.collidepoint(mouse_pos):
                    self.game_manager.game_phase = 0  # CHOOSE_ROLE
                    self.uicards_player = []
                    self.uicards_cpu = []
                    self.uicards_tie_pile = []
                    self.uicard_played_player = None
                    self.uicard_played_cpu = None
                    self.show_result_modal = False
                    self.game_manager.status_message = "請選擇您的陣營開始新的一局"

    def update(self, dt, mouse_pos):
        # 定時器倒數
        if self.active_timer > 0:
            self.active_timer -= dt
            if self.active_timer <= 0:
                self.active_timer = 0
                self.handle_timer_expiration()
                
        # 更新卡牌位置與動畫
        for uc in self.uicards_player:
            uc.update(dt)
        for uc in self.uicards_cpu:
            uc.update(dt)
        if self.uicard_played_player:
            self.uicard_played_player.update(dt)
        if self.uicard_played_cpu:
            self.uicard_played_cpu.update(dt)
        for uc in self.uicards_tie_pile:
            uc.update(dt)
            
        # 狀態機更新
        if self.game_manager.game_phase == 1:  # PLAYING
            for uc in self.uicards_player:
                rect = pygame.Rect(uc.x, uc.y, uc.width, uc.height)
                if rect.collidepoint(mouse_pos):
                    uc.is_hovered = True
                    uc.target_y = 495.0
                else:
                    uc.is_hovered = False
                    uc.target_y = 520.0
                    
        elif self.game_manager.game_phase == 2:  # ANIMATING_PLAY
            p_arrived = abs(self.uicard_played_player.x - self.uicard_played_player.target_x) < 1.0 and abs(self.uicard_played_player.y - self.uicard_played_player.target_y) < 1.0
            c_arrived = (self.uicard_played_cpu is not None) and (abs(self.uicard_played_cpu.x - self.uicard_played_cpu.target_x) < 1.0 and abs(self.uicard_played_cpu.y - self.uicard_played_cpu.target_y) < 1.0)
            if p_arrived and c_arrived:
                self.uicard_played_player.x, self.uicard_played_player.y = self.uicard_played_player.target_x, self.uicard_played_player.target_y
                self.uicard_played_cpu.x, self.uicard_played_cpu.y = self.uicard_played_cpu.target_x, self.uicard_played_cpu.target_y
                
                self.game_manager.game_phase = 3  # REVEALING
                self.uicard_played_cpu.start_flip()
                
        elif self.game_manager.game_phase == 3:  # REVEALING
            if not self.uicard_played_cpu.is_flipping:
                self.trigger_evaluation()
                
        elif self.game_manager.game_phase == 5:  # TIE_SLIDING
            p_arrived = abs(self.uicard_played_player.x - self.uicard_played_player.target_x) < 1.0 and abs(self.uicard_played_player.y - self.uicard_played_player.target_y) < 1.0
            c_arrived = abs(self.uicard_played_cpu.x - self.uicard_played_cpu.target_x) < 1.0 and abs(self.uicard_played_cpu.y - self.uicard_played_cpu.target_y) < 1.0
            if p_arrived and c_arrived:
                self.uicard_played_player.x, self.uicard_played_player.y = self.uicard_played_player.target_x, self.uicard_played_player.target_y
                self.uicard_played_cpu.x, self.uicard_played_cpu.y = self.uicard_played_cpu.target_x, self.uicard_played_cpu.target_y
                
                self.uicard_played_player = None
                self.uicard_played_cpu = None
                self.game_manager.resolve_tie()
                
                if self.game_manager.game_phase == 1:  # PLAYING
                    self.sync_hand_layouts(initial=False)

    def draw(self, surface, mouse_pos):
        # 繪製背景與頂部
        draw_gradient_background(surface, (15, 16, 22), (25, 28, 38))
        self.draw_header(surface, mouse_pos)
        
        if self.game_manager.game_phase == 0:  # CHOOSE_ROLE
            self.draw_role_selection(surface, mouse_pos)
        else:
            self.draw_placeholders(surface)
            
            # 畫卡片
            for uc in self.uicards_tie_pile:
                uc.draw(surface)
            for uc in self.uicards_cpu:
                uc.draw(surface)
            for uc in self.uicards_player:
                uc.draw(surface)
                
            if self.uicard_played_cpu:
                self.uicard_played_cpu.draw(surface)
            if self.uicard_played_player:
                self.uicard_played_player.draw(surface)
                
        self.draw_status_bar(surface)
        
        if self.game_manager.game_phase == 6 and self.show_result_modal:
            self.draw_result_modal(surface, mouse_pos)

    def draw_header(self, surface, mouse_pos):
        pygame.draw.rect(surface, (15, 15, 20), pygame.Rect(0, 0, 1000, 50))
        pygame.draw.line(surface, (35, 35, 40), (0, 50), (1000, 50), width=1)
        
        back_btn_rect = pygame.Rect(20, 12, 110, 26)
        is_back_hover = back_btn_rect.collidepoint(mouse_pos)
        draw_button(surface, back_btn_rect, "返回遊戲大廳", (40, 40, 45), (60, 60, 70), (220, 220, 220), is_back_hover, get_font(13))
        
        font_title = get_font(18, bold=True)
        title_text = font_title.render("E-CARD 國王與奴隸", True, (200, 180, 140))
        surface.blit(title_text, (150, 13))
        
        font_score = get_font(18, bold=True)
        score_str = f"戰績 — 玩家 {self.game_manager.wins_player} : {self.game_manager.wins_cpu} 電腦"
        score_text = font_score.render(score_str, True, (240, 240, 245))
        score_rect = score_text.get_rect(center=(1000 // 2, 25))
        surface.blit(score_text, score_rect)
        
        reset_btn_rect = pygame.Rect(870, 12, 110, 26)
        is_hovered = reset_btn_rect.collidepoint(mouse_pos)
        draw_button(surface, reset_btn_rect, "重置累計分數", (40, 40, 45), (100, 30, 30), (220, 220, 220), is_hovered, get_font(13))

    def draw_placeholders(self, surface):
        cpu_spot = pygame.Rect(455, 210, 90, 140)
        pygame.draw.rect(surface, (35, 30, 45), cpu_spot, width=1, border_radius=8)
        font = get_font(14)
        lbl = font.render("電腦出牌槽", True, (65, 55, 75))
        surface.blit(lbl, lbl.get_rect(center=cpu_spot.center))
        
        p_spot = pygame.Rect(455, 360, 90, 140)
        pygame.draw.rect(surface, (25, 35, 45), p_spot, width=1, border_radius=8)
        lbl2 = font.render("玩家出牌槽", True, (55, 65, 75))
        surface.blit(lbl2, lbl2.get_rect(center=p_spot.center))
        
        tie_area = pygame.Rect(760, 120, 220, 380)
        pygame.draw.rect(surface, (20, 20, 25), tie_area, border_radius=10)
        pygame.draw.rect(surface, (38, 38, 44), tie_area, width=1, border_radius=10)
        
        font_sub = get_font(14, bold=True)
        tie_lbl = font_sub.render("平局對戰歷程 (Tie Logs)", True, (110, 110, 120))
        surface.blit(tie_lbl, tie_lbl.get_rect(center=(870, 100)))

    def draw_status_bar(self, surface):
        pygame.draw.rect(surface, (10, 10, 15), pygame.Rect(0, 665, 1000, 35))
        pygame.draw.line(surface, (30, 30, 35), (0, 665), (1000, 665), width=1)
        
        font_msg = get_font(14)
        color = (220, 220, 225)
        
        if "勝利" in self.game_manager.status_message:
            color = (255, 215, 0)
        elif "失敗" in self.game_manager.status_message:
            color = (220, 20, 60)
        elif "平手" in self.game_manager.status_message:
            color = (100, 180, 240)
            
        msg_surf = font_msg.render(self.game_manager.status_message, True, color)
        surface.blit(msg_surf, msg_surf.get_rect(center=(1000 // 2, 682)))

    def draw_role_selection(self, surface, mouse_pos):
        font_large = get_font(56, bold=True)
        title_text = font_large.render("E - C A R D", True, (240, 200, 120))
        title_rect = title_text.get_rect(center=(1000 // 2, 115))
        
        title_shadow = font_large.render("E - C A R D", True, (15, 10, 5))
        surface.blit(title_shadow, (title_rect.x + 3, title_rect.y + 3))
        surface.blit(title_text, title_rect)
        
        font_sub = get_font(20, bold=True)
        sub_text = font_sub.render("《賭博默示錄》— 國王與奴隸心理對決", True, (150, 150, 160))
        surface.blit(sub_text, sub_text.get_rect(center=(1000 // 2, 175)))
        
        font_prompt = get_font(16)
        prompt_text = font_prompt.render("【請選擇您在本回合擔任的陣營】", True, (200, 200, 205))
        surface.blit(prompt_text, prompt_text.get_rect(center=(1000 // 2, 220)))
        
        emp_rect = pygame.Rect(180, 260, 260, 200)
        slave_rect = pygame.Rect(560, 260, 260, 200)
        
        emp_hover = emp_rect.collidepoint(mouse_pos)
        slave_hover = slave_rect.collidepoint(mouse_pos)
        
        # 國王
        if emp_hover:
            draw_glow(surface, emp_rect, (255, 215, 0), border_radius=12)
        bg_emp = (45, 35, 15) if emp_hover else (30, 22, 10)
        pygame.draw.rect(surface, bg_emp, emp_rect, border_radius=12)
        border_emp = (255, 215, 0) if emp_hover else (180, 140, 40)
        pygame.draw.rect(surface, border_emp, emp_rect, width=2, border_radius=12)
        ui_components.draw_crown_icon(surface, emp_rect.centerx, emp_rect.y + 65, 1.2, border_emp)
        
        font_btn_title = get_font(24, bold=True)
        text_emp = font_btn_title.render("皇帝陣營", True, (255, 215, 0))
        surface.blit(text_emp, text_emp.get_rect(center=(emp_rect.centerx, emp_rect.y + 130)))
        
        font_btn_desc = get_font(13)
        desc_emp = font_btn_desc.render("執掌國王卡，壓制平民，但懼怕奴隸", True, (200, 190, 160))
        surface.blit(desc_emp, desc_emp.get_rect(center=(emp_rect.centerx, emp_rect.y + 165)))
        
        # 奴隸
        if slave_hover:
            draw_glow(surface, slave_rect, (220, 20, 60), border_radius=12)
        bg_slave = (40, 15, 15) if slave_hover else (25, 10, 10)
        pygame.draw.rect(surface, bg_slave, slave_rect, border_radius=12)
        border_slave = (220, 20, 60) if slave_hover else (160, 30, 30)
        pygame.draw.rect(surface, border_slave, slave_rect, width=2, border_radius=12)
        ui_components.draw_slave_icon(surface, slave_rect.centerx, slave_rect.y + 65, 1.2, border_slave)
        
        text_slave = font_btn_title.render("奴隸陣營", True, (220, 20, 60))
        surface.blit(text_slave, text_slave.get_rect(center=(slave_rect.centerx, slave_rect.y + 130)))
        
        desc_slave = font_btn_desc.render("手握奴隸卡，伺機弒君，但懼怕平民", True, (200, 160, 160))
        surface.blit(desc_slave, desc_slave.get_rect(center=(slave_rect.centerx, slave_rect.y + 165)))
        
        # 說明
        rules_rect = pygame.Rect(180, 490, 640, 160)
        pygame.draw.rect(surface, (20, 20, 25), rules_rect, border_radius=10)
        pygame.draw.rect(surface, (38, 38, 44), rules_rect, width=1, border_radius=10)
        
        font_rules_title = get_font(15, bold=True)
        rules_title = font_rules_title.render("◆ 對決機制與規則說明 ◆", True, (180, 180, 190))
        surface.blit(rules_title, (210, 505))
        
        font_rules = get_font(13)
        rules_lines = [
            "1. 皇帝陣營：手牌包含 1 張皇帝卡與 4 張平民卡；奴隸陣營包含 1 張奴隸卡與 4 張平民卡。",
            "2. 卡牌克制：皇帝 壓制 平民，平民 鎮壓 奴隸，奴隸 逆襲 皇帝（一擊必殺）。",
            "3. 勝負積分：每局對決分多個回合，打出牌分勝負後累計戰績，平局卡牌存入平局槽，繼續下一回合。",
            "4. 局數說明：率先贏取多數回合的玩家將勝出此輪。請點擊上方按鈕選擇您的陣營！"
        ]
        for idx, line in enumerate(rules_lines):
            line_surf = font_rules.render(line, True, (150, 150, 160))
            surface.blit(line_surf, (210, 535 + idx * 26))

    def draw_result_modal(self, surface, mouse_pos):
        modal_rect = pygame.Rect(300, 200, 400, 300)
        draw_rect_alpha(surface, (10, 10, 15, 230), modal_rect, border_radius=15)
        
        winner = self.game_manager.round_winner
        is_player_win = (winner == "Player")
        
        if winner == "Tie":
            color = (100, 180, 240)
            title = "本輪平手"
        else:
            color = (255, 215, 0) if is_player_win else (220, 20, 60)
            title = "你贏了本輪！" if is_player_win else "你輸了本輪..."
            
        pygame.draw.rect(surface, color, modal_rect, width=2, border_radius=15)
        
        font_modal_title = get_font(28, bold=True)
        title_surf = font_modal_title.render(title, True, color)
        surface.blit(title_surf, title_surf.get_rect(center=(500, 250)))
        
        font_modal_desc = get_font(13)
        desc_surf = font_modal_desc.render(self.game_manager.status_message, True, (180, 180, 190))
        surface.blit(desc_surf, desc_surf.get_rect(center=(500, 320)))
        
        score_surf = get_font(16, bold=True).render(f"目前戰績: 玩家 {self.game_manager.wins_player} : {self.game_manager.wins_cpu} 電腦", True, (240, 240, 245))
        surface.blit(score_surf, score_surf.get_rect(center=(500, 370)))
        
        btn_rect = pygame.Rect(380, 430, 240, 50)
        btn_hover = btn_rect.collidepoint(mouse_pos)
        btn_bg = (255, 215, 0) if is_player_win else (220, 20, 60)
        btn_hover_bg = (220, 180, 0) if is_player_win else (180, 15, 45)
        btn_text_color = (15, 15, 20) if is_player_win else (255, 255, 255)
        
        draw_button(surface, btn_rect, "開始下一局遊戲", btn_bg, btn_hover_bg, btn_text_color, btn_hover, get_font(18, bold=True))
