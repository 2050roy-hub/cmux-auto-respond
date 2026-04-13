# CLAUDE.md — cmux-auto-respond

## 專案說明

**一句話**：監控 cmux 終端裡的 Claude Code session，自動回覆提示、輪替 session、並自動調整輪替門檻來省 token。

**詳細描述**：
macOS 背景常駐服務（launchd），每 10 秒讀一次 cmux 指定 surface 的畫面，根據內容自動送出回應：
- 檔案建立提示 → 自動按 `1`
- 繼續類提示 → 自動回「繼續」
- 閒置 → 回「去爬文進化」
- Context 使用率 ≥ 門檻 → 存 memory → `/exit` → 新開 Claude → 繼續

Auto-Tuner 會追蹤每次 session 的 tokens/min，每 3 次輪替後自動微調門檻（20%–60%），讓 token 消耗最小化。

---

## 架構概覽

```
launchd (每 10 秒)
  └─ src/daemon.sh          # 主狀態機：讀畫面 → 判斷 → 送回應
       └─ src/tuner.py      # 分析 session 效率，輸出新門檻
src/gui.py                  # tkinter 控制面板（獨立 .app 運行）
install.sh                  # 安裝到 ~/.local/bin/ + 建 .app bundle
```

**狀態機（STATE file）**：
| 狀態 | 說明 |
|------|------|
| `normal` | 正常監控 |
| `waiting_memory_save` | 已送存記憶指令，等 Claude 完成 |
| `waiting_shell` | 已送 `/exit`，等 shell prompt 出現 |
| `waiting_claude_start` | 已送 `claude`，等新 session 就緒 |

---

## 重要檔案

| 檔案 | 說明 |
|------|------|
| `src/daemon.sh` | 核心邏輯，**第 10-11 行**設定監控的 `SURF` 和 `WS` |
| `src/tuner.py` | 自動調參引擎，也可獨立執行查狀態 |
| `src/gui.py` | tkinter 控制面板，5 秒自動刷新 |
| `src/launchd.plist.template` | launchd 服務範本，install.sh 填入路徑後複製 |
| `install.sh` | 一鍵安裝：複製到 `~/.local/bin/` + 建 app bundle + 啟動 daemon |

**Runtime 檔案**（`/tmp/`）：
- `cmux-auto-respond.log` — 操作記錄
- `cmux-auto-respond-state` — 目前狀態機狀態
- `cmux-auto-respond-cooldown` — 防連發冷卻時間戳
- `cmux-auto-respond-actions` — 本 session 已執行動作數
- `cmux-auto-tuner-stats.json` — tuner 歷史數據

**安裝後檔案**：
- `~/.local/bin/cmux-auto-respond.sh` — daemon（launchd 直接執行這個）
- `~/.local/bin/cmux-auto-tuner.py` — tuner
- `~/Library/LaunchAgents/com.cmux-auto-respond.plist` — launchd 服務定義
- `~/Applications/cmux Monitor.app` — GUI app bundle

---

## 開發指令

```bash
# 安裝（首次或改完 src/ 後重裝）
./install.sh

# 查 daemon 狀態
launchctl list | grep cmux-auto-respond

# 看即時 log
tail -f /tmp/cmux-auto-respond.log

# 手動觸發一次 daemon（測試用）
~/.local/bin/cmux-auto-respond.sh

# 查 tuner 狀態
python3 ~/.local/bin/cmux-auto-tuner.py status

# 開 GUI 控制面板
open ~/Applications/cmux\ Monitor.app
# 或直接跑
python3 src/gui.py

# 停止 / 啟動 daemon
launchctl unload ~/Library/LaunchAgents/com.cmux-auto-respond.plist
launchctl load ~/Library/LaunchAgents/com.cmux-auto-respond.plist

# 完整解除安裝
./uninstall.sh

# Lint
ruff check src/

# 測試
pytest --tb=no -q
```

---

## 設定監控目標

編輯 `src/daemon.sh` 第 10-11 行，再跑 `./install.sh` 重裝：

```bash
SURF="surface:9"    # 要監控的 cmux surface
WS="workspace:1"    # 對應的 workspace
```

找你的 surface 編號：`cmux tree --all`

---

## 注意事項

1. **改 `src/` 後必須重跑 `./install.sh`** — daemon 跑的是 `~/.local/bin/` 裡的複本，不是 `src/` 原始檔
2. **daemon.sh 的 `CTX_THRESHOLD` 會被 tuner 自動修改** — 不要手動 hardcode 這個值，改了下次 tuner 調參會覆蓋
3. **`gui.py` 改的 config 存在 `~/.local/bin/cmux-monitor-config.json`** — 這個 config 目前只影響 GUI 顯示，daemon.sh 的規則是獨立 hardcode 的（兩者尚未完全同步）
4. **tkinter 需要 Python.app 路徑**才能在 macOS 顯示視窗 — install.sh 會自動偵測，直接 `python3 src/gui.py` 如果視窗沒出來，改用 Python.app 路徑執行
5. **僅支援 macOS**（依賴 launchd + cmux + tkinter）
