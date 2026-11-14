import argparse
import socket
import threading
import struct
import json
import sys

# Sprint 2 Concurrency & FSM State (Shared Memory)
game_lock = threading.Lock()
connected_clients = {}
game_state = {
    "msg_type": "STATE_UPDATE",
    "phase": "PRE_FLOP",
    "pot_size": 0,
    "community_cards": [],
    "p1_chips": 1000,
    "p2_chips": 1000,
    "p1_bet": 0,             # Tracks P1's bet for the current street
    "p2_bet": 0,             # Tracks P2's bet for the current street
    "current_bet": 0,        # The highest bet to match
    "actions_this_round": 0, # Ensures both players get a chance to act
    "active_turn": "P1"
}

def send_message(sock, message_dict):
    """Sprint 1 Protocol: Serialize JSON and prepend 4-byte length header."""
    payload_bytes = json.dumps(message_dict).encode("utf-8")
    header = struct.pack("!I", len(payload_bytes))
    sock.sendall(header + payload_bytes)

def recv_exact(sock, n_bytes):
    """Sprint 1 Protocol: Receive exactly n_bytes from the TCP stream."""
    buf = bytearray()
    while len(buf) < n_bytes:
        chunk = sock.recv(n_bytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)

def handle_client(client_sock, addr):
    """Sprint 2 Option A: Dedicated worker thread per client."""
    try:
        while True:
            # 1. Read the 4-byte Big-Endian length prefix
            header = recv_exact(client_sock, 4)
            if not header:
                break # Clean TCP FIN
            
            payload_len = struct.unpack("!I", header)[0]
            
            # 2. Read exact JSON payload
            payload_bytes = recv_exact(client_sock, payload_len)
            message = json.loads(payload_bytes.decode("utf-8"))
            
            # 3. Enter Critical Section for FSM transitions
            with game_lock:
                msg_type = message.get("msg_type")
                
                if msg_type == "CONNECT":
                    if len(connected_clients) == 0:
                        connected_clients[client_sock] = "P1"
                        send_message(client_sock, {"msg_type": "LOBBY_WAIT"})
                        print("[FSM] P1 connected. Waiting for opponent...")
                        
                    elif len(connected_clients) == 1:
                        connected_clients[client_sock] = "P2"
                        print("[FSM] P2 connected. Starting game...")
                        
                        # Send GAME_START with roles
                        for sock, role in connected_clients.items():
                            send_message(sock, {
                                "msg_type": "GAME_START",
                                "role": role,
                                "hole_cards": ["As", "Kh"] if role == "P1" else ["Qc", "Qd"]
                            })
                            
                        # Broadcast the initial global board state
                        for sock in connected_clients.keys():
                            send_message(sock, game_state)
                            
                elif msg_type == "MOVE":
                    sender_role = connected_clients.get(client_sock)
                    payload = message.get("payload", {})
                    action = payload.get("action", "FOLD").upper()
                    amount = int(payload.get("amount", 0))
                    
                    print(f"[FSM] Received {action} {amount} from {sender_role}")
                    
                    # 1. Handle FOLD (Terminal State)
                    if action == "FOLD":
                        winner = "P2" if sender_role == "P1" else "P1"
                        for sock in connected_clients.keys():
                            try:
                                send_message(sock, {
                                    "msg_type": "GAME_OVER",
                                    "winner": winner,
                                    "reason": f"{sender_role} folded."
                                })
                            except:
                                pass
                        continue # Skips sending a standard STATE_UPDATE
                        
                    # 2. Extract player-specific state keys
                    my_bet_key = "p1_bet" if sender_role == "P1" else "p2_bet"
                    my_chip_key = "p1_chips" if sender_role == "P1" else "p2_chips"
                    
                    # 3. Validate and Apply Bets
                    if action == "CHECK":
                        if game_state[my_bet_key] < game_state["current_bet"]:
                            send_message(client_sock, {"msg_type": "ERROR", "reason": "Cannot check. You must call the raise."})
                            continue 
                            
                    elif action == "CALL":
                        call_amount = game_state["current_bet"] - game_state[my_bet_key]
                        game_state[my_chip_key] -= call_amount
                        game_state[my_bet_key] += call_amount
                        game_state["pot_size"] += call_amount
                        
                    elif action == "RAISE":
                        new_total_bet = game_state["current_bet"] + amount
                        cost = new_total_bet - game_state[my_bet_key]
                        game_state[my_chip_key] -= cost
                        game_state[my_bet_key] = new_total_bet
                        game_state["current_bet"] = new_total_bet
                        game_state["pot_size"] += cost

                    game_state["actions_this_round"] += 1
                    
                    # 4. Check for Phase Advancement
                    if game_state["actions_this_round"] >= 2 and game_state["p1_bet"] == game_state["p2_bet"]:
                        if game_state["phase"] == "PRE_FLOP":
                            game_state["phase"] = "FLOP"
                            game_state["community_cards"] = ["Ah", "Kd", "7c"]
                        elif game_state["phase"] == "FLOP":
                            game_state["phase"] = "TURN"
                            game_state["community_cards"].append("2s")
                        elif game_state["phase"] == "TURN":
                            game_state["phase"] = "RIVER"
                            game_state["community_cards"].append("9h")
                            
                        # Reset street variables for the next betting round
                        game_state["actions_this_round"] = 0
                        game_state["p1_bet"] = 0
                        game_state["p2_bet"] = 0
                        game_state["current_bet"] = 0
                            
                    # 5. Toggle active turn
                    game_state["active_turn"] = "P2" if sender_role == "P1" else "P1"
                    
                    # 6. Broadcast updated state
                    for sock in connected_clients.keys():
                        send_message(sock, game_state)
                    
    except (ConnectionResetError, BrokenPipeError):
        print(f"[!] Abrupt disconnect from {addr}")
    finally:
        with game_lock:
            if client_sock in connected_clients:
                disconnected_role = connected_clients.pop(client_sock)
                print(f"[FSM] {disconnected_role} disconnected.")
                for sock in connected_clients.keys():
                    try:
                        send_message(sock, {
                            "msg_type": "GAME_OVER",
                            "winner": "P1" if disconnected_role == "P2" else "P2",
                            "reason": "DISCONNECT_FORFEIT"
                        })
                    except:
                        pass
            client_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Texas Hold'em Authoritative Server")
    parser.add_argument("-p", "--port", type=int, required=True, help="Listening port")
    args = parser.parse_args()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", args.port))
    server_sock.listen(2)
    
    print(f"[*] Server listening on 0.0.0.0:{args.port}...")
    
    while True:
        client_sock, addr = server_sock.accept()
        print(f"[*] Accepted connection from {addr}")
        threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()