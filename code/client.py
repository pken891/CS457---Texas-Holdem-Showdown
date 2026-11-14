import argparse
import socket
import sys
import struct
import json

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

def render_ui(state_dict, my_role):
    """CLI User Interface for game boards and score summaries."""
    print("\n" + "="*50)
    print(f"Phase: {state_dict.get('phase')} | Pot: {state_dict.get('pot_size', 0)}")
    print(f"Community Cards: {state_dict.get('community_cards', [])}")
    print(f"Current Bet to Match: {state_dict.get('current_bet', 0)}")
    print("-" * 50)
    print(f"P1 Chips: {state_dict.get('p1_chips', 0)} | P1 Round Bet: {state_dict.get('p1_bet', 0)}")
    print(f"P2 Chips: {state_dict.get('p2_chips', 0)} | P2 Round Bet: {state_dict.get('p2_bet', 0)}")
    print("="*50)
    
    if state_dict.get('active_turn') == my_role:
        return True
    else:
        print(">>> Waiting for opponent...")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Texas Hold'em Client")
    parser.add_argument("-i", "--hostname", required=True, help="Server DNS hostname")
    parser.add_argument("-p", "--port", type=int, required=True, help="Server port (1024-65535)")
    args = parser.parse_args()

    # Rubric Criterion 1: Validate port numbers (1024-65535)
    if not (1024 <= args.port <= 65535):
        parser.error("Port must be an integer between 1024 and 65535.")

    # Mandatory Graceful DNS Resolution Handling
    try:
        server_ip = socket.gethostbyname(args.hostname)
        print(f"[*] Resolved {args.hostname} to {server_ip}")
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
        print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
        sys.exit(1)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_sock.connect((server_ip, args.port))
        send_message(client_sock, {"msg_type": "CONNECT", "player_id": "pk_1"})
        
        my_role = None

        while True:
            header = recv_exact(client_sock, 4)
            if not header:
                print("\n[!] Server disconnected.")
                break
                
            payload_len = struct.unpack("!I", header)[0]
            payload_bytes = recv_exact(client_sock, payload_len)
            if not payload_bytes:
                print("\n[!] Server disconnected.")
                break
            message = json.loads(payload_bytes.decode("utf-8"))
            
            msg_type = message.get("msg_type")
            
            if msg_type == "LOBBY_WAIT":
                print(">>> Waiting for Player 2...")
            elif msg_type == "GAME_START":
                my_role = message.get("role")
                print(f"\n[!] Game Started! You are: {my_role}")
                print(f"Hole Cards: {message.get('hole_cards')}")
            elif msg_type == "STATE_UPDATE":
                is_my_turn = render_ui(message, my_role)
                if is_my_turn:
                    raw_input = input(">>> YOUR TURN! Enter action (FOLD, CHECK, CALL, RAISE [amount]): ").strip().split()
                    action = raw_input[0].upper() if raw_input else "FOLD"
                    amount = int(raw_input[1]) if len(raw_input) > 1 and raw_input[1].isdigit() else 0
                    
                    send_message(client_sock, {
                        "msg_type": "MOVE",
                        "payload": {"action": action, "amount": amount}
                    })
            elif msg_type == "ERROR":
                print(f"\n[ERROR] {message.get('reason')}")
            elif msg_type == "GAME_OVER":
                print("\n" + "="*50)
                print(f"[!] GAME OVER. Winner: {message.get('winner')}")
                print(f"Reason: {message.get('reason')}")
                print("="*50)
                break
                
    except ConnectionRefusedError:
        print("[ERROR] Connection refused. Is the server running?")
        sys.exit(1)
    finally:
        client_sock.close()