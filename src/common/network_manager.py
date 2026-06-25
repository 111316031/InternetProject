# filepath: C:\Users\ethan\Desktop\Project-Combine\src\common\network_manager.py
"""
E-Game Center (國王與奴隸 & 限定剪刀石頭布) - TCP 網路層管理器
=========================================================

重構為「房主一鍵啟動中央伺服器」模式：
1. 當 Host 開房時，主動在背景啟動獨立執行緒運行 server.py。
2. 不論 Host 還是 Client 均連線至中央伺服器 (Host 連線 127.0.0.1，Client 連線指定 IP)。
3. 使用 Line-delimited JSON 協定 (\n) 與 C 底層 Socket 進行非阻塞資料輪詢。
"""

import socket
import json
import os
import threading
import time
from typing import Callable, Any, Optional

class NetworkManager:
    def __init__(self):
        self.is_connected = False
        self.is_connecting = False
        self.is_host = False
        self.server_ip = "127.0.0.1"
        self.server_port = 8888
        self.sock = None
        self._recv_buffer = ""
        
        # 玩家名字與對手名字
        self.player_name = "Player"
        self.opponent_name = "Opponent"
        
        # 房間大廳狀態變數
        self.room_id = None
        self.room_host = None
        self.room_players = []  # [{"name": str, "is_bot": bool, "status": str}, ...]
        self.room_status = "LOBBY"
        self.room_bots_count = 0
        
        # 主機端局數狀態暫存變數
        self.host_role = None
        self.client_role = None
        self.host_card = None
        self.client_card = None
        self.wins_host = 0
        self.wins_client = 0
        
        # 事件回呼掛鉤
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[str], None]] = None
        self.on_receive_message: Optional[Callable[[dict[str, Any]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # C 連線庫對接
        self.connection = None
        self.game_type = "ecard"  # "ecard" or "rps"
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
        """Client 模式：非同步在背景連線至指定中央伺服器並加入房間"""
        if self.is_connecting or self.is_connected:
            return True, "正在連線中..."
            
        self.is_host = False
        self.server_ip = ip
        self.server_port = int(port)
        
        if not self.connection:
            self.is_connected = True
            self.room_id = "1234"
            self.room_host = "HostName"
            self.room_players = [
                {"name": "HostName", "is_bot": False, "status": "LOBBY"},
                {"name": self.player_name, "is_bot": False, "status": "LOBBY"}
            ]
            if self.on_connected:
                self.on_connected()
            return True, "模擬連線成功 (未加載 C 庫)"
            
        self.is_connecting = True
        
        def connect_thread():
            try:
                py_socket = self.connection.connect_to_server(ip, self.server_port)
                if py_socket:
                    # 檢查連線期間是否已手動取消/中斷
                    if not self.is_connecting:
                        if self.connection:
                            self.connection.close_socket(py_socket)
                        else:
                            py_socket.close()
                        return
                    self.sock = py_socket
                    self.sock.setblocking(False)
                    self._recv_buffer = ""
                    self.is_connected = True
                    self.is_connecting = False
                    
                    self.send_data({
                        "action": "join_room",
                        "name": self.player_name,
                        "game_type": self.game_type
                    })
                    
                    if self.on_connected:
                        self.on_connected()
                else:
                    self.is_connected = False
                    self.is_connecting = False
                    if self.on_error:
                        self.on_error("C 庫連線失敗，返回空套接字")
            except Exception as e:
                self.is_connected = False
                self.is_connecting = False
                if self.on_error:
                    self.on_error(f"連線伺服器異常: {str(e)}")
                    
        threading.Thread(target=connect_thread, daemon=True).start()
        return True, "正在與伺服器建立連線..."

    def host(self, port):
        """HOST 模式：一鍵在背景啟動中央伺服器，並連線至 127.0.0.1 建立房間"""
        self.is_host = True
        self.server_port = int(port)
        self.host_role = None
        self.client_role = None
        self.host_card = None
        self.client_card = None
        self.wins_host = 0
        self.wins_client = 0
        
        # 1. 於背景執行緒啟動 server.py
        try:
            import server
            def run_server_daemon():
                try:
                    server.main()
                except Exception as se:
                    print(f"[Network Host] Server background stopped: {se}")
            t = threading.Thread(target=run_server_daemon, daemon=True)
            t.start()
            print("[Network Host] 已於背景執行緒成功啟動中央伺服器。")
        except Exception as e:
            print(f"[Network Host] 啟動/匯入 server.py 失敗: {e}")
            
        # 等待 0.2 秒讓伺服器順利綁定 Port
        time.sleep(0.2)
        
        if not self.connection:
            self.is_connected = True
            self.room_id = "1234"
            self.room_host = self.player_name
            self.room_players = [{"name": self.player_name, "is_bot": False, "status": "LOBBY"}]
            if self.on_connected:
                self.on_connected()
            return True, "模擬開房成功 (未加載 C 庫)"
            
        try:
            # 本地 Host 連入 127.0.0.1 的中央伺服器
            py_socket = self.connection.connect_to_server("127.0.0.1", self.server_port)
            if py_socket:
                self.sock = py_socket
                self.sock.setblocking(False)
                self._recv_buffer = ""
                self.is_connected = True
                
                # 發送 create_room 建立房間
                self.send_data({
                    "action": "create_room",
                    "name": self.player_name,
                    "game_type": self.game_type
                })
                
                if self.on_connected:
                    self.on_connected()
                return True, "伺服器已建立並成功創房！"
            else:
                self.is_connected = False
                return False, "C 庫連線本地伺服器失敗"
        except Exception as e:
            self.is_connected = False
            return False, f"連線本地伺服器異常: {str(e)}"

    def disconnect(self):
        """中斷連線並釋放資源"""
        was_active = self.is_connected or self.is_connecting
        self.is_connected = False
        self.is_connecting = False
        self.is_host = False
        self.room_id = None
        self.room_host = None
        self.room_players = []
        if self.sock:
            try:
                if self.connection:
                    self.connection.close_socket(self.sock)
                else:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None
        if was_active and self.on_disconnected:
            self.on_disconnected("連線已中斷")

    def send_data(self, data_dict):
        """將資料序列化為 JSON + \\n 發送"""
        if not self.is_connected:
            return False, "未連線"
            
        if not self.sock:
            self._process_mock_send(data_dict)
            return True, "模擬發送成功"
            
        try:
            json_str = json.dumps(data_dict) + "\n"
            self.sock.sendall(json_str.encode('utf-8'))
            return True, "發送成功"
        except Exception as e:
            self.disconnect()
            return False, f"發送資料異常: {str(e)}"

    def _process_mock_send(self, data_dict):
        action = data_dict.get("action")
        if action == "ADD_BOT":
            self.room_bots_count += 1
            bot_name = f"BOT_{self.room_bots_count}"
            self.room_players.append({"name": bot_name, "is_bot": True, "status": "LOBBY"})
            if self.on_receive_message:
                self.on_receive_message({
                    "action": "ROOM_INFO_UPDATE",
                    "room_id": self.room_id,
                    "host": self.room_host,
                    "players": self.room_players,
                    "bots_count": self.room_bots_count,
                    "status": self.room_status
                })
        elif action == "REMOVE_BOT":
            bot_to_remove = None
            for p in reversed(self.room_players):
                if p.get("is_bot", False):
                    bot_to_remove = p
                    break
            if bot_to_remove:
                self.room_players.remove(bot_to_remove)
                self.room_bots_count = max(0, self.room_bots_count - 1)
                if self.on_receive_message:
                    self.on_receive_message({
                        "action": "ROOM_INFO_UPDATE",
                        "room_id": self.room_id,
                        "host": self.room_host,
                        "players": self.room_players,
                        "bots_count": self.room_bots_count,
                        "status": self.room_status
                    })
        elif action == "START_GAME_REQ":
            self.room_status = "PLAYING"
            if self.on_receive_message:
                self.on_receive_message({
                    "action": "GAME_START",
                    "opponent_name": f"BOT_{self.room_bots_count}",
                    "opponents": [f"BOT_{self.room_bots_count}"]
                })

    def _process_host_send(self, data_dict):
        self.send_data(data_dict)

    def _process_client_msg(self, data_dict):
        if self.on_receive_message:
            self.on_receive_message(data_dict)

    def _deliver_local(self, data_dict):
        if self.on_receive_message:
            self.on_receive_message(data_dict)

    def poll(self):
        """非阻塞式輪詢接收緩衝區"""
        if not self.is_connected or not self.sock:
            return
            
        try:
            data = self.sock.recv(4096)
            if not data:
                self.disconnect()
                return
                
            self._recv_buffer += data.decode('utf-8')
            
            while '\n' in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    data_dict = json.loads(line)
                    
                    if data_dict.get("action") == "ROOM_INFO_UPDATE":
                        self.room_id = data_dict.get("room_id")
                        self.room_host = data_dict.get("host")
                        self.room_players = data_dict.get("players", [])
                        self.room_bots_count = data_dict.get("bots_count", 0)
                        self.room_status = data_dict.get("status")
                    
                    if self.on_receive_message:
                        self.on_receive_message(data_dict)
                        
                except json.JSONDecodeError as e:
                    print(f"[Network] JSON 斷包格式解析錯誤: {e}")
                    
        except BlockingIOError:
            pass
        except socket.error as e:
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
