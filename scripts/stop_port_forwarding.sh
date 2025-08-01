#!/bin/bash
echo "🛑 停止所有端口转发..."

if [ -d ".pids" ]; then
    for pidfile in .pids/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "✅ 停止进程 $pid"
            fi
            rm "$pidfile"
        fi
    done
    rmdir .pids 2>/dev/null
fi

echo "🎉 所有端口转发已停止"
