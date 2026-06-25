# filepath: C:\Users\ethan\Desktop\Project-Combine\server.py
"""
E-Game Center 中央遊戲伺服器 (Central Game Server)
=================================================

多玩家大廳中央伺服器：
1. 支援國王與奴隸 (限2人) 與限定剪刀石頭布 (無人數上限) 的大廳房主控制與機器人加入。
2. 進行位置同步的組內廣播 (Broadcast to room except sender)。
3. 對於帶有 target 欄位的指令 (互動邀請、交易封包)，精準轉發給目標玩家。
4. 只要有人斷線/退出，解散房間以保持邏輯簡單安全。
"""

import socket
import json
import threading
import random

HOST = "0.0.0.0"
PORT = 8888

GAME_ROOMS = {}
rooms_lock = threading.Lock()

def get_unique_room_id():
    return str(random.randint(1000, 9999))

def broadcast_to_room(room, data_dict, exclude_sock=None):
    """將訊息廣播給房間內的所有人，可排除特定的 socket"""
    json_str = json.dumps(data_dict) + "\n"
    payload = json_str.encode('utf-8')
    for player in room["players"]:
        if not player["is_bot"] and player["socket"]:
            if player["socket"] == exclude_sock:
                continue
            try:
                player["socket"].sendall(payload)
            except Exception as e:
                print(f"[Server] Broadcast failed to {player['name']}: {e}")

def send_to_player_by_name(room, name, data_dict):
    """根據暱稱將訊息發送給單一玩家"""
    json_str = json.dumps(data_dict) + "\n"
    payload = json_str.encode('utf-8')
    for player in room["players"]:
        if player["name"] == name and not player["is_bot"] and player["socket"]:
            try:
                player["socket"].sendall(payload)
                return True
            except Exception as e:
                print(f"[Server] Target send failed to {name}: {e}")
    return False

def send_to_player(player, data_dict):
    if player["is_bot"] or not player["socket"]:
        return
    try:
        json_str = json.dumps(data_dict) + "\n"
        player["socket"].sendall(json_str.encode('utf-8'))
    except Exception as e:
        print(f"[Server] Send failed to {player['name']}: {e}")

def send_room_info_update(room):
    players_info = []
    for p in room["players"]:
        players_info.append({
            "name": p["name"],
            "is_bot": p["is_bot"],
            "status": room["status"]
        })
    
    update_data = {
        "action": "ROOM_INFO_UPDATE",
        "room_id": room["room_id"],
        "host": room["host"],
        "players": players_info,
        "bots_count": room["bots_count"],
        "status": room["status"]
    }
    broadcast_to_room(room, update_data)

def evaluate_ecard(host_role, host_card_type, client_card_type):
    if host_card_type == "Citizen" and client_card_type == "Citizen":
        return "TIE", "雙方皆為平民！判定平局。請準備出下一張牌..."
        
    winner = None
    reason = ""
    
    if host_role == "Emperor":
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

def handle_client_disconnect(client_sock):
    with rooms_lock:
        for r_id, room in list(GAME_ROOMS.items()):
            has_disconnected_player = False
            for p in room["players"]:
                if not p["is_bot"] and p["socket"] == client_sock:
                    has_disconnected_player = True
                    break
            
            if has_disconnected_player:
                broadcast_to_room(room, {
                    "action": "error",
                    "message": "有玩家退出，房間已解散。"
                })
                del GAME_ROOMS[r_id]
                print(f"[Server] Room {r_id} disbanded because a player disconnected.")
                break

def process_message(client_sock, msg):
    action = msg.get("action")
    name = msg.get("name", "Unknown")
    
    if action == "create_room":
        game_type = msg.get("game_type", "ecard")
        with rooms_lock:
            r_id = get_unique_room_id()
            new_room = {
                "room_id": r_id,
                "game_type": game_type,
                "status": "LOBBY",
                "host": name,
                "players": [{"name": name, "is_bot": False, "socket": client_sock, "role": None}],
                "bots_count": 0,
                "game_state": {
                    "host_card": None,
                    "client_card": None,
                    "wins_host": 0,
                    "wins_client": 0,
                    "host_role": None,
                    "client_role": None,
                    "bot_hand": []
                }
            }
            GAME_ROOMS[r_id] = new_room
            print(f"[Server] Room {r_id} ({game_type}) created by Host '{name}'")
            send_room_info_update(new_room)
            return

    elif action == "join_room":
        game_type = msg.get("game_type", "ecard")
        with rooms_lock:
            joined = False
            for r_id, room in GAME_ROOMS.items():
                if room["game_type"] == game_type and room["status"] == "LOBBY":
                    if game_type == "ecard":
                        # E-Card 限制 2 人，若已滿且其中有機器人，則將機器人擠掉
                        if len(room["players"]) < 2:
                            room["players"].append({"name": name, "is_bot": False, "socket": client_sock, "role": None})
                            print(f"[Server] Player '{name}' joined Room {r_id}")
                            send_room_info_update(room)
                            
                            # E-Card 滿 2 人自動開局
                            if len(room["players"]) == 2:
                                room["status"] = "PLAYING"
                                for p in room["players"]:
                                    if not p["is_bot"]:
                                        opp_of_p = [x for x in room["players"] if x["name"] != p["name"]][0]
                                        send_to_player(p, {
                                            "action": "GAME_START",
                                            "opponent_name": opp_of_p["name"]
                                        })
                                print(f"[Server] E-Card room {r_id} automatically started game.")
                                
                            joined = True
                            break
                        else:
                            # 尋找機器人並替換
                            bot_p = None
                            for p in room["players"]:
                                if p["is_bot"]:
                                    bot_p = p
                                    break
                            if bot_p:
                                room["players"].remove(bot_p)
                                room["players"].append({"name": name, "is_bot": False, "socket": client_sock, "role": None})
                                print(f"[Server] Player '{name}' joined Room {r_id}, replacing bot '{bot_p['name']}'")
                                send_room_info_update(room)
                                
                                # 替換機器人後滿 2 人自動開局
                                if len(room["players"]) == 2:
                                    room["status"] = "PLAYING"
                                    for p in room["players"]:
                                        if not p["is_bot"]:
                                            opp_of_p = [x for x in room["players"] if x["name"] != p["name"]][0]
                                            send_to_player(p, {
                                                "action": "GAME_START",
                                                "opponent_name": opp_of_p["name"]
                                            })
                                    print(f"[Server] E-Card room {r_id} automatically started game after bot replacement.")
                                    
                                joined = True
                                break
                    else:
                        # RPS 無人數上限，直接加入
                        room["players"].append({"name": name, "is_bot": False, "socket": client_sock, "role": None})
                        print(f"[Server] Player '{name}' joined Room {r_id}")
                        send_room_info_update(room)
                        joined = True
                        break
            
            if not joined:
                # 找不到就自創
                r_id = get_unique_room_id()
                new_room = {
                    "room_id": r_id,
                    "game_type": game_type,
                    "status": "LOBBY",
                    "host": name,
                    "players": [{"name": name, "is_bot": False, "socket": client_sock, "role": None}],
                    "bots_count": 0,
                    "game_state": {
                        "host_card": None,
                        "client_card": None,
                        "wins_host": 0,
                        "wins_client": 0,
                        "host_role": None,
                        "client_role": None,
                        "bot_hand": []
                    }
                }
                GAME_ROOMS[r_id] = new_room
                print(f"[Server] No matching lobby room. Created Room {r_id} for '{name}'")
                send_room_info_update(new_room)
            return

    current_room = None
    my_player = None
    with rooms_lock:
        for r_id, room in GAME_ROOMS.items():
            for p in room["players"]:
                if not p["is_bot"] and p["socket"] == client_sock:
                    current_room = room
                    my_player = p
                    break
            if current_room:
                break

    if not current_room:
        return

    if action == "ADD_BOT":
        if current_room["host"] != my_player["name"]:
            send_to_player(my_player, {"action": "error", "message": "非房主無法新增機器人"})
            return
        limit = 4 if current_room["game_type"] == "rps" else 2
        if len(current_room["players"]) >= limit:
            send_to_player(my_player, {"action": "error", "message": f"房間人數已達上限 ({limit}人)"})
            return
        current_room["bots_count"] += 1
        bot_name = f"BOT_{current_room['bots_count']}"
        current_room["players"].append({"name": bot_name, "is_bot": True, "socket": None, "role": None})
        print(f"[Server] Added {bot_name} to Room {current_room['room_id']}")
        send_room_info_update(current_room)
        return

    elif action == "REMOVE_BOT":
        if current_room["host"] != my_player["name"]:
            send_to_player(my_player, {"action": "error", "message": "非房主無法移除機器人"})
            return
        bot_to_remove = None
        for p in reversed(current_room["players"]):
            if p["is_bot"]:
                bot_to_remove = p
                break
        if bot_to_remove:
            current_room["players"].remove(bot_to_remove)
            current_room["bots_count"] = max(0, current_room["bots_count"] - 1)
            print(f"[Server] Removed {bot_to_remove['name']} from Room {current_room['room_id']}")
            send_room_info_update(current_room)
        else:
            send_to_player(my_player, {"action": "error", "message": "房間內無機器人可移除"})
        return

    elif action == "START_GAME_REQ":
        if current_room["host"] != my_player["name"]:
            send_to_player(my_player, {"action": "error", "message": "非房主無法啟動遊戲"})
            return
        
        # 開始遊戲要求：E-Card 剛好 2 人，RPS 至少 2 人
        req_len = 2
        if current_room["game_type"] == "rps":
            if len(current_room["players"]) < 2:
                send_to_player(my_player, {"action": "error", "message": "房間必須至少有 2 人才能開始遊戲"})
                return
        else:
            if len(current_room["players"]) != 2:
                send_to_player(my_player, {"action": "error", "message": "房間必須剛好滿 2 人才能開始遊戲"})
                return
                
        current_room["status"] = "PLAYING"
        
        # 廣播 GAME_START 給所有玩家，並附帶對手列表
        for p in current_room["players"]:
            if not p["is_bot"]:
                opponents_names = [x["name"] for x in current_room["players"] if x["name"] != p["name"]]
                send_to_player(p, {
                    "action": "GAME_START",
                    "opponents": opponents_names
                })
        print(f"[Server] Game started in Room {current_room['room_id']}")
        return

    # 5. E-Card 專屬邏輯 (select_role, play_card等保持原樣)
    elif action == "select_role":
        role = msg.get("role")
        g_state = current_room["game_state"]
        my_player["role"] = role
        opp = [p for p in current_room["players"] if p["name"] != my_player["name"]][0]
        
        if opp["is_bot"]:
            opp["role"] = "Slave" if role == "Emperor" else "Emperor"
            g_state["host_role"] = role if my_player["name"] == current_room["host"] else opp["role"]
            g_state["client_role"] = opp["role"] if my_player["name"] == current_room["host"] else role
            if opp["role"] == "Emperor":
                g_state["bot_hand"] = ["Emperor", "Citizen", "Citizen", "Citizen", "Citizen"]
            else:
                g_state["bot_hand"] = ["Slave", "Citizen", "Citizen", "Citizen", "Citizen"]
            send_to_player(my_player, {"action": "game_start", "role": role})
        else:
            if not opp["role"]:
                opp["role"] = "Slave" if role == "Emperor" else "Emperor"
                g_state["host_role"] = role if my_player["name"] == current_room["host"] else opp["role"]
                g_state["client_role"] = opp["role"] if my_player["name"] == current_room["host"] else role
                send_to_player(my_player, {"action": "game_start", "role": role})
                send_to_player(opp, {"action": "game_start", "role": opp["role"]})
            else:
                send_to_player(my_player, {"action": "game_start", "role": role})

    elif action in ("sync_hand", "hover_card"):
        opp = [p for p in current_room["players"] if p["name"] != my_player["name"]][0]
        if not opp["is_bot"]:
            send_to_player(opp, msg)

    elif action == "play_card" and current_room["game_type"] == "ecard":
        g_state = current_room["game_state"]
        opp = [p for p in current_room["players"] if p["name"] != my_player["name"]][0]
        is_host = (my_player["name"] == current_room["host"])
        if is_host:
            g_state["host_card"] = msg
        else:
            g_state["client_card"] = msg
            
        if opp["is_bot"]:
            bot_hand = g_state["bot_hand"]
            if bot_hand:
                bot_card_type = random.choice(bot_hand)
                bot_hand.remove(bot_card_type)
                bot_card_index = random.randint(0, len(bot_hand))
                bot_card_id = 999
                
                bot_msg = {
                    "action": "play_card",
                    "card_type": bot_card_type,
                    "card_id": bot_card_id,
                    "index": bot_card_index
                }
                g_state["client_card"] = bot_msg
                send_to_player(my_player, {
                    "action": "opponent_has_played",
                    "index": bot_card_index
                })
                send_to_player(my_player, {
                    "action": "opponent_played",
                    "card_type": bot_card_type,
                    "card_id": bot_card_id,
                    "index": bot_card_index
                })
                winner, reason = evaluate_ecard(g_state["host_role"], g_state["host_card"]["card_type"], bot_card_type)
                if winner != "TIE":
                    if winner == "host":
                        g_state["wins_host"] += 1
                        winner_str = "Player"
                        wins_player = g_state["wins_host"]
                        wins_cpu = g_state["wins_client"]
                        reason_str = f"【勝利】{reason}"
                    else:
                        g_state["wins_client"] += 1
                        winner_str = "CPU"
                        wins_player = g_state["wins_host"]
                        wins_cpu = g_state["wins_client"]
                        reason_str = f"【失敗】{reason}"
                    send_to_player(my_player, {
                        "action": "round_result",
                        "winner": winner_str,
                        "reason": reason_str,
                        "wins_player": wins_player,
                        "wins_cpu": wins_cpu
                    })
                g_state["host_card"] = None
                g_state["client_card"] = None
        else:
            send_to_player(opp, {
                "action": "opponent_has_played",
                "index": msg.get("index")
            })
            if g_state["host_card"] and g_state["client_card"]:
                hc = g_state["host_card"]
                cc = g_state["client_card"]
                send_to_player(my_player if is_host else opp, {
                    "action": "opponent_played",
                    "card_type": cc["card_type"],
                    "card_id": cc["card_id"],
                    "index": cc["index"]
                })
                send_to_player(opp if is_host else my_player, {
                    "action": "opponent_played",
                    "card_type": hc["card_type"],
                    "card_id": hc["card_id"],
                    "index": hc["index"]
                })
                winner, reason = evaluate_ecard(g_state["host_role"], hc["card_type"], cc["card_type"])
                if winner != "TIE":
                    if winner == "host":
                        g_state["wins_host"] += 1
                        winner_str_host = "Player"
                        winner_str_client = "CPU"
                        reason_host = f"【勝利】{reason}"
                        reason_client = f"【失敗】{reason}"
                    else:
                        g_state["wins_client"] += 1
                        winner_str_host = "CPU"
                        winner_str_client = "Player"
                        reason_host = f"【失敗】{reason}"
                        reason_client = f"【勝利】{reason}"
                    send_to_player(my_player if is_host else opp, {
                        "action": "round_result",
                        "winner": winner_str_host,
                        "reason": reason_host,
                        "wins_player": g_state["wins_host"],
                        "wins_cpu": g_state["wins_client"]
                    })
                    send_to_player(opp if is_host else my_player, {
                        "action": "round_result",
                        "winner": winner_str_client,
                        "reason": reason_client,
                        "wins_player": g_state["wins_client"],
                        "wins_cpu": g_state["wins_host"]
                    })
                g_state["host_card"] = None
                g_state["client_card"] = None

    # 6. 多玩家指令處理
    else:
        # 6.1 精準轉發至 target 玩家 (例如 interact_req, interact_resp, trade_xxx)
        target = msg.get("target")
        if target:
            send_to_player_by_name(current_room, target, msg)
        else:
            # 6.2 廣播給房間內除了自己以外的所有人類玩家 (例如 sync_pos 座標同步)
            broadcast_to_room(current_room, msg, exclude_sock=client_sock)

def client_thread(conn, addr):
    print(f"[Server] New connection from {addr}")
    recv_buffer = ""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            recv_buffer += data.decode('utf-8')
            while '\n' in recv_buffer:
                line, recv_buffer = recv_buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    process_message(conn, msg)
                except Exception as e:
                    print(f"[Server] Error parsing JSON line from {addr}: {e}")
    except Exception as e:
        print(f"[Server] Socket connection error with {addr}: {e}")
    finally:
        conn.close()
        handle_client_disconnect(conn)
        print(f"[Server] Closed connection with {addr}")

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind((HOST, PORT))
        server_sock.listen(10)
        print(f"[Server] E-Game Central Server started on {HOST}:{PORT}")
    except Exception as e:
        print(f"[Server] Failed to bind to {HOST}:{PORT}: {e}")
        return
        
    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("[Server] Server shutting down.")
    finally:
        server_sock.close()

if __name__ == "__main__":
    main()
