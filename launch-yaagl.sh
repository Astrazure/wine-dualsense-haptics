#!/bin/bash
# 用 Yaagl 启动原神，并在启动前后自动补齐 DualSense 震动属性
# 用完即退，不常驻后台
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/wine-dualsense-haptics.log"
APP="${YAAGL_APP:-Yaagl}"

apply() {
    /usr/bin/python3 "$DIR/fix_dualsense_haptics.py" --quiet >> "$LOG" 2>&1
}

# 1) 先补（USB 端口没变的情况下，这里就把上一次的端点修好了）
apply

# 2) 拉起 Yaagl
if [ -z "$HAPTICS_SKIP_OPEN" ]; then
    open -a "$APP"
fi

# 3) 等游戏进程起来（最多等 5 分钟），起来后再补几次
WAIT="${HAPTICS_WAIT_SECS:-300}"
for _ in $(seq 1 $((WAIT / 3))); do
    sleep 3
    pgrep -f "Genshin Impact Game/YuanShen.exe" >/dev/null 2>&1 && break
done

if pgrep -f "Genshin Impact Game/YuanShen.exe" >/dev/null 2>&1; then
    apply
    sleep 10; apply
    sleep 20; apply
fi
