import argparse
import socket
import threading
import struct
import json
import sys

# Sprint 2 Concurrency & FSM State (Shared Memory)
game_lock = threading.Lock()
connected_clients = {}

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
                # Handle message logic (CONNECT, MOVE, etc.) and state transitions here
                pass 
                
    except (ConnectionResetError, BrokenPipeError):
        print(f"[!] Abrupt disconnect from {addr}")
    finally:
        with game_lock:
            # Handle socket teardown and FSM DISCONNECT_FORFEIT transition
            client_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Texas Hold'em Authoritative Server")
    parser.add_argument("-p", "--port", type=int, required=True, help="Listening port")
    args = parser.parse_args()

    # TCP Socket Initialization & Binding
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", args.port))
    server_sock.listen(2)
    
    print(f"[*] Server listening on 0.0.0.0:{args.port}...")
    
    while True:
        client_sock, addr = server_sock.accept()
        print(f"[*] Accepted connection from {addr}")
        threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True).start()