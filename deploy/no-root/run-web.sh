#!/usr/bin/env bash
# 无 root/无 systemd --user 场景下的兜底常驻脚本：
# 死循环拉起 paper-wiki web，崩了自动重启，日志写文件方便事后查看。
# 用法：在项目根目录下 nohup deploy/no-root/run-web.sh > /dev/null 2>&1 & disown
# 配合 crontab -e 里加一行 @reboot 达到重启服务器后自动拉起（见 DEPLOY.md）。
set -u

# 默认假设 venv 布局；用 conda 环境的话必须显式传 PAPER_WIKI_BIN=/path/to/envs/paper-wiki/bin/paper-wiki，
# 否则会去找不存在的 .venv/bin/paper-wiki。
PROJECT_DIR="${PAPER_WIKI_HOME:-$HOME/paper-wiki}"
PAPER_WIKI_BIN="${PAPER_WIKI_BIN:-$PROJECT_DIR/.venv/bin/paper-wiki}"
HOST="${PAPER_WIKI_HOST:-10.109.252.89}"
PORT="${PAPER_WIKI_PORT:-8080}"
LOG_FILE="${PAPER_WIKI_LOG:-$PROJECT_DIR/paper-wiki-web.log}"

cd "$PROJECT_DIR" || exit 1

while true; do
    echo "[$(date '+%F %T')] starting paper-wiki web on $HOST:$PORT" >> "$LOG_FILE"
    "$PAPER_WIKI_BIN" web --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1
    echo "[$(date '+%F %T')] paper-wiki web exited with code $?, restarting in 5s" >> "$LOG_FILE"
    sleep 5
done
