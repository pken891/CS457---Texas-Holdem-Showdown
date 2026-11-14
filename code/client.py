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
    print("\n" + "="*40)
    print(f"Pot: {state_dict.get('pot_size', 0)} | Community Cards: {state_dict.get('community_cards', [])}")
    print(f"P1 Chips: {state_dict.get('p1_chips', 0)} | P2 Chips: {state_dict.get('p2_chips', 0)}")
    print("="*40)
    
    if state_dict.get('active_turn') == my_role:
        return True # Indicates it is this client's turn
    else:
        print(">>> Waiting for opponent...")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Texas Hold'em Client")
    parser.add_argument("-i", "--hostname", required=True, help="Server DNS hostname")
    parser.add_argument("-p", "--port", type=int, required=True, help="Server port")
    args = parser.parse_args()

    # Mandatory Graceful DNS Resolution Handling
    try:
        server_ip = socket.gethostbyname(args.hostname)
        print(f"[*] Resolved {args.hostname} to {server_ip}")
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
        print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
        sys.exit(1)

    # TCP Socket Initialization & Connection
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_sock.connect((server_ip, args.port))
        
        # Example initial CONNECT payload matching Sprint 1 schema
        send_message(client_sock, {"msg_type": "CONNECT", "player_id": "pk_1"})
        
        my_role = None

        # Main game loop blocking on exact TCP frames
        while True:
            # 1. Read the 4-byte length header
            header = recv_exact(client_sock, 4)
            if not header:
                print("\n[!] Server disconnected.")
                break
                
            payload_len = struct.unpack("!I", header)[0]
            
            # 2. Read exact JSON payload
            payload_bytes = recv_exact(client_sock, payload_len)
            message = json.loads(payload_bytes.decode("utf-8"))
            
            # 3. Handle message types
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
                    # Parse user input to extract action and optional bet amount
                    raw_input = input(">>> YOUR TURN! Enter action (FOLD, CHECK, CALL, RAISE [amount]): ").strip().split()
                    action = raw_input[0].upper() if raw_input else "FOLD"
                    amount = int(raw_input[1]) if len(raw_input) > 1 and raw_input[1].isdigit() else 0
                    
                    send_message(client_sock, {
                        "msg_type": "MOVE",
                        "player_id": "pk_1", # Update this if using dynamic usernames later
                        "payload": {"action": action, "amount": amount}
                    })
            elif msg_type == "ERROR":
                print(f"\n[ERROR] {message.get('reason')}")
            elif msg_type == "GAME_OVER":
                print(f"\n[!] GAME OVER. Winner: {message.get('winner')} - {message.get('reason')}")
                break
                
    except ConnectionRefusedError:
        print("[ERROR] Connection refused. Is the server running?")
        sys.exit(1)
    finally:
        client_sock.close()