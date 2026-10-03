```markdown
# AI Prompting & Constraint Strategy

## 1. Objective
To enforce strict adherence to the custom length-prefixed JSON protocol when generating Python socket serialization and parsing code using AI assistants.

## 2. System Prompts & Constraints Used

### Prompt 1: Receiver Framing implementation
**Prompt given to AI:**
> "Write a Python TCP socket receiver function named `recv_exact(sock, n_bytes)` that reads exactly `n_bytes` from the stream. Then, write a parser that uses `recv_exact` to first read a 
  4-byte unsigned Big-Endian integer (`!I`) header using the `struct` module. This header represents the payload length. Pass that length back into `recv_exact` to read the payload,
  then decode it as UTF-8 JSON. If `recv_exact` ever returns an empty byte string `b""`, raise a custom `ClientDisconnected` exception. Do not use newline delimiters or arbitrary buffer sizes."

**Justification:**
This prompt explicitly prevents the AI from generating standard `sock.recv(1024)` loops that are vulnerable to TCP coalescing and fragmentation. It forces the use of the `struct` module for the 
exact 4-byte Big-Endian length prefix defined in the protocol blueprint, and explicitly dictates the EOF (`b""`) handling behavior to manage clean disconnects.

### Prompt 2: Sender Serialization Implementation
**Prompt given to AI:**
> "Write a Python function `send_message(sock, message_dict)` that serializes a dictionary to JSON, encodes it to UTF-8, and calculates its byte length. Pack the length into 
  a 4-byte unsigned Big-Endian integer header. Send the header followed immediately by the payload using `sock.sendall()`. Ensure no newline characters are appended to the end of the payload."

**Justification:**
This prevents the AI from mixing framing rules (like accidentally adding a `\n` to a length-prefixed payload). It enforces `sendall()` to guarantee the entire buffer is pushed to the OS network stack.
