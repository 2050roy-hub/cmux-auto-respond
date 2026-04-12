#!/bin/bash
# cmux auto-respond daemon v8 — session 輪替 + 自動調參
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

LOG="/tmp/cmux-auto-respond.log"
CD="/tmp/cmux-auto-respond-cooldown"
STATE="/tmp/cmux-auto-respond-state"
ACTIONS="/tmp/cmux-auto-respond-actions"
SURF="surface:9"
WS="workspace:1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CMUX="/Applications/cmux.app/Contents/Resources/bin/cmux"
TUNER="${SCRIPT_DIR}/tuner.py"
CTX_THRESHOLD=30

[ -f "$CD" ] || echo "0" > "$CD"
[ -f "$STATE" ] || echo "normal" > "$STATE"
[ -f "$ACTIONS" ] || echo "0" > "$ACTIONS"
now=$(date +%s)
last=$(cat "$CD" 2>/dev/null || echo 0)
[ $((now - last)) -lt 10 ] && exit 0

# Read screen
screen=$("$CMUX" read-screen --workspace "$WS" --surface "$SURF" 2>/dev/null) || exit 0
[ -z "$screen" ] && exit 0

tail15=$(echo "$screen" | tail -15)
state=$(cat "$STATE" 2>/dev/null || echo "normal")

# Extract tokens from status bar (RTK shows total like 1010.5K or 1125.3K)
extract_tokens() {
    local tk=$(echo "$tail15" | grep -oE '[0-9]+\.[0-9]+K' | tail -1 | tr -d 'K')
    if [ -n "$tk" ]; then
        echo "$tk" | awk '{printf "%d", $1 * 1000}'
    else
        echo "0"
    fi
}

# Extract context % from status bar
extract_ctx() {
    echo "$tail15" | grep -oE '━[━┄]*[[:space:]]*[0-9]+%' | grep -oE '[0-9]+' | head -1
}

increment_actions() {
    local a=$(cat "$ACTIONS" 2>/dev/null || echo 0)
    echo $((a + 1)) > "$ACTIONS"
}

send_msg() {
    echo "[$(date)] [$SURF] $1 → $2" >> "$LOG"
    "$CMUX" send --workspace "$WS" --surface "$SURF" "$2" 2>/dev/null
    "$CMUX" send-key --workspace "$WS" --surface "$SURF" Enter 2>/dev/null
    echo "$now" > "$CD"
    increment_actions
}

# ============================================================
# State machine for session rotation
# ============================================================

# --- State: waiting_memory_save ---
if [ "$state" = "waiting_memory_save" ]; then
    if echo "$tail15" | grep -qE '[·✳✶✽✢✻] .+…'; then
        exit 0
    fi
    if echo "$tail15" | grep -q '❯'; then
        echo "[$(date)] [$SURF] Memory saved. Exiting session..." >> "$LOG"
        send_msg "exit session" "/exit"
        echo "waiting_shell" > "$STATE"
        exit 0
    fi
    exit 0
fi

# --- State: waiting_shell ---
if [ "$state" = "waiting_shell" ]; then
    if echo "$tail15" | grep -qE '^\$|^❯|^%|Luke@'; then
        echo "[$(date)] [$SURF] Shell ready. Starting new Claude..." >> "$LOG"
        send_msg "start claude" "claude"
        echo "waiting_claude_start" > "$STATE"
        exit 0
    fi
    if echo "$tail15" | grep -q '❯'; then
        send_msg "retry exit" "/exit"
    fi
    exit 0
fi

# --- State: waiting_claude_start ---
if [ "$state" = "waiting_claude_start" ]; then
    if echo "$tail15" | grep -q '❯'; then
        if echo "$tail15" | grep -qE 'Opus|Sonnet|Haiku|context'; then
            echo "[$(date)] [$SURF] New Claude ready! Sending continue..." >> "$LOG"

            # Tell tuner: new session started
            ctx=$(extract_ctx)
            tokens=$(extract_tokens)
            python3 "$TUNER" start "${ctx:-0}" "${tokens:-0}" 2>/dev/null

            send_msg "continue" "繼續之前的動作"
            echo "0" > "$ACTIONS"
            echo "normal" > "$STATE"
            exit 0
        fi
    fi
    exit 0
fi

# ============================================================
# Normal state
# ============================================================

# === Case 1: File create/edit prompt ===
if echo "$tail15" | grep -q 'Do you want to'; then
    send_msg "create/edit" "1"
    exit 0
fi

# === Case 2: 正在工作中 → 不動 ===
if echo "$tail15" | grep -qE '[·✳✶✽✢✻⏺] .+…'; then
    exit 0
fi

# === 不在工作中，檢查是否等待輸入 ===
if ! echo "$tail15" | grep -q '❯'; then
    exit 0
fi

# === Case 3: Rating prompt ===
if echo "$tail15" | grep -q 'How is Claude doing'; then
    send_msg "rating" "3"
    exit 0
fi

# === Case 4: 繼續嗎 ===
if echo "$screen" | tail -30 | grep -qE '繼續|continue|要不要|是否|接著|下一'; then
    send_msg "繼續類" "繼續"
    exit 0
fi

# === Case 5: Context ≥ threshold → session 輪替 + tuner ===
ctx_pct=$(extract_ctx)
if [ -n "$ctx_pct" ] && [ "$ctx_pct" -ge "$CTX_THRESHOLD" ] 2>/dev/null; then
    tokens=$(extract_tokens)
    actions=$(cat "$ACTIONS" 2>/dev/null || echo 0)

    # Tell tuner: session ending
    tuner_result=$(python3 "$TUNER" end "${ctx_pct}" "${tokens}" "${actions}" 2>/dev/null)
    new_threshold=$(echo "$tuner_result" | grep -oE '[0-9]+' | head -1)

    if [ -n "$new_threshold" ] && [ "$new_threshold" -ne "$CTX_THRESHOLD" ] 2>/dev/null; then
        echo "[$(date)] [$SURF] Auto-tuner adjusted threshold: ${CTX_THRESHOLD}% → ${new_threshold}%" >> "$LOG"
        # Update this script's threshold for next run
        sed -i '' "s/CTX_THRESHOLD=${CTX_THRESHOLD}/CTX_THRESHOLD=${new_threshold}/" "$0"
    fi

    echo "[$(date)] [$SURF] Context ${ctx_pct}% (≥${CTX_THRESHOLD}%) — session rotation! [actions=${actions}, tokens=${tokens}]" >> "$LOG"
    send_msg "save memory" "把目前的進度、正在做什麼、下一步要做什麼，全部記到 memory。記好後告訴我。"
    echo "waiting_memory_save" > "$STATE"
    exit 0
fi

# === Case 6: 其他問句 ===
if echo "$screen" | tail -30 | grep -qE '？|\?|嗎|呢'; then
    send_msg "問句" "繼續去爬文進化"
    exit 0
fi

# === Case 7: Fallback — 閒置 ===
send_msg "idle" "去爬文進化"
exit 0
