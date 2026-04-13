# SNAPSHOT — cmux-auto-respond
> 最後更新：2026-04-13

## 狀態
- 階段：開發中
- 版本：v1.0（commit 00b4d0f）

## 當前最重要的 3 件事
1. 核心功能（daemon.sh 狀態機 + tuner.py + gui.py）已完成並可安裝，但測試骨架尚未填入真實測試
2. `gui.py` 的 config（`cmux-monitor-config.json`）與 `daemon.sh` 規則尚未完全同步 — 兩套設定並行是已知技術債
3. 改 `src/` 後必須重跑 `./install.sh` 才會生效，容易忘記（daemon 跑的是 `~/.local/bin/` 的複本）

## 上次改動
- 填寫完整 CLAUDE.md 專案指引（架構、重要檔案、指令、注意事項）
- 前次：修復 ruff lint 錯誤（E501 行太長）+ 補 pyproject.toml 和 tests 骨架

## 阻塞項
- `tests/` 只有佔位骨架，尚無真實測試覆蓋 daemon 狀態機邏輯
