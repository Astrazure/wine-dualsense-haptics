#!/bin/bash
# 生成「Yaagl 带震动」.app（拖到 Dock / 双击即可启动，跑完自动退出）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-$HOME/Applications/Yaagl 带震动.app}"

chmod +x "$DIR/launch-yaagl.sh"
mkdir -p "$(dirname "$APP")"

osacompile -o "$APP" -e "do shell script \"nohup '$DIR/launch-yaagl.sh' >/dev/null 2>&1 &\""

echo "已生成：$APP"
echo "把它拖到 Dock，以后用它启动 Yaagl 就行。"
