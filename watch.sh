#!/bin/bash
# 游戏运行时守护：发现属性缺失就补上（Wine 会因 USB 端口/枚举变化换新设备 GUID，属性会丢）
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/wine-dualsense-haptics.log"

pgrep -f "Genshin Impact Game/YuanShen.exe" >/dev/null 2>&1 || exit 0

if /usr/bin/python3 "$DIR/fix_dualsense_haptics.py" --check --quiet; then
    exit 0
fi

echo "[$(date '+%F %T')] properties missing, re-applying" >> "$LOG"
/usr/bin/python3 "$DIR/fix_dualsense_haptics.py" --quiet >> "$LOG" 2>&1
