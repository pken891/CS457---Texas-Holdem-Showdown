# Sprint 2: Server Concurrency & Game Behavior Architecture
**Project:** Heads-Up Texas Hold'em Showdown (1v1 CLI Network Game)  
**Author:** Peter Kenoian  
**Course:** CS 457 – Computer Networks  
**Target Host:** `server.kenoian.edu` (TCP Port `5000`)  

---

## 1. Server Concurrency Model Selection (Option A: Multi-Threading)

### 1.1 Architectural Overview
The authoritative game server for **Heads-Up Texas Hold'em Showdown** implements **Option A: Multi-Threading** using Python's `threading.Thread` module and standard `socket` primitives. 

Because our Sprint 1 application protocol relies on **4-byte big-endian length-prefixed JSON framing** over TCP streams, a multi-threaded architecture provides clean execution isolation per client. Each connected player is serviced by a dedicated daemon worker thread (`ClientHandlerThread`) that can block safely on socket `recv()` calls while assembling complete length-prefixed frames without stalling the main acceptor loop or delaying the opponent's network I/O.

### 1.2 Thread Topology
The server process consists of **three primary threads** during an active match:
1. **Main Acceptor Thread (`MainThread`):** Binds to `0.0.0.0:5000` (`server.kenoian.edu`), listens for incoming TCP handshakes, enforces the 2-player table capacity limit, initializes shared state structures, and spawns worker threads.
2. **Player 1 Worker Thread (`Thread-Client-1`):** Dedicated to reading length-prefixed JSON frames from Player 1's TCP socket, invoking synchronized state transitions, and handling Player 1 disconnection events.
3. **Player 2 Worker Thread (`Thread-Client-2`):** Dedicated to reading length-prefixed JSON frames from Player 2's TCP socket, invoking synchronized state transitions, and handling Player 2 disconnection events.

---

## 2. Complete Connection Lifecycle

The server manages client connections across four deterministic lifecycle stages:

### Stage 1: Listening Socket Initialization & Client Accept
1. The server creates an IPv4 TCP socket (`socket.AF_INET`, `socket.SOCK_STREAM`) and sets `socket.SO_REUSEADDR = 1` to allow immediate port rebinding upon server restart.
2. The socket binds to `('0.0.0.0', 5000)` and calls `server_sock.listen(5)`.
3. The main loop blocks on `client_sock, client_addr = server_sock.accept()`.
4. Upon accepting a TCP connection:
   * The server acquires `game_lock` and checks the active player count (`len(connected_clients)`).
   * If `len(connected_clients) >= 2`, the server immediately sends a length-prefixed `ERROR` payload (`{"type": "ERROR", "code": "TABLE_FULL", "message": "Match already in progress."}`) and closes `client_sock`.
   * Otherwise, the server spawns a dedicated daemon thread: `threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()`.

### Stage 2: Client Registration & Matchmaking Handshake
1. Inside `handle_client()`, the worker thread waits for the initial 4-byte length header and JSON payload, expecting a `CONNECT` message (`{"type": "CONNECT", "username": "Alice"}`).
2. The worker thread acquires `game_lock` to register the player:
   * Assigns a seat ID (`PLAYER_1` or `PLAYER_2`).
   * Initializes the player's starting chip stack (`1000` chips) and session leaderboard entry in shared memory.
   * Stores the client's socket descriptor in `connected_clients[player_id]`.
3. If only one player is registered (`WAITING_FOR_PLAYER` state), the server sends a `CONNECT_ACK` message informing Player 1 they are waiting for an opponent.
4. When the second player registers, the worker thread handling Player 2 transitions the FSM from `WAITING_FOR_PLAYER` to `PRE_FLOP`, shuffles the authoritative 52-card deck, posts the Small Blind (10 chips) and Big Blind (20 chips), deals 2 private hole cards to each player, and broadcasts the initial customized `STATE_UPDATE` to both clients.

### Stage 3: Active Game Loop Servicing
1. Each worker thread runs a continuous framing loop (`while True:`):
   * Calls `recv_exact(client_sock, 4)` to read the 4-byte unsigned integer length prefix (`!I`).
   * Calls `recv_exact(client_sock, payload_length)` to read the exact UTF-8 JSON bytes.
   * Deserializes the JSON string into a Python dictionary.
2. Upon receiving a `MOVE` request (e.g., `FOLD`, `CHECK`, `CALL`, `RAISE`), the worker thread enters the **Critical Section** (`with game_lock:`):
   * Validates that the match is in an active betting state (`PRE_FLOP`, `FLOP`, `TURN`, `RIVER`).
   * Validates that `game_state.active_turn == player_id`.
   * Validates move legality (e.g., sufficient chips for `RAISE`, valid `CHECK` when current bet is matched).
   * Mutates the shared game state (updates pot, deducts player stack, advances betting street or triggers Showdown, switches `active_turn`).
   * Broadcasts updated state frames to both connected client sockets before releasing `game_lock`.

### Stage 4: Client Socket Teardown (Graceful & Abrupt)
Teardown occurs when a client sends a `QUIT` frame, or when `recv_exact()` returns `None` / raises `ConnectionResetError` or `BrokenPipeError` (indicating TCP `FIN` or `RST`):
1. The worker thread acquires `game_lock` in a `finally:` block.
2. Removes the disconnected player's socket from `connected_clients`.
3. If a hand was actively in progress, the remaining connected player is immediately awarded the current pot and match victory by forfeit.
4. Sends a `GAME_OVER` notification (`reason: "OPPONENT_DISCONNECTED"`) and updated `SCORE_UPDATE` to the surviving client socket.
5. Resets the table state back to `WAITING_FOR_PLAYER` (or closes the room) and calls `client_sock.close()`, terminating the worker thread cleanly.

---

## 3. Thread Safety, Lock Acquisition & State Isolation Strategy

### 3.1 Shared Memory Resources
Because both `Thread-Client-1` and `Thread-Client-2` read and mutate the same poker table instance concurrently, all shared state is encapsulated inside a single `GameState` object protected by a mutual exclusion lock (`self.game_lock = threading.Lock()`).

| Shared Variable | Data Type | Purpose | Race Condition Risk Without Lock |
| :--- | :--- | :--- | :--- |
| `connected_clients` | `dict[str, socket.socket]` | Maps `player_id` to active TCP socket objects | Simultaneous read/write during broadcast while opponent disconnects raises `RuntimeError: dictionary changed size during iteration`. |
| `fsm_state` | `str` | Tracks current phase (`WAITING`, `PRE_FLOP`, `FLOP`, `TURN`, `RIVER`, `SHOWDOWN`) | Simultaneous packet processing could trigger double street advancement (e.g., dealing both Flop and Turn at once). |
| `active_turn` | `str` | Stores `PLAYER_1` or `PLAYER_2` | Out-of-turn action could interleave with valid turn action, allowing double-betting or skipped turns. |
| `deck` | `list[str]` | Server-only list of remaining playing cards | Concurrent `deck.pop()` calls could deal duplicate cards or corrupt deck index. |
| `community_cards` | `list[str]` | Up to 5 shared board cards (`["Ah", "Kd", "7c"]`) | Partial board updates visible to one thread before street transition completes. |
| `pot` & `current_bet` | `int` | Total chips in center pot and highest bet in current street | Classic read-modify-write hazard (`pot += bet`), losing chips if two updates interleave. |
| `player_state` | `dict[str, dict]` | Holds each player's `stack`, `hole_cards`, `street_bet`, and `status` | Inconsistent chip deduction or exposing unmasked hole cards during state serialization. |
| `leaderboard` | `dict[str, dict]` | Tracks `hands_won`, `hands_lost`, `net_chips`, and `bankroll` across rounds | Corrupted cumulative scores at round boundaries. |

### 3.2 Lock Acquisition & Critical Section Pattern
To guarantee strict serialization of state transitions and prevent race conditions, worker threads **never** read or write `GameState` attributes outside of `with self.game_lock:`.

```python
def process_client_message(self, player_id: str, message: dict):
    # Network I/O (reading the frame) happens OUTSIDE the lock so a slow 
    # client connection never blocks the opponent thread.
    
    with self.game_lock:
        # --- START CRITICAL SECTION ---
        # 1. Turn Enforcement Check
        if self.active_turn != player_id:
            self._send_to_client(player_id, {
                "type": "ERROR",
                "code": "OUT_OF_TURN",
                "message": f"Action rejected: It is currently {self.active_turn}'s turn."
            })
            return

        # 2. Move Legality Validation
        is_valid, err_msg = self._validate_betting_action(player_id, message)
        if not is_valid:
            self._send_to_client(player_id, {
                "type": "ERROR",
                "code": "INVALID_MOVE",
                "message": err_msg
            })
            return

        # 3. Authoritative State Mutation
        self._apply_action(player_id, message)

        # 4. Synchronous State & Score Broadcast
        # Executed inside the lock so outbound STATE_UPDATE packets are guaranteed 
        # to be transmitted in the exact chronological order of state transitions.
        self._broadcast_synchronized_state()
        # --- END CRITICAL SECTION ---
```

### 3.3 Deadlock Prevention & Information Hiding (Anti-Cheat Isolation)
1. **Single Coarse-Grained Lock Ordering:** By using a single `threading.Lock()` (`self.game_lock`) for the table state rather than nested per-player locks, circular wait conditions (deadlocks) are mathematically impossible.
2. **Non-Blocking Socket Reads Outside Lock:** Worker threads only acquire `self.game_lock` *after* a full JSON message has been read from the socket buffer. Socket `sendall()` inside the lock is protected by a short socket timeout (`sock.settimeout(2.0)`) so a dead client cannot stall lock release indefinitely.
3. **Per-Client State Masking (Fog of War):** During `_broadcast_synchronized_state()`, the server constructs two distinct JSON payloads while holding the lock. Player 1 receives their own `hole_cards` (`["As", "Kh"]`) while Player 2's hole cards are masked as `["??", "??"]` (and vice versa), preventing packet-sniffing cheats on the client side until the `SHOWDOWN` phase.

---

## 4. Score & Leaderboard Synchronization Design

### 4.1 In-Memory Score & Leaderboard Schema
The server maintains a persistent in-memory `leaderboard` dictionary inside `GameState` that tracks multi-hand session statistics across the lifetime of the match:

```json
{
  "hand_number": 4,
  "players": {
    "PLAYER_1": {
      "username": "Alice",
      "bankroll": 1240,
      "net_profit": 240,
      "hands_won": 3,
      "hands_lost": 1,
      "all_in_wins": 1
    },
    "PLAYER_2": {
      "username": "Bob",
      "bankroll": 760,
      "net_profit": -240,
      "hands_won": 1,
      "hands_lost": 3,
      "all_in_wins": 0
    }
  }
}
```

### 4.2 Round Completion & Synchronous Leaderboard Broadcast Logic
A hand concludes via one of two paths:
1. **Fold Termination:** One player sends `MOVE (action: "FOLD")` during any betting street.
2. **Showdown Termination:** Betting concludes on the `RIVER` (or both players are All-In), triggering the server's 7-card hand evaluator (`evaluate_best_five_card_hand()`).

When either termination condition is reached inside the critical section (`with self.game_lock:`):
1. **Pot Settlement:** The server adds `self.pot` to the winning player's `bankroll` (or splits `self.pot` evenly on a tied hand, awarding any odd chip to the first player after the dealer button).
2. **Leaderboard Mutation:** The server increments `hands_won`, `hands_lost`, and recalculates `net_profit` (`current_bankroll - 1000`) for both players.
3. **Synchronous Broadcast (`ROUND_OVER` / `SCORE_UPDATE`):** While still holding `self.game_lock`, the server iterates through `connected_clients` and transmits a length-prefixed `ROUND_OVER` frame containing:
   * Revealed hole cards for both players (if terminated via Showdown).
   * Hand rank description (e.g., `"Two Pair, Aces and Kings"`).
   * Pot amount awarded and the updated **Leaderboard Table**.
4. **Match Termination or Next Hand Transition:**
   * If either player's `bankroll == 0`, the server immediately broadcasts a `GAME_OVER` frame declaring the final match champion and final leaderboard standings.
   * If both players have chips remaining (`bankroll > 0`), the server increments `hand_number`, rotates the Dealer/Small Blind button, deals the next hand, and broadcasts the new `PRE_FLOP` `STATE_UPDATE` synchronously to both clients.
