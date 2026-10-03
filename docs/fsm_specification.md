# Game State Machine (FSM) Specification: 1v1 Texas Hold'em

## 1. State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> LOBBY_WAIT : Server Boots

    LOBBY_WAIT --> GAME_START : Player 2 Joins
    GAME_START --> PRE_FLOP : Deal 2 Cards & Assign Roles

    state Betting_Phase {
        [*] --> P1_TURN
        P1_TURN --> P2_TURN : Valid Move (Check, Bet)
        P2_TURN --> P1_TURN : Valid Move (Raise)
        P2_TURN --> EVALUATE_ROUND : Valid Move (Call, Fold)
        P1_TURN --> EVALUATE_ROUND : Valid Move (Call, Fold)
        
        P1_TURN --> P1_TURN : ERROR (Invalid Bet / Out of Turn)
        P2_TURN --> P2_TURN : ERROR (Invalid Bet / Out of Turn)
    }

    PRE_FLOP --> Betting_Phase
    Betting_Phase --> FLOP : Round Complete (No Fold)
    FLOP --> Betting_Phase
    Betting_Phase --> TURN : Round Complete (No Fold)
    TURN --> Betting_Phase
    Betting_Phase --> RIVER : Round Complete (No Fold)
    RIVER --> Betting_Phase
    
    Betting_Phase --> SHOWDOWN : All Betting Complete (No Fold)
    Betting_Phase --> GAME_OVER : Fold Detected
    
    SHOWDOWN --> GAME_OVER : Determine Winner
    GAME_OVER --> [*]

    LOBBY_WAIT --> DISCONNECT_FORFEIT : TCP EOF / Reset
    Betting_Phase --> DISCONNECT_FORFEIT : TCP EOF / Reset
    DISCONNECT_FORFEIT --> GAME_OVER : Remaining Player Wins Default
