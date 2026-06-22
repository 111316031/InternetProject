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
        self.server_ip = "127.0.0.1"
        self.server_port = 8888
        self.sock = None
        self._recv_buffer = ""
        
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
        """嘗試建立 TCP 連線"""
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
                if self.on_connected:
                    self.on_connected()
                return True, "連線成功"
            else:
                self.is_connected = False
                return False, "C 庫連線失敗，返回空套接字"
        except Exception as e:
            self.is_connected = False
            return False, f"呼叫 C 連線函數異常: {str(e)}"

    def disconnect(self):
        """中斷連線並釋放資源"""
        if self.is_connected:
            self.is_connected = False
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
