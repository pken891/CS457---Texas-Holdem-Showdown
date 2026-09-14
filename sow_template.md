# CS 457 Final Project: Statement of Work (Sprint 0)

## 1. Project Information
*   **Target Server Domain Name:** server.kenoian.edu
*   **Programming Language:** Python 3

## 2. Game Selection
*   **Game Name:** Heads-Up (1v1) Texas Hold'em Poker
*   **Game Type:** Turn-based, 1v1 card and betting strategy game.

## 3. Game Mechanics & Rules
*   **Player Turn Mechanics:** 
    *   Both players start with a set amount of chips (e.g., 1000). 
    *   The "Dealer Button" alternates each hand. The player off the button posts the Small Blind; the player on the button posts the Big Blind.
    *   During betting rounds (Pre-flop, Flop, Turn, River), players alternate turns choosing to Fold, Check, Call, or Raise.
    *   The server maintains a standard 52-card deck, securely dealing 2 hidden hole cards to each client and managing the 5 shared community cards.
*   **Victory Conditions:** 
    *   A player wins a single hand if the opponent folds, or if they have the best 5-card hand at the showdown.
    *   Overall game victory is achieved when one player accumulates all the chips, eliminating the opponent.
*   **Draw/Tie Conditions:** 
    *   If both players have the exact same 5-card hand value at the showdown, the pot is split equally ("chopped pot").
