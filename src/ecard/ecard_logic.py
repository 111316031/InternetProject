# filepath: C:\Users\ethan\Desktop\Project\src\ecard\ecard_logic.py
"""
E-Card (國王與奴隸) - 核心遊戲邏輯模組
==================================

此模組定義遊戲規則、手牌狀態管理與對決勝負判定，完全不依賴 Pygame 視窗或渲染邏輯。
便於未來擴充網路 Socket 功能或導入 AI 決策邏輯。

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

系統依賴與安裝 (Dependencies & Installation)
----------------------------------------
請在命令列執行以下指令進行安裝：
    pip install pygame

執行方式 (How to Run)
--------------------
在專案根目錄下執行：
    python main.py
"""

import random

# ==========================================
# 遊戲卡牌常數定義
# ==========================================
EMPEROR = "Emperor"
SLAVE = "Slave"
CITIZEN = "Citizen"

# ==========================================
# 遊戲狀態常數定義 (無渲染狀態機)
# ==========================================
CHOOSE_ROLE = 0
PLAYING = 1
ANIMATING_PLAY = 2
REVEALING = 3
TIE_WAIT = 4
TIE_SLIDING = 5
ROUND_OVER = 6

class CardData:
    """卡牌邏輯數據類別，用於分離資料與繪圖渲染"""
    def __init__(self, card_type, is_cpu, card_id):
        self.card_type = card_type
        self.is_cpu = is_cpu
        self.card_id = card_id  # 唯一標識 ID，便於與 UI 動畫對象關聯

class EcardGame:
    """核心遊戲規則與狀態控制器"""
    def __init__(self):
        self.wins_player = 0
        self.wins_cpu = 0
        self.player_role = EMPEROR
        self.cpu_role = SLAVE
        self.player_hand = []  # 玩家目前賸餘手牌 (List of CardData)
        self.cpu_hand = []    # 電腦目前賸餘手牌 (List of CardData)
        self.player_played = None  # 玩家已打出之卡牌 (CardData)
        self.cpu_played = None    # 電腦已打出之卡牌 (CardData)
        self.tie_pile = []        # 因平手暫存於場上的卡牌記錄
        self.game_phase = CHOOSE_ROLE
        self.status_message = "請選擇您的陣營開始遊戲"
        self.round_winner = None
        self._next_id = 0

    def get_next_id(self):
        """產生卡牌的唯一識別碼"""
        self._next_id += 1
        return self._next_id

    def init_round(self, p_role):
        """初始化一輪新的遊戲陣營與手牌"""
        self.player_role = p_role
        self.cpu_role = SLAVE if p_role == EMPEROR else EMPEROR
        
        self.player_played = None
        self.cpu_played = None
        self.tie_pile = []
        self.player_hand = []
        self.cpu_hand = []
        
        # 根據玩家陣營分配卡牌
        if self.player_role == EMPEROR:
            self.player_hand.append(CardData(EMPEROR, False, self.get_next_id()))
            for _ in range(4):
                self.player_hand.append(CardData(CITIZEN, False, self.get_next_id()))
                
            self.cpu_hand.append(CardData(SLAVE, True, self.get_next_id()))
            for _ in range(4):
                self.cpu_hand.append(CardData(CITIZEN, True, self.get_next_id()))
        else:
            self.player_hand.append(CardData(SLAVE, False, self.get_next_id()))
            for _ in range(4):
                self.player_hand.append(CardData(CITIZEN, False, self.get_next_id()))
                
            self.cpu_hand.append(CardData(EMPEROR, True, self.get_next_id()))
            for _ in range(4):
                self.cpu_hand.append(CardData(CITIZEN, True, self.get_next_id()))
                
        # 隨機打亂手牌順序
        random.shuffle(self.player_hand)
        random.shuffle(self.cpu_hand)
        
        self.game_phase = PLAYING
        self.status_message = "請點擊一張手牌，將其打出！"
        self.round_winner = None

    def play_card(self, p_card_id):
        """處理玩家出牌，並觸發電腦對手的隨機出牌決策"""
        p_card = None
        for card in self.player_hand:
            if card.card_id == p_card_id:
                p_card = card
                break
        if not p_card:
            return None, None
            
        self.player_hand.remove(p_card)
        self.player_played = p_card
        
        # 電腦隨機選擇手牌打出
        cpu_card = random.choice(self.cpu_hand)
        self.cpu_hand.remove(cpu_card)
        self.cpu_played = cpu_card
        
        self.game_phase = ANIMATING_PLAY
        self.status_message = "對決進行中，卡牌已配置..."
        return p_card, cpu_card

    def evaluate_clash(self):
        """判定打出卡牌的克制關係與輸贏"""
        if self.player_played is None or self.cpu_played is None:
            return "ERROR", "無效的對決：出牌資料缺失！"
            
        p_type = self.player_played.card_type
        c_type = self.cpu_played.card_type
        
        # 雙方平民：平手
        if p_type == CITIZEN and c_type == CITIZEN:
            self.status_message = "雙方皆為平民！判定平局。請準備出下一張牌..."
            self.game_phase = TIE_WAIT
            return "TIE", self.status_message
            
        # 勝負判定
        winner = None
        reason = ""
        
        if self.player_role == EMPEROR:
            # 玩家為國王方，電腦為奴隸方
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
            # 玩家為奴隸方，電腦為國王方
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
            self.wins_player += 1
            self.round_winner = "Player"
            self.status_message = f"【勝利】{reason}"
        else:
            self.wins_cpu += 1
            self.round_winner = "CPU"
            self.status_message = f"【失敗】{reason}"
            
        self.game_phase = ROUND_OVER
        return winner, self.status_message

    def resolve_tie(self):
        """處理平手局的卡片存檔，並重設本輪的出牌"""
        self.tie_pile.append(self.cpu_played)
        self.tie_pile.append(self.player_played)
        self.player_played = None
        self.cpu_played = None
        
        if len(self.player_hand) > 0:
            self.game_phase = PLAYING
            self.status_message = "平局卡已存檔。請點擊下一張手牌打出。"
        else:
            self.status_message = "所有卡牌用罄，平局結束此輪。"
            self.game_phase = ROUND_OVER
            self.round_winner = "Tie"

    def reset_scores(self):
        """將玩家與電腦的累計戰績歸零"""
        self.wins_player = 0
        self.wins_cpu = 0
        self.game_phase = CHOOSE_ROLE
        self.status_message = "分數已重置。請重新選擇陣營開始遊戲。"
