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
    "pot_size": 0,
    "community_cards": [],
    "p1_chips": 1000,
    "p2_chips": 1000,
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
                        # Register first player and tell them to wait
                        connected_clients[client_sock] = "P1"
                        send_message(client_sock, {"msg_type": "LOBBY_WAIT"})
                        print("[FSM] P1 connected. Waiting for opponent...")
                        
                    elif len(connected_clients) == 1:
                        # Register second player and initialize the game
                        connected_clients[client_sock] = "P2"
                        print("[FSM] P2 connected. Starting game...")
                        
                        # Send GAME_START with role assignments and dummy hole cards
                        for sock, role in connected_clients.items():
                            send_message(sock, {
                                "msg_type": "GAME_START",
                                "role": role,
                                "hole_cards": ["As", "Kh"] if role == "P1" else ["Qc", "Qd"]
                            })
                            
                        # Broadcast the initial board state to both clients
                        for sock in connected_clients.keys():
                            send_message(sock, game_state)
                            
                elif msg_type == "MOVE":
                    sender_role = connected_clients.get(client_sock)
                    payload = message.get("payload", {})
                    action = payload.get("action", "FOLD")
                    amount = int(payload.get("amount", 0))
                    
                    print(f"[FSM] Received {action} {amount} from {sender_role}")
                    
                    # Mutate shared state based on the move
                    if action in ["CALL", "RAISE"]:
                        game_state["pot_size"] += amount
                        if sender_role == "P1":
                            game_state["p1_chips"] -= amount
                        else:
                            game_state["p2_chips"] -= amount
                            
                    # Toggle the active turn
                    game_state["active_turn"] = "P2" if sender_role == "P1" else "P1"
                    
                    # Broadcast updated state to unblock the next player's UI
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