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

def render_ui(state_dict):
    """CLI User Interface for game boards and score summaries."""
    print("\n" + "="*40)
    print(f"Pot: {state_dict.get('pot_size')} | Community Cards: {state_dict.get('community_cards')}")
    print(f"Your Chips: {state_dict.get('p1_chips')} | Opponent Chips: {state_dict.get('p2_chips')}")
    print("="*40)
    if state_dict.get('active_turn') == "P1":
        print(">>> YOUR TURN! Enter action (FOLD, CHECK, CALL, RAISE): ")
    else:
        print(">>> Waiting for Player 2...")

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
        
        # Main game loop (would include recv_exact logic to receive STATE_UPDATEs)
        # ...
        
    except ConnectionRefusedError:
        print("[ERROR] Connection refused. Is the server running?")
        sys.exit(1)