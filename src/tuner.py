#!/usr/bin/env python3
"""
cmux Auto-Tuner — 自動優化 session 輪替門檻值

追蹤每次 session 的 token 消耗，找到最省的 context % 門檻。
由 daemon 腳本在每次輪替時呼叫。
"""
import json
import os
import time

STATS_FILE = "/tmp/cmux-auto-tuner-stats.json"
CONFIG_FILE = os.path.expanduser("~/.local/bin/cmux-monitor-config.json")
SCRIPT_FILE = os.path.expanduser("~/.local/bin/cmux-auto-respond.sh")

MIN_THRESHOLD = 20
MAX_THRESHOLD = 60
ADJUST_AFTER = 3  # 每 N 次輪替後分析一次


def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            return json.load(f)
    return {
        "sessions": [],
        "current_session": None,
        "current_threshold": 30,
        "best_threshold": 30,
        "best_efficiency": None,
        "adjustment_history": [],
    }


def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def update_script_threshold(new_threshold):
    """Update CTX_THRESHOLD in the daemon script."""
    try:
        with open(SCRIPT_FILE) as f:
            content = f.read()
        import re
        content = re.sub(
            r'CTX_THRESHOLD=\d+',
            f'CTX_THRESHOLD={new_threshold}',
            content,
        )
        with open(SCRIPT_FILE, "w") as f:
            f.write(content)
    except Exception:
        pass


def start_session(ctx_pct, tokens_total):
    """Called when a new session starts (after rotation)."""
    stats = load_stats()
    stats["current_session"] = {
        "start_time": time.time(),
        "start_tokens": tokens_total,
        "start_ctx_pct": ctx_pct,
        "threshold_used": stats["current_threshold"],
    }
    save_stats(stats)


def end_session(ctx_pct, tokens_total, actions_count):
    """Called when a session is about to rotate (context hit threshold)."""
    stats = load_stats()

    if stats["current_session"] is None:
        # No start recorded, just record what we can
        stats["current_session"] = {
            "start_time": time.time() - 300,
            "start_tokens": max(0, tokens_total - 50000),
            "start_ctx_pct": 0,
            "threshold_used": stats["current_threshold"],
        }

    session = stats["current_session"]
    duration = time.time() - session["start_time"]
    tokens_used = tokens_total - session["start_tokens"]

    record = {
        "timestamp": time.time(),
        "threshold": session["threshold_used"],
        "end_ctx_pct": ctx_pct,
        "duration_sec": round(duration),
        "tokens_used": tokens_used,
        "actions": actions_count,
        "tokens_per_action": round(tokens_used / max(actions_count, 1)),
        "tokens_per_minute": round(tokens_used / max(duration / 60, 1)),
    }
    stats["sessions"].append(record)

    # Keep last 20 sessions
    stats["sessions"] = stats["sessions"][-20:]

    # Analyze and maybe adjust
    if len(stats["sessions"]) >= ADJUST_AFTER:
        new_threshold = analyze_and_adjust(stats)
        if new_threshold != stats["current_threshold"]:
            stats["adjustment_history"].append({
                "timestamp": time.time(),
                "old": stats["current_threshold"],
                "new": new_threshold,
                "reason": f"Based on {len(stats['sessions'])} sessions",
            })
            stats["current_threshold"] = new_threshold
            update_script_threshold(new_threshold)

            # Update GUI config too
            cfg = load_config()
            for rule in cfg.get("rules", []):
                if "Context" in rule.get("trigger", ""):
                    rule["trigger"] = f"Context ≥ {new_threshold}%"
            save_config(cfg)

    stats["current_session"] = None
    save_stats(stats)
    return stats["current_threshold"]


def analyze_and_adjust(stats):
    """
    分析歷史 sessions，找最佳門檻。

    策略：
    - tokens_per_minute 越低越好（同樣時間花更少 token）
    - 但太低的門檻 = 太頻繁輪替 = 輪替成本高
    - 找 tokens_per_minute 最低的門檻值，加減 5% 微調
    """
    sessions = stats["sessions"]
    if len(sessions) < ADJUST_AFTER:
        return stats["current_threshold"]

    # Group by threshold
    by_threshold = {}
    for s in sessions:
        t = s["threshold"]
        if t not in by_threshold:
            by_threshold[t] = []
        by_threshold[t].append(s)

    # Calculate average efficiency for each threshold
    efficiencies = {}
    for threshold, sess_list in by_threshold.items():
        avg_tpm = sum(s["tokens_per_minute"] for s in sess_list) / len(sess_list)
        avg_tpa = sum(s["tokens_per_action"] for s in sess_list) / len(sess_list)
        # Combined score: lower is better
        # Weight tokens_per_minute more (70%) vs tokens_per_action (30%)
        efficiencies[threshold] = {
            "avg_tpm": avg_tpm,
            "avg_tpa": avg_tpa,
            "sessions": len(sess_list),
            "score": avg_tpm,  # Primary metric
        }

    current = stats["current_threshold"]

    # If we only have data for one threshold, try exploring
    if len(efficiencies) == 1:
        current_score = list(efficiencies.values())[0]["score"]

        # Record best known
        if stats["best_efficiency"] is None or current_score < stats["best_efficiency"]:
            stats["best_efficiency"] = current_score
            stats["best_threshold"] = current

        # Explore: try +5 or -5 alternately
        explored = [h["new"] for h in stats.get("adjustment_history", [])]
        if current + 5 <= MAX_THRESHOLD and (current + 5) not in explored:
            return current + 5
        elif current - 5 >= MIN_THRESHOLD and (current - 5) not in explored:
            return current - 5
        else:
            return stats["best_threshold"]

    # Multiple thresholds tested — pick the best
    best_threshold = min(efficiencies, key=lambda t: efficiencies[t]["score"])

    # Confidence check: need at least 2 sessions at best threshold
    if efficiencies[best_threshold]["sessions"] < 2:
        return current  # Not enough data, keep current

    # Update best
    best_score = efficiencies[best_threshold]["score"]
    if stats["best_efficiency"] is None or best_score < stats["best_efficiency"]:
        stats["best_efficiency"] = best_score
        stats["best_threshold"] = best_threshold

    return best_threshold


def get_status():
    """Return current tuner status for display."""
    stats = load_stats()
    sessions = stats["sessions"]

    status = {
        "current_threshold": stats["current_threshold"],
        "best_threshold": stats["best_threshold"],
        "total_sessions": len(sessions),
        "adjustments": len(stats.get("adjustment_history", [])),
    }

    if sessions:
        last = sessions[-1]
        status["last_tokens_per_min"] = last["tokens_per_minute"]
        status["last_duration"] = last["duration_sec"]

        avg_tpm = sum(s["tokens_per_minute"] for s in sessions) / len(sessions)
        status["avg_tokens_per_min"] = round(avg_tpm)

    return status


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(json.dumps(get_status(), indent=2, ensure_ascii=False))
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "start" and len(sys.argv) >= 4:
        start_session(int(sys.argv[2]), int(sys.argv[3]))
        print("Session started")
    elif cmd == "end" and len(sys.argv) >= 5:
        new_t = end_session(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
        print(f"Session ended. Threshold: {new_t}%")
    elif cmd == "status":
        print(json.dumps(get_status(), indent=2, ensure_ascii=False))
    else:
        print("Usage: auto-tuner.py [start <ctx%> <tokens> | end <ctx%> <tokens> <actions> | status]")
