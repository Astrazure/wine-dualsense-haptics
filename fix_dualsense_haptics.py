#!/usr/bin/env python3
"""
fix_dualsense_haptics.py — 让 Wine（Yaagl / CrossOver）里的 DualSense 手柄恢复音频触觉震动

原理见 README。简而言之：Wine 的 winecoreaudio 驱动不给音频端点填
  * PKEY_Device_ContainerId     （Wwise 靠它把音频端点和 HID 手柄认成同一个设备）
  * PKEY_AudioEndpoint_PhysicalSpeakers / FullRangeSpeakers（四声道配置）
于是游戏（例如原神，Wwise 音频引擎）找不到震动通道，静默关闭震动。
本脚本按 winebus 的同一套算法算出 containerID 并写进设备的属性键。

用法：
  python3 fix_dualsense_haptics.py                 # 自动找 Yaagl 的 wine/prefix 并修复
  python3 fix_dualsense_haptics.py --list          # 只列出候选音频端点
  python3 fix_dualsense_haptics.py --undo          # 撤销本脚本写入的三个属性
  python3 fix_dualsense_haptics.py --wine /path/to/wine --prefix /path/to/prefix
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys

RENDER_KEY = r"HKLM\Software\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"

# 与 winebus.sys/main.c 完全一致：container id = SHA1(父设备字符串) 的前 16 字节
# macOS 上 IOHID 后端的父设备字符串是固定的 "/bus/iohid"
PARENT_STRING = "/bus/iohid"

PKEY_CONTAINER_ID = "{8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C},2"
PKEY_PHYSICAL_SPEAKERS = "{1DA5D803-D492-4EDD-8C23-E0C0FFEE7F0E},3"
PKEY_FULLRANGE_SPEAKERS = "{1DA5D803-D492-4EDD-8C23-E0C0FFEE7F0E},6"

QUAD_SPEAKERS = "0x33"   # FL|FR|BL|BR
FULLRANGE_MASK = "0xf"   # 四个声道都算全音域

MATCH_NAMES = ("dualsense", "wireless controller")


def container_guid(parent: str) -> str:
    raw = hashlib.sha1(parent.encode("utf-16-le")).digest()[:16]
    d1 = int.from_bytes(raw[0:4], "little")
    d2 = int.from_bytes(raw[4:6], "little")
    d3 = int.from_bytes(raw[6:8], "little")
    d4 = raw[8:16]
    return "{%08x-%04x-%04x-%02x%02x-%s}" % (
        d1, d2, d3, d4[0], d4[1], "".join("%02x" % b for b in d4[2:])
    )


def find_default_paths():
    home = os.path.expanduser("~")
    yaagl_wine = os.path.join(home, "Library/Application Support/Yaagl/wine/bin/wine")
    yaagl_prefix = os.path.join(home, "Library/Application Support/Yaagl/wineprefix")
    if os.path.exists(yaagl_wine) and os.path.isdir(yaagl_prefix):
        return yaagl_wine, yaagl_prefix
    return None, None


def run(wine, prefix, *args):
    env = dict(os.environ, WINEPREFIX=prefix, WINEDEBUG="-all")
    return subprocess.run([wine, *args], env=env, capture_output=True, text=True)


def endpoints(wine, prefix):
    """返回 [(key, name, values_dict)]，只包含名称像手柄的渲染端点。"""
    res = run(wine, prefix, "reg", "query", RENDER_KEY, "/s")
    if res.returncode != 0:
        sys.exit("读取注册表失败：\n" + res.stderr)

    out, current, props, state, result = res.stdout.splitlines(), None, {}, {}, []
    for line in out:
        line = line.rstrip()
        if line.startswith("HKEY_"):
            if current and current.endswith("\\Properties") and props:
                name = props.get("{A45C254E-DF1C-4EFD-8020-67D146A850E0},2") or \
                       props.get("{A45C254E-DF1C-4EFD-8020-67D146A850E0},14") or ""
                parent = current[: -len("\\Properties")]
                # DeviceState: 1 = 设备在线，4 = 未插入
                if state.get(parent) in (None, "0x1") and any(m in name.lower() for m in MATCH_NAMES):
                    result.append((current, name, props))
            current, props = line, {}
        elif current and re.search(r"\s+REG_", line):
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 3:
                if parts[0] == "DeviceState":
                    state[current] = parts[-1]
                elif current.endswith("\\Properties"):
                    props[parts[0]] = parts[-1]
    if current and current.endswith("\\Properties") and props:
        name = props.get("{A45C254E-DF1C-4EFD-8020-67D146A850E0},2") or ""
        parent = current[: -len("\\Properties")]
        if state.get(parent) in (None, "0x1") and any(m in name.lower() for m in MATCH_NAMES):
            result.append((current, name, props))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wine")
    ap.add_argument("--prefix")
    ap.add_argument("--parent", default=PARENT_STRING, help="winebus 父设备字符串")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--undo", action="store_true")
    args = ap.parse_args()

    wine, prefix = args.wine, args.prefix
    if not wine or not prefix:
        dw, dp = find_default_paths()
        wine, prefix = wine or dw, prefix or dp
    if not wine or not prefix:
        sys.exit("没找到 Yaagl 的 wine/prefix，请用 --wine 和 --prefix 指定")

    guid = container_guid(args.parent)
    eps = endpoints(wine, prefix)
    if not eps:
        sys.exit("没有找到 DualSense 音频端点。手柄插好了吗？Wine 跑过至少一次吗？")

    for key, name, props in eps:
        print(f"端点：{name}\n  {key}")
        if args.list:
            for k in (PKEY_CONTAINER_ID, PKEY_PHYSICAL_SPEAKERS, PKEY_FULLRANGE_SPEAKERS):
                print(f"    {k} = {props.get(k, '(缺失)')}")
            continue
        if args.undo:
            for k in (PKEY_CONTAINER_ID, PKEY_PHYSICAL_SPEAKERS, PKEY_FULLRANGE_SPEAKERS):
                run(wine, prefix, "reg", "delete", key, "/v", k, "/f")
            print("  已撤销三个属性")
            continue
        run(wine, prefix, "reg", "add", key, "/v", PKEY_CONTAINER_ID, "/t", "REG_SZ", "/d", guid, "/f")
        run(wine, prefix, "reg", "add", key, "/v", PKEY_PHYSICAL_SPEAKERS, "/t", "REG_DWORD", "/d", QUAD_SPEAKERS, "/f")
        run(wine, prefix, "reg", "add", key, "/v", PKEY_FULLRANGE_SPEAKERS, "/t", "REG_DWORD", "/d", FULLRANGE_MASK, "/f")
        print(f"  已写入 containerID {guid}（四声道属性同步写入）")

    if not args.list:
        print("\n完成。完全退出游戏再重开，然后进游戏试试震动。")


if __name__ == "__main__":
    main()
