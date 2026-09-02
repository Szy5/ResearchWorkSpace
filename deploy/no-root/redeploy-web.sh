#!/usr/bin/env bash
# 重启 Paper-Wiki Web：杀掉旧进程 →（可选）重建前端 → 在 8080 拉起 → 日志写入 paper-wiki-web.log
#
# 用法（在任意目录执行均可）：
#   ./deploy/no-root/redeploy-web.sh
#
# 常用环境变量：
#   PAPER_WIKI_HOME   项目根目录，默认取本脚本所在仓库根
#   PAPER_WIKI_BIN    paper-wiki 可执行文件，默认 conda env paper-wiki
#   PAPER_WIKI_HOST   监听地址，默认 0.0.0.0（本机 + 局域网都能访问）
#   PAPER_WIKI_PORT   端口，默认 8080
#   PAPER_WIKI_LOG    日志文件，默认 $PAPER_WIKI_HOME/paper-wiki-web.log
#   SKIP_FRONTEND=1   跳过 npm run build
#   SKIP_INSTALL=1    跳过 pip install -e .
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PAPER_WIKI_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
CONDA_BIN="${HOME}/miniconda3/envs/paper-wiki/bin/paper-wiki"
PAPER_WIKI_BIN="${PAPER_WIKI_BIN:-}"
if [[ -z "$PAPER_WIKI_BIN" ]]; then
  if [[ -x "$CONDA_BIN" ]]; then
    PAPER_WIKI_BIN="$CONDA_BIN"
  elif [[ -x "$PROJECT_DIR/.venv/bin/paper-wiki" ]]; then
    PAPER_WIKI_BIN="$PROJECT_DIR/.venv/bin/paper-wiki"
  elif command -v paper-wiki >/dev/null 2>&1; then
    PAPER_WIKI_BIN="$(command -v paper-wiki)"
  else
    echo "找不到 paper-wiki 可执行文件，请设置 PAPER_WIKI_BIN" >&2
    exit 1
  fi
fi

HOST="${PAPER_WIKI_HOST:-0.0.0.0}"
PORT="${PAPER_WIKI_PORT:-8080}"
LOG_FILE="${PAPER_WIKI_LOG:-$PROJECT_DIR/paper-wiki-web.log}"
PID_FILE="${PAPER_WIKI_PID:-$PROJECT_DIR/paper-wiki-web.pid}"
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

cd "$PROJECT_DIR"

log() {
  echo "[$(date '+%F %T')] $*"
}

kill_existing() {
  log "停止已有 paper-wiki web / run-web 进程..."
  # 先杀掉常驻循环，否则会在 5 秒内把 web 再拉起来。
  pkill -f "$PROJECT_DIR/deploy/no-root/run-web.sh" 2>/dev/null || true
  pkill -f "deploy/no-root/run-web.sh" 2>/dev/null || true
  pkill -f "paper-wiki web" 2>/dev/null || true
  # 兼容旧启动方式：直接 uvicorn / python -m
  pkill -f "uvicorn paper_wiki.web.app:app" 2>/dev/null || true

  for _ in $(seq 1 20); do
    if ! pgrep -f "paper-wiki web" >/dev/null 2>&1 \
      && ! ss -lntp 2>/dev/null | grep -q ":${PORT} "; then
      break
    fi
    sleep 0.5
  done

  if pgrep -f "paper-wiki web" >/dev/null 2>&1; then
    log "仍有残留进程，发送 SIGKILL..."
    pkill -9 -f "paper-wiki web" 2>/dev/null || true
    sleep 1
  fi

  if ss -lntp 2>/dev/null | grep -q ":${PORT} "; then
    log "警告：端口 ${PORT} 仍被占用，请手动检查："
    ss -lntp 2>/dev/null | grep ":${PORT} " || true
    exit 1
  fi

  rm -f "$PID_FILE"
  log "旧进程已清理"
}

rebuild_frontend() {
  if [[ "$SKIP_FRONTEND" == "1" ]]; then
    log "跳过前端构建（SKIP_FRONTEND=1）"
    return
  fi
  if [[ ! -d "$PROJECT_DIR/web/frontend" ]]; then
    log "未找到 web/frontend，跳过前端构建"
    return
  fi
  log "构建前端..."
  (
    cd "$PROJECT_DIR/web/frontend"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
    npm run build
  )
  log "前端构建完成 → web/frontend/dist/"
}

reinstall_package() {
  if [[ "$SKIP_INSTALL" == "1" ]]; then
    log "跳过 pip install -e .（SKIP_INSTALL=1）"
    return
  fi
  local python_bin
  python_bin="$(dirname "$PAPER_WIKI_BIN")/python"
  if [[ ! -x "$python_bin" ]]; then
    python_bin="python3"
  fi
  log "刷新本地包安装：$python_bin -m pip install -e ."
  "$python_bin" -m pip install --no-build-isolation -e "$PROJECT_DIR" >/tmp/paper-wiki-redeploy-pip.log 2>&1 \
    || {
      log "pip install 失败，详见 /tmp/paper-wiki-redeploy-pip.log"
      tail -n 40 /tmp/paper-wiki-redeploy-pip.log >&2 || true
      exit 1
    }
}

start_server() {
  mkdir -p "$(dirname "$LOG_FILE")"
  log "启动 paper-wiki web on ${HOST}:${PORT}"
  echo "[$(date '+%F %T')] redeploy starting paper-wiki web on ${HOST}:${PORT}" >> "$LOG_FILE"

  nohup "$PAPER_WIKI_BIN" web --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  log "已后台启动 pid=$pid，日志 → $LOG_FILE"

  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1 \
      || curl -fsS "http://127.0.0.1:${PORT}/openapi.json" >/dev/null 2>&1; then
      log "健康检查通过：http://127.0.0.1:${PORT}"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      log "进程已退出，请查看日志尾部："
      tail -n 40 "$LOG_FILE" >&2 || true
      exit 1
    fi
    sleep 0.5
  done

  log "启动超时，进程仍在跑但健康检查未通过。最近日志："
  tail -n 40 "$LOG_FILE" >&2 || true
  exit 1
}

log "项目目录：$PROJECT_DIR"
log "可执行文件：$PAPER_WIKI_BIN"
kill_existing
reinstall_package
rebuild_frontend
start_server
log "部署完成。查看日志：tail -f $LOG_FILE"
