# filepath: C:\Users\ethan\Desktop\Project\src\common\network_manager.py
"""
E-Card (國王與奴隸) - TCP 網路層對接管理器模組
==========================================

此模組負責對接 C 語言與 Python 的 TCP 連線層。
當 C 連線庫編譯完成後，將動態加載並取得連線 Socket，將其包裝為 Python 原生的套接字，
並在更新迴圈中進行非阻塞 (non-blocking) 資料輪詢與 JSON 訊息分包解析。

本模組具備「模擬對接模式」：若 C 連線庫尚未編譯，將會自動啟用模擬運作，確保離線測試順暢。
"""

import socket
import json
import os

class NetworkManager:
    def __init__(self):
        self.is_connected = False
        self.is_host = False
        self.server_ip = "127.0.0.1"
        self.server_port = 8888
        self.sock = None
        self._recv_buffer = ""
        
        # 玩家名字與對手名字
        self.player_name = "Player"
        self.opponent_name = "Opponent"
        
        # 主機端局數狀態暫存變數
        self.host_role = None
        self.client_role = None
        self.host_card = None
        self.client_card = None
        self.wins_host = 0
        self.wins_client = 0
        
        # 事件回呼掛鉤 (由 main.py / ecard_ui.py 註冊)
        self.on_connected = None         # 連線成功回呼: lambda: ...
        self.on_disconnected = None      # 斷線回呼: lambda reason: ...
        self.on_receive_message = None   # 接收完整 JSON 數據回呼: lambda data_dict: ...
        self.on_error = None             # 通訊錯誤回呼: lambda err_msg: ...
        
        # 嘗試載入隊友開發的 C 連線對接包
        self.connection = None
        self._load_connection_module()

    def _load_connection_module(self):
        """動態加載 TCP connection 模組"""
        try:
            from src.connection import connection
            self.connection = connection
            print("[Network] 成功載入 C 連線對接包 (src.connection)")
        except Exception as e:
            print(f"[Network] 未能載入 C 連線庫 ({str(e)})。啟用「模擬對接模式」。")
            self.connection = None

    def connect(self, ip, port):
        """嘗試建立 TCP 客戶端連線"""
        self.is_host = False
        self.server_ip = ip
        self.server_port = int(port)
        
        # 模擬模式 fallback
        if not self.connection:
            self.is_connected = True
            if self.on_connected:
                self.on_connected()
            return True, "模擬連線成功 (未加載 C 庫)"
            
        try:
            # 呼叫 C 端連線，並取得包裝好的 Python socket 物件
            py_socket = self.connection.connect_to_server(ip, self.server_port)
            if py_socket:
                self.sock = py_socket
                self.sock.setblocking(False)  # 設為非阻塞模式以利主更新執行緒輪詢
                self._recv_buffer = ""
                self.is_connected = True
                
                # 發送握手訊息給 Host 以同步名字
                self.send_data({"action": "handshake", "name": self.player_name})
                
                if self.on_connected:
                    self.on_connected()
                return True, "連線成功"
            else:
                self.is_connected = False
                return False, "C 庫連線失敗，返回空套接字"
        except Exception as e:
            self.is_connected = False
            return False, f"呼叫 C 連線函數異常: {str(e)}"

    def host(self, port):
        """嘗試開立 TCP 伺服器並在背景等待連線"""
        self.is_host = True
        self.server_port = int(port)
        self.host_role = None
        self.client_role = None
        self.host_card = None
        self.client_card = None
        self.wins_host = 0
        self.wins_client = 0
        
        conn = self.connection
        # 模擬模式 fallback
        if not conn:
            self.is_connected = True
            if self.on_connected:
                self.on_connected()
            return True, "模擬開房成功 (未加載 C 庫)"
            
        import threading
        
        def listen_thread():
            try:
                # 呼叫 C 端監聽 Server，並取得包裝好的 Python socket 物件 (這會阻塞直到 client 連線)
                py_socket = conn.start_server(self.server_port)
                if py_socket:
                    self.sock = py_socket
                    self.sock.setblocking(False)  # 設為非阻塞
                    self._recv_buffer = ""
                    self.is_connected = True
                    # 回呼通知連線成功，主執行緒會在 poll 中偵測到並做出轉換
                    if self.on_connected:
                        self.on_connected()
                    print("[Network Host] Client connected successfully via C server socket!")
                else:
                    self.is_connected = False
                    if self.on_error:
                        self.on_error("建立 C 伺服器監聽失敗")
            except Exception as e:
                self.is_connected = False
                if self.on_error:
                    self.on_error(f"C 伺服器連線執行緒異常: {str(e)}")

        threading.Thread(target=listen_thread, daemon=True).start()
        return True, "伺服器已啟動，正在等待對手連入..."

    def disconnect(self):
        """中斷連線並釋放資源"""
        if self.is_connected:
            self.is_connected = False
            self.is_host = False
            if self.sock:
                try:
                    if self.connection:
                        self.connection.close_socket(self.sock)
                    else:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
            if self.on_disconnected:
                self.on_disconnected("連線已中斷")

    def send_data(self, data_dict):
        """將資料字典序列化為 JSON 字串並發送"""
        if not self.is_connected:
            return False, "未連線"
            
        if self.is_host:
            # 主機模式下，攔截主機玩家出牌與選角封包，進行本地伺服器規則模擬
            self._process_host_send(data_dict)
            return True, "發送成功 (主機模擬)"
            
        # 模擬模式直接回傳成功
        if not self.sock:
            return True, "模擬發送成功"
            
        try:
            json_str = json.dumps(data_dict)
            self.sock.sendall(json_str.encode('utf-8'))
            return True, "發送成功"
        except Exception as e:
            self.disconnect()
            return False, f"發送資料異常: {str(e)}"

    def _process_host_send(self, data_dict):
        """處理 Host 本地玩家發送的訊息"""
        action = data_dict.get("action")
        if action == "select_role":
            self.host_role = data_dict.get("role")
            self.client_role = "Slave" if self.host_role == "Emperor" else "Emperor"
            # 傳給 Client
            self._send_to_client({"action": "game_start", "role": self.client_role})
            # 傳回給 Host 本地 UI
            self._deliver_local({"action": "game_start", "role": self.host_role})
        elif action == "play_card":
            self.host_card = data_dict
            self._check_and_evaluate()

    def _process_client_msg(self, data_dict):
        """處理 Client 傳入的訊息"""
        action = data_dict.get("action")
        if action == "handshake":
            self.opponent_name = data_dict.get("name", "Guest") or "Guest"
            print(f"[Network Host] Received client name: {self.opponent_name}")
            # 回傳主機的名字給客機，同時觸發對方的 sync_names 封包
            self._send_to_client({
                "action": "sync_names",
                "player_name": self.opponent_name,
                "opponent_name": self.player_name
            })
            # 派發給主機本地 UI 讓其更新名字
            self._deliver_local({
                "action": "sync_names",
                "player_name": self.player_name,
                "opponent_name": self.opponent_name
            })
        elif action == "select_role":
            self.client_role = data_dict.get("role")
            self.host_role = "Slave" if self.client_role == "Emperor" else "Emperor"
            # 傳給 Client
            self._send_to_client({"action": "game_start", "role": self.client_role})
            # 傳回給 Host 本地 UI
            self._deliver_local({"action": "game_start", "role": self.host_role})
        elif action == "play_card":
            self.client_card = data_dict
            self._check_and_evaluate()

    def _check_and_evaluate(self):
        """檢查是否雙方出牌完畢，若完畢則進行判定並廣播"""
        if self.host_card and self.client_card:
            host_card_type = self.host_card.get("card_type")
            host_card_id = self.host_card.get("card_id")
            client_card_type = self.client_card.get("card_type")
            client_card_id = self.client_card.get("card_id")

            # 1. 廣播對手出牌狀態
            self._send_to_client({
                "action": "opponent_played",
                "card_type": host_card_type,
                "card_id": host_card_id
            })
            self._deliver_local({
                "action": "opponent_played",
                "card_type": client_card_type,
                "card_id": client_card_id
            })

            # 2. 進行克制判定
            winner, reason = self._evaluate_ecard(host_card_type, client_card_type)

            if winner == "TIE":
                # 平手局在 Client 本地邏輯中已可直接藉由 evaluate_clash() 判斷並處理 TIE_WAIT，
                # 故此處不用發送 round_result
                pass
            else:
                if winner == "host":
                    self.wins_host += 1
                    winner_str_host = "Player"
                    winner_str_client = "CPU"
                    reason_host = f"【勝利】{reason}"
                    reason_client = f"【失敗】{reason}"
                else:
                    self.wins_client += 1
                    winner_str_host = "CPU"
                    winner_str_client = "Player"
                    reason_host = f"【失敗】{reason}"
                    reason_client = f"【勝利】{reason}"

                # 發送結算結果
                self._send_to_client({
                    "action": "round_result",
                    "winner": winner_str_client,
                    "reason": reason_client,
                    "wins_player": self.wins_client,
                    "wins_cpu": self.wins_host
                })
                self._deliver_local({
                    "action": "round_result",
                    "winner": winner_str_host,
                    "reason": reason_host,
                    "wins_player": self.wins_host,
                    "wins_cpu": self.wins_client
                })

            # 3. 清空本回合暫存
            self.host_card = None
            self.client_card = None

    def _evaluate_ecard(self, host_card_type, client_card_type):
        """Ecard 勝負核心邏輯計算"""
        if host_card_type == "Citizen" and client_card_type == "Citizen":
            return "TIE", "雙方皆為平民！判定平局。請準備出下一張牌..."
            
        winner = None  # "host" or "client"
        reason = ""
        
        if self.host_role == "Emperor":
            # 主機為國王方，客機為奴隸方
            if host_card_type == "Emperor" and client_card_type == "Citizen":
                winner = "host"
                reason = "國王 駕崩平民！陛下取得了勝利。"
            elif host_card_type == "Citizen" and client_card_type == "Slave":
                winner = "host"
                reason = "平民 鎮壓奴隸！玩家防守成功。"
            elif host_card_type == "Emperor" and client_card_type == "Slave":
                winner = "client"
                reason = "奴隸 逆襲國王！對手反叛弒君成功。"
        else:
            # 主機為奴隸方，客機為國王方
            if host_card_type == "Slave" and client_card_type == "Emperor":
                winner = "host"
                reason = "奴隸 逆襲國王！玩家反叛弒君成功。"
            elif host_card_type == "Citizen" and client_card_type == "Emperor":
                winner = "client"
                reason = "國王 駕崩平民！對手取得了勝利。"
            elif host_card_type == "Slave" and client_card_type == "Citizen":
                winner = "client"
                reason = "平民 鎮壓奴隸！對手防守成功。"
                
        return winner, reason

    def _send_to_client(self, data_dict):
        """發送封包給客機"""
        if self.sock:
            try:
                json_str = json.dumps(data_dict)
                self.sock.sendall(json_str.encode('utf-8'))
            except Exception as e:
                print(f"[Network Host] 發送封包至客機異常: {e}")

    def _deliver_local(self, data_dict):
        """派發本地封包至 UI 監聽回呼"""
        if self.on_receive_message:
            self.on_receive_message(data_dict)

    def poll(self):
        """由 Pygame 主更新迴圈每幀調用，用以非阻塞式輪詢接收緩衝區"""
        if not self.is_connected or not self.sock:
            return
            
        try:
            # 讀取非阻塞套接字
            data = self.sock.recv(4096)
            if not data:
                # 對端已正常關閉連線
                self.disconnect()
                return
                
            self._recv_buffer += data.decode('utf-8')
            
            # 解析串流中所有完整的 JSON 物件
            while self._recv_buffer:
                self._recv_buffer = self._recv_buffer.lstrip()
                if not self._recv_buffer.startswith('{'):
                    # 丟棄開頭垃圾字元以防死鎖
                    if self._recv_buffer:
                        self._recv_buffer = self._recv_buffer[1:]
                    continue
                
                # 計算對稱的花括弧以斷包
                brace_count = 0
                in_quote = False
                escape = False
                end_idx = -1
                
                for idx, char in enumerate(self._recv_buffer):
                    if escape:
                        escape = False
                        continue
                    if char == '\\':
                        escape = True
                        continue
                    if char == '"':
                        in_quote = not in_quote
                        continue
                    if not in_quote:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = idx + 1
                                break
                                
                if end_idx != -1:
                    json_str = self._recv_buffer[:end_idx]
                    self._recv_buffer = self._recv_buffer[end_idx:]
                    try:
                        data_dict = json.loads(json_str)
                        if self.is_host:
                            # 主機攔截客機資料並在本地做伺服器邏輯分發
                            self._process_client_msg(data_dict)
                        else:
                            # 客機直接投遞至連線回呼
                            if self.on_receive_message:
                                self.on_receive_message(data_dict)
                    except json.JSONDecodeError as e:
                        print(f"[Network] JSON 斷包格式解析錯誤: {e}")
                else:
                    # 資料尚不完整，等待下一幀 poll 接收剩餘內容
                    break
                    
        except BlockingIOError:
            # 無新資料，正常返回
            pass
        except socket.error as e:
            # WouldBlock / TryAgain 在非阻塞下為正常現象
            import errno
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                pass
            else:
                if self.on_error:
                    self.on_error(f"連線套接字異常: {str(e)}")
                self.disconnect()
        except Exception as e:
            if self.on_error:
                self.on_error(f"輪詢資料異常: {str(e)}")
            self.disconnect()
