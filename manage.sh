#!/usr/bin/env bash
# nightwatcher process manager

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/.nightwatcher.pid"
LOG_FILE="$APP_DIR/nightwatcher.log"
CMD="uv run python -m nightwatcher.main"
PORT=12505

# ── color helpers ──────────────────────────────────────────────────────────────
green()  { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }
red()    { echo -e "\033[31m$*\033[0m"; }

# ── helpers ────────────────────────────────────────────────────────────────────
is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

get_pid() {
  cat "$PID_FILE" 2>/dev/null
}

# ── commands ───────────────────────────────────────────────────────────────────
do_start() {
  if is_running; then
    yellow "Already running  (PID $(get_pid))"
    return 1
  fi
  cd "$APP_DIR"
  nohup $CMD >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 0.5
  if is_running; then
    green "Started  (PID $(get_pid))  → log: $LOG_FILE"
  else
    red "Failed to start — check $LOG_FILE"
    rm -f "$PID_FILE"
    return 1
  fi
}

do_stop() {
  if ! is_running; then
    yellow "Not running"
    return 0
  fi
  local pid
  pid=$(get_pid)
  kill "$pid"
  # wait up to 5 s for graceful exit
  for i in $(seq 1 10); do
    sleep 0.5
    kill -0 "$pid" 2>/dev/null || break
  done
  if kill -0 "$pid" 2>/dev/null; then
    yellow "Still alive after 5s — sending SIGKILL"
    kill -9 "$pid"
  fi
  rm -f "$PID_FILE"
  green "Stopped  (PID $pid)"

  # 等端口真正释放（最多 10 秒），顺手清掉残留占用者
  for i in $(seq 1 20); do
    local port_pids
    port_pids=$(lsof -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null)
    if [ -z "$port_pids" ]; then
      break
    fi
    echo "$port_pids" | while read p; do
      yellow "Port $PORT still held by PID $p — killing"
      kill -9 "$p" 2>/dev/null
    done
    sleep 0.5
  done
  green "Port $PORT is free"
}

do_restart() {
  yellow "Restarting…"
  do_stop
  sleep 0.5
  do_start
}

do_status() {
  if is_running; then
    green "Running  (PID $(get_pid))"
  else
    red "Not running"
  fi
}

do_logs() {
  tail -f "$LOG_FILE"
}

# ── dispatch ───────────────────────────────────────────────────────────────────
case "${1:-}" in
  start)   do_start   ;;
  stop)    do_stop    ;;
  restart) do_restart ;;
  status)  do_status  ;;
  logs)    do_logs    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
