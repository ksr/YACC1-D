; Simple Monitor Program for YACC1-2020
; Supports: 
; 1) Display a memory location (D command)
; 2) Modify a memory location (M command)
; 3) Display 256 bytes of memory block (B command)
; Uses support functions:
; - getc: gets character from keyboard, returns in R7
; - putc: outputs character in R7 to the screen

; Constants
CR: EQU  0x0D       ; Carriage return
LF: EQU 0x0A       ; Line feed
SPACE:  EQU 0x20    ; Space character
CMD_DISP: EQU 0x44 ; 'D' - Display memory location
CMD_MOD: EQU 0x4D  ; 'M' - Modify memory location
CMD_BLOCK:  EQU 0x42 ; 'B' - Display memory block

; Main program starts here
START:
    ; Print welcome message
    LDR R1, MSG_WELCOME    ; F1 [MSG_HI] [MSG_LO]
    JSR PRINT_STRING       ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    
MAIN_LOOP:
    ; Print prompt
    LDR R1, MSG_PROMPT     ; F1 [PROMPT_HI] [PROMPT_LO]
    JSR PRINT_STRING       ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    
    ; Get command
    JSR GETC_TO_CHAR       ; 04 [GETC_HI] [GETC_LO]
    MVRLA R7              ; 27  ; Get input character
    MVAT                  ; 0B  ; Store in tmp
    
    ; Echo the character
    JSR PUTC_CHAR         ; 04 [PUTC_HI] [PUTC_LO]
    
    ; Print newline
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
    ; Compare with commands
    MVTA                  ; 0C  ; Restore character to accumulator
    
    ; Compare with 'D' (Display)
    LDTI CMD_DISP         ; 0D 44
    BREQ HANDLE_DISPLAY   ; A8 [DISPLAY_HI] [DISPLAY_LO]
    
    ; Compare with 'M' (Modify)
    LDTI CMD_MOD         ; 0D 4D
    BREQ HANDLE_MODIFY   ; A8 [MODIFY_HI] [MODIFY_LO]
    
    ; Compare with 'B' (Block display)
    LDTI CMD_BLOCK       ; 0D 42
    BREQ HANDLE_BLOCK    ; A8 [BLOCK_HI] [BLOCK_LO]
    
    ; Unknown command
    LDR R1, MSG_UNKNOWN   ; F1 [UNKNOWN_HI] [UNKNOWN_LO]
    JSR PRINT_STRING      ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    BR MAIN_LOOP          ; A0 [MAIN_LOOP_HI] [MAIN_LOOP_LO]

; ---- Handle Display Memory Location ----
HANDLE_DISPLAY:
    ; Print message
    LDR R1, MSG_ADDR_REQ  ; F1 [ADDR_REQ_HI] [ADDR_REQ_LO]
    JSR PRINT_STRING      ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    
    ; Get address
    JSR GET_HEX_WORD      ; 04 [GET_HEX_WORD_HI] [GET_HEX_WORD_LO]
    
    ; R0 now contains the address to display
    MOVRR R0, R3          ; 0F 03  ; Copy address to R3
    
    ; Print newline
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
    ; Print address
    MOVRR R3, R0          ; 0F 30  ; Copy address to R0
    JSR PRINT_HEX_WORD    ; 04 [PRINT_HEX_WORD_HI] [PRINT_HEX_WORD_LO]
    
    ; Print separator
    LDAI SPACE            ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI ':'             ; 0E 3A
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI SPACE           ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    
    ; Load and display byte from memory
    LDAVR R3             ; 43  ; Load byte at address in R3
    MVARL R0             ; 30  ; Store in R0 low
    LDAI 0               ; 0E 00
    MVARH R0             ; 38  ; Clear R0 high
    JSR PRINT_HEX_BYTE   ; 04 [PRINT_HEX_BYTE_HI] [PRINT_HEX_BYTE_LO]
    
    ; Print newline
    JSR PRINT_NEWLINE    ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
    BR MAIN_LOOP         ; A0 [MAIN_LOOP_HI] [MAIN_LOOP_LO]

; ---- Handle Modify Memory Location ----
HANDLE_MODIFY:
    ; Print message
    LDR R1, MSG_ADDR_REQ  ; F1 [ADDR_REQ_HI] [ADDR_REQ_LO]
    JSR PRINT_STRING      ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    
    ; Get address
    JSR GET_HEX_WORD      ; 04 [GET_HEX_WORD_HI] [GET_HEX_WORD_LO]
    
    ; R0 now contains the address to modify
    MOVRR R0, R3          ; 0F 03  ; Copy address to R3
    
    ; Print current value
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
    ; Print address
    MOVRR R3, R0          ; 0F 30  ; Copy address to R0
    JSR PRINT_HEX_WORD    ; 04 [PRINT_HEX_WORD_HI] [PRINT_HEX_WORD_LO]
    
    ; Print separator
    LDAI SPACE            ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI ':'             ; 0E 3A
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI SPACE           ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    
    ; Load and display current byte
    LDAVR R3             ; 43  ; Load byte at address in R3
    MVARL R0             ; 30  ; Store in R0 low
    LDAI 0               ; 0E 00
    MVARH R0             ; 38  ; Clear R0 high
    JSR PRINT_HEX_BYTE   ; 04 [PRINT_HEX_BYTE_HI] [PRINT_HEX_BYTE_LO]
    
    ; Print separator for new value
    LDAI SPACE            ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI '-'             ; 0E 2D
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI '>'             ; 0E 3E
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI SPACE           ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    
    ; Get new value
    JSR GET_HEX_BYTE     ; 04 [GET_HEX_BYTE_HI] [GET_HEX_BYTE_LO]
    
    ; R0 now contains new byte value
    MVRLA R0             ; 20  ; Load new value to accumulator
    STAVR R3             ; 4B  ; Store at address in R3
    
    ; Print newline
    JSR PRINT_NEWLINE    ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
    BR MAIN_LOOP         ; A0 [MAIN_LOOP_HI] [MAIN_LOOP_LO]

; ---- Handle Block Display ----
HANDLE_BLOCK:
    ; Print message
    LDR R1, MSG_ADDR_REQ  ; F1 [ADDR_REQ_HI] [ADDR_REQ_LO]
    JSR PRINT_STRING      ; 04 [PRINT_STRING_HI] [PRINT_STRING_LO]
    
    ; Get start address
    JSR GET_HEX_WORD      ; 04 [GET_HEX_WORD_HI] [GET_HEX_WORD_LO]
    
    ; R0 now contains start address
    MOVRR R0, R3          ; 0F 03  ; Copy to R3 (current address)
    
    ; Use R4 as line counter (16 bytes per line)
    MVIW R4, 0            ; 1C 00 00
    
    ; Use R5 as byte counter (256 bytes total)
    MVIW R5, 0            ; 1D 00 00
    
    ; Print newline
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]

BLOCK_LOOP:
    ; Check if we need a new line (R4 == 0)
    MVRLA R4              ; 24
    ORI 0                 ; B2 00  ; Test if zero
    BRNZ BLOCK_CONT       ; A2 [BLOCK_CONT_HI] [BLOCK_CONT_LO]
    
    ; New line - print address
    MOVRR R3, R0          ; 0F 30  ; Copy address to R0
    JSR PRINT_HEX_WORD    ; 04 [PRINT_HEX_WORD_HI] [PRINT_HEX_WORD_LO]
    
    ; Print separator
    LDAI SPACE            ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI ':'             ; 0E 3A
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI SPACE           ; 0E 20
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    
BLOCK_CONT:
    ; Display byte at current address
    LDAVR R3              ; 43  ; Load byte at address in R3
    MVARL R0              ; 30  ; Store in R0 low
    LDAI 0                ; 0E 00
    MVARH R0              ; 38  ; Clear R0 high
    JSR PRINT_HEX_BYTE    ; 04 [PRINT_HEX_BYTE_HI] [PRINT_HEX_BYTE_LO]
    
    ; Print space
    LDAI SPACE            ; 0E 20
    MVARL R7              ; 37
    JSR PUTC_CHAR         ; 04 [PUTC_HI] [PUTC_LO]
    
    ; Increment address
    INCR R3               ; 53
    
    ; Increment byte counter
    INCR R5               ; 55
    
    ; Increment and check line counter
    INCR R4               ; 54
    MVRLA R4              ; 24
    LDTI 16               ; 0D 10
    BRNEQ BLOCK_LINE_CONT ; AA [BLOCK_LINE_CONT_HI] [BLOCK_LINE_CONT_LO]
    
    ; End of line - reset line counter and print newline
    MVIW R4, 0            ; 1C 00 00
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]
    
BLOCK_LINE_CONT:
    ; Check if we've displayed 256 bytes
    MVRLA R5              ; 25
    LDTI 0                ; 0D 00
    BRNEQ BLOCK_LOOP      ; AA [BLOCK_LOOP_HI] [BLOCK_LOOP_LO]
    MVRHA R5              ; 2D
    LDTI 1                ; 0D 01
    BRNEQ BLOCK_LOOP      ; AA [BLOCK_LOOP_HI] [BLOCK_LOOP_LO]
    
    ; Done with block display
    JSR PRINT_NEWLINE     ; 04 [NEWLINE_HI] [NEWLINE_LO]
    BR MAIN_LOOP          ; A0 [MAIN_LOOP_HI] [MAIN_LOOP_LO]

; ---- Support Subroutines ----

; Get character from keyboard into R7
GETC_TO_CHAR:
    JSR GETC             ; 04 [SYSTEM_GETC_HI] [SYSTEM_GETC_LO]
    RET                  ; 05

; Output character in R7 to screen
PUTC_CHAR:
    JSR PUTC             ; 04 [SYSTEM_PUTC_HI] [SYSTEM_PUTC_LO]
    RET                  ; 05

; Print newline (CR+LF)
PRINT_NEWLINE:
    PUSHR R7             ; 07
    LDAI CR              ; 0E 0D
    MVARL R7             ; 37
    JSR PUTC_CHAR        ; 04 [PUTC_HI] [PUTC_LO]
    LDAI LF              ; 0E 0A
