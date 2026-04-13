#!/usr/bin/env python3
"""cmux Auto-Respond 控制面板"""

import json
import os
import re
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

PLIST = os.path.expanduser("~/Library/LaunchAgents/com.luke.cmux-monitor.plist")
SCRIPT = os.path.expanduser("~/.local/bin/cmux-auto-respond.sh")
LOG = "/tmp/cmux-auto-respond.log"
CONFIG = os.path.expanduser("~/.local/bin/cmux-monitor-config.json")

FONT_NORMAL = ("", 15)
FONT_BTN = ("", 14)
FONT_LOG = ("Menlo", 13)
FONT_STATUS = ("", 20)
FONT_ENTRY = ("", 14)

DEFAULT_CONFIG = {
    "interval": 10,
    "rules": [
        {"trigger": "Do you want to create/edit", "response": "1", "enabled": True},
        {"trigger": "繼續嗎 / 要不要 / 是否", "response": "繼續", "enabled": True},
        {"trigger": "其他問句 (？/嗎/呢)", "response": "繼續去爬文進化", "enabled": True},
        {"trigger": "Rating prompt", "response": "3", "enabled": True},
        {"trigger": "閒置（做完沒事做）", "response": "去爬文進化", "enabled": True},
        {"trigger": "Context ≥ 30%", "response": "Session 輪替", "enabled": True},
    ],
    "memory_prompt": "把目前的進度、正在做什麼、下一步要做什麼，全部記到 memory。記好後告訴我。",
    "continue_prompt": "繼續之前的動作",
}


def load_config():
    if os.path.exists(CONFIG):
        with open(CONFIG) as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg):
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def is_running():
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True, stderr=subprocess.DEVNULL)
        return "com.luke.cmux-monitor" in out
    except Exception:
        return False


def start_daemon():
    subprocess.run(["launchctl", "load", PLIST], capture_output=True)


def stop_daemon():
    subprocess.run(["launchctl", "unload", PLIST], capture_output=True)


def read_log(n=50):
    try:
        with open(LOG) as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except FileNotFoundError:
        return "(尚無 log)"


def get_state():
    try:
        with open("/tmp/cmux-auto-respond-state") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "normal"


def update_interval(new_interval):
    try:
        with open(PLIST) as f:
            content = f.read()
        content = re.sub(
            r"<key>StartInterval</key>\s*<integer>\d+</integer>",
            f"<key>StartInterval</key>\n    <integer>{new_interval}</integer>",
            content,
        )
        with open(PLIST, "w") as f:
            f.write(content)
        was_running = is_running()
        if was_running:
            stop_daemon()
            start_daemon()
        return True
    except Exception as e:
        messagebox.showerror("Error", str(e))
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("cmux Auto-Respond 控制面板")
        self.root.geometry("800x960")
        self.root.resizable(False, False)
        self.config = load_config()

        # === Status Frame ===
        status_frame = ttk.LabelFrame(root, text="  狀態  ", padding=12)
        status_frame.pack(fill="x", padx=12, pady=(12, 6))

        self.status_label = ttk.Label(status_frame, text="", font=FONT_STATUS)
        self.status_label.pack(side="left")

        self.state_label = ttk.Label(status_frame, text="", font=FONT_NORMAL, foreground="gray")
        self.state_label.pack(side="left", padx=(20, 0))

        # Use ttk.Button with custom style for proper macOS rendering
        style = ttk.Style()
        style.configure("Stop.TButton", font=FONT_BTN)
        style.configure("Start.TButton", font=FONT_BTN)
        self.toggle_btn = ttk.Button(
            status_frame, command=self.toggle, style="Stop.TButton", width=8
        )
        self.toggle_btn.pack(side="right")

        # === Interval Frame ===
        interval_frame = ttk.LabelFrame(root, text="  檢查頻率  ", padding=12)
        interval_frame.pack(fill="x", padx=12, pady=6)

        ttk.Label(interval_frame, text="每", font=FONT_NORMAL).pack(side="left")
        self.interval_var = tk.StringVar(value=str(self.config.get("interval", 10)))
        self.interval_entry = tk.Spinbox(
            interval_frame,
            from_=5,
            to=120,
            width=5,
            textvariable=self.interval_var,
            font=FONT_NORMAL,
        )
        self.interval_entry.pack(side="left", padx=8)
        ttk.Label(interval_frame, text="秒檢查一次", font=FONT_NORMAL).pack(side="left")
        ttk.Button(interval_frame, text="套用", command=self.apply_interval, width=6).pack(
            side="right"
        )

        # === Rules Frame (all responses editable) ===
        rules_frame = ttk.LabelFrame(root, text="  自動回覆規則（回覆可自由修改）  ", padding=12)
        rules_frame.pack(fill="x", padx=12, pady=6)

        self.rule_vars = []
        self.response_vars = []
        for i, rule in enumerate(self.config["rules"]):
            enabled_var = tk.BooleanVar(value=rule["enabled"])
            response_var = tk.StringVar(value=rule["response"])
            self.rule_vars.append(enabled_var)
            self.response_vars.append(response_var)

            frame = ttk.Frame(rules_frame)
            frame.pack(fill="x", pady=4)

            cb = ttk.Checkbutton(frame, variable=enabled_var, command=self.save_rules)
            cb.pack(side="left")

            ttk.Label(frame, text=f"{rule['trigger']}  →", font=FONT_NORMAL).pack(
                side="left", padx=(8, 4)
            )

            entry = tk.Entry(frame, textvariable=response_var, font=FONT_ENTRY, width=18)
            entry.pack(side="left", padx=4)
            entry.bind("<FocusOut>", lambda e: self.save_rules())
            entry.bind("<Return>", lambda e: self.save_rules())

        # Save button for rules
        ttk.Button(rules_frame, text="儲存規則", command=self.save_rules, width=10).pack(
            anchor="e", pady=(6, 0)
        )

        # === Session Rotation Prompts ===
        rotation_frame = ttk.LabelFrame(root, text="  Session 輪替用語  ", padding=12)
        rotation_frame.pack(fill="x", padx=12, pady=6)

        ttk.Label(rotation_frame, text="記憶指令：", font=FONT_NORMAL).pack(anchor="w")
        self.memory_prompt_var = tk.StringVar(
            value=self.config.get("memory_prompt", DEFAULT_CONFIG["memory_prompt"])
        )
        tk.Entry(
            rotation_frame, textvariable=self.memory_prompt_var, font=FONT_ENTRY, width=60
        ).pack(fill="x", pady=(2, 8))

        ttk.Label(rotation_frame, text="繼續指令：", font=FONT_NORMAL).pack(anchor="w")
        self.continue_prompt_var = tk.StringVar(
            value=self.config.get("continue_prompt", DEFAULT_CONFIG["continue_prompt"])
        )
        tk.Entry(
            rotation_frame, textvariable=self.continue_prompt_var, font=FONT_ENTRY, width=60
        ).pack(fill="x", pady=(2, 4))

        ttk.Button(rotation_frame, text="儲存", command=self.save_prompts, width=8).pack(
            anchor="e", pady=(6, 0)
        )

        # === Auto-Tuner Frame ===
        tuner_frame = ttk.LabelFrame(root, text="  自動調參  ", padding=12)
        tuner_frame.pack(fill="x", padx=12, pady=6)

        self.tuner_label = ttk.Label(tuner_frame, text="", font=FONT_NORMAL)
        self.tuner_label.pack(anchor="w")

        # === Log Frame ===
        log_frame = ttk.LabelFrame(root, text="  最近紀錄  ", padding=12)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=6, font=FONT_LOG, state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(log_frame)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="重新整理", command=self.refresh_log, width=10).pack(
            side="left"
        )
        ttk.Button(btn_frame, text="清除 Log", command=self.clear_log, width=10).pack(side="right")

        self.refresh_status()
        self.refresh_log()
        self.auto_refresh()

    def auto_refresh(self):
        self.refresh_status()
        self.refresh_log()
        self.refresh_tuner()
        self.root.after(5000, self.auto_refresh)

    def refresh_status(self):
        running = is_running()
        state = get_state()
        state_labels = {
            "normal": "正常監控",
            "waiting_memory_save": "等待存 Memory...",
            "waiting_shell": "等待 Shell...",
            "waiting_claude_start": "等待新 Claude...",
        }
        self.state_label.config(text=f"[ {state_labels.get(state, state)} ]")

        if running:
            self.status_label.config(text="● 運行中", foreground="green")
            self.toggle_btn.config(text="⏹ 停止")
        else:
            self.status_label.config(text="○ 已停止", foreground="red")
            self.toggle_btn.config(text="▶ 啟動")

    def toggle(self):
        if is_running():
            stop_daemon()
        else:
            start_daemon()
        self.root.after(500, self.refresh_status)

    def apply_interval(self):
        try:
            val = int(self.interval_var.get())
            if val < 5:
                val = 5
            self.config["interval"] = val
            save_config(self.config)
            update_interval(val)
            messagebox.showinfo("OK", f"已設為每 {val} 秒檢查一次")
        except ValueError:
            messagebox.showerror("Error", "請輸入數字")

    def save_rules(self):
        for i, (enabled_var, response_var) in enumerate(zip(self.rule_vars, self.response_vars)):
            self.config["rules"][i]["enabled"] = enabled_var.get()
            self.config["rules"][i]["response"] = response_var.get()
        save_config(self.config)

    def save_prompts(self):
        self.config["memory_prompt"] = self.memory_prompt_var.get()
        self.config["continue_prompt"] = self.continue_prompt_var.get()
        save_config(self.config)
        messagebox.showinfo("OK", "已儲存")

    def refresh_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", read_log())
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def refresh_tuner(self):
        try:
            import subprocess

            result = subprocess.run(
                ["python3", os.path.expanduser("~/.local/bin/cmux-auto-tuner.py"), "status"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            data = json.loads(result.stdout)
            threshold = data.get("current_threshold", "?")
            sessions = data.get("total_sessions", 0)
            adjustments = data.get("adjustments", 0)
            avg_tpm = data.get("avg_tokens_per_min", "—")
            text = (
                f"門檻: {threshold}%  |  已輪替: {sessions} 次  |"
                f"  調參: {adjustments} 次  |  平均: {avg_tpm} tok/min"
            )
            self.tuner_label.config(text=text)
        except Exception:
            self.tuner_label.config(text="尚無調參數據")

    def clear_log(self):
        try:
            open(LOG, "w").close()
            self.refresh_log()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
