# Application Protocol Blueprint: 1v1 Texas Hold'em

## 1. Transport Layer & Serialization
*   **Transport Protocol**: TCP
*   **Serialization Format**: Structured JSON (UTF-8 encoded)

## 2. Framing Mechanism: Length-Prefixed Binary Header
TCP is a byte-stream protocol. To prevent coalescing or fragmentation of JSON messages, this application uses a Fixed-Width Length-Prefixed Header.

*   **Rule**: Every JSON payload is preceded by a 4-byte unsigned integer in Network Byte Order (Big-Endian `!I`).
*   **Sender Mechanism**: Calculate the exact byte length of the UTF-8 encoded JSON payload. Pack this integer into a 4-byte header using `struct.pack('!I', length)`. Send the header, followed immediately by the payload.
*   **Receiver Mechanism**: Call a loop-based exact receive function to read exactly 4 bytes. Unpack this header to derive payload length `N`. Call the exact receive function again to read exactly `N` bytes. Decode as UTF-8 and parse as JSON.

### Concrete Wire Stream Example
Two continuous messages arriving in a single TCP chunk:
`[0x0000002F] {"msg_type":"CONNECT","player_id":"Player1"} [0x00000045] {"msg_type":"MOVE","payload":{"action":"CALL","amount":50}}`

## 3. Application Message Types

### 3.1 CONNECT
*   **Direction**: Client -> Server
*   **Purpose**: Initial connection request and alias registration.
*   **Schema**:
    ```json
    {
      "msg_type": "CONNECT",
      "player_id": "string (alphanumeric)"
    }
    ```

### 3.2 LOBBY_WAIT
*   **Direction**: Server -> Client
*   **Purpose**: Instructs the first connected client to block until Player 2 joins.
*   **Schema**:
    ```json
    {
      "msg_type": "LOBBY_WAIT",
      "message": "string"
    }
    ```

### 3.3 GAME_START
*   **Direction**: Server -> Clients
*   **Purpose**: Notifies clients the game has begun, assigns roles, and deals hole cards.
*   **Schema**:
    ```json
    {
      "msg_type": "GAME_START",
      "role": "string (P1 or P2)",
      "hole_cards": ["string (e.g., 'AH')", "string (e.g., 'KS')"]
    }
    ```

### 3.4 MOVE
*   **Direction**: Client -> Server
*   **Purpose**: Active player submits their betting phase action.
*   **Schema**:
    ```json
    {
      "msg_type": "MOVE",
      "player_id": "string",
      "payload": {
        "action": "string (FOLD, CHECK, CALL, RAISE)",
        "amount": "integer (0 if non-betting action)"
      }
    }
    ```

### 3.5 STATE_UPDATE
*   **Direction**: Server -> Clients
*   **Purpose**: Broadcasts the current board state and indicates whose turn it is.
*   **Schema**:
    ```json
    {
      "msg_type": "STATE_UPDATE",
      "active_turn": "string (P1 or P2)",
      "pot_size": "integer",
      "community_cards": ["string", "string", "string", "string", "string"],
      "p1_chips": "integer",
      "p2_chips": "integer"
    }
    ```

### 3.6 ERROR
*   **Direction**: Server -> Client
*   **Purpose**: Notifies a client of an invalid move (e.g., out of turn, invalid bet amount).
*   **Schema**:
    ```json
    {
      "msg_type": "ERROR",
      "reason": "string"
    }
    ```

### 3.7 DISCONNECT
*   **Direction**: Client -> Server
*   **Purpose**: Graceful application-layer exit.
*   **Schema**:
    ```json
    {
      "msg_type": "DISCONNECT",
      "player_id": "string"
    }
    ```

### 3.8 GAME_OVER
*   **Direction**: Server -> Clients
*   **Purpose**: Declares the final outcome of the game.
*   **Schema**:
    ```json
    {
      "msg_type": "GAME_OVER",
      "winner": "string (P1, P2, or DRAW)",
      "reason": "string (SHOWDOWN, FORFEIT, DISCONNECT)"
    }
    ```

## 4. Connection Termination & Lifecycle Management
Connections will be terminated explicitly and handled predictably by the server state engine to prevent infinite loops and dangling sockets.

*   **Graceful TCP Teardown (TCP FIN / EOF)**: The receiver explicitly checks for an End-Of-File condition. If the exact receive function calls `sock.recv()` and it returns `b""` (0 bytes), the application
*   acknowledges the remote peer cleanly closed the connection. The server triggers a `DISCONNECT_FORFEIT` event to award the win to the remaining player.
*   **Abrupt Termination (Network Drop / TCP RST)**: The application wraps socket reads/writes in `try/except` blocks targeting `ConnectionResetError`, `BrokenPipeError`, and `TimeoutError`. If caught,
*   the connection is treated as dead, the socket is destroyed, and the remaining player is awarded a win by forfeit
