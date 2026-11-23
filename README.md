# wine-dualsense-haptics

**让 Wine / Yaagl / CrossOver 里的《原神》（以及其它 Wwise 游戏）恢复 PS5 DualSense 手柄震动。**

在 macOS 上用手柄玩原神，按键、摇杆、触摸板全都正常，唯独**一点震动都没有**；同一只手柄在网页手柄测试里震动正常，Windows 上插线也能震。这不是手柄问题，也不是游戏没做——是 Wine 少给了游戏两个属性。

---

## 根因

DualSense 的震动（官方叫"音频触觉 / VCM haptics"）**不是 HID 报文，而是音频**：手柄会额外枚举成一个 **4 声道音频设备**，第 3、4 声道驱动震动马达。米哈游官方 FAQ 要求在 Windows 上把「扬声器 Wireless Controller」配置成**四声道**，就是为了这个。

游戏这边（原神用 **Wwise** 音频引擎，配置项里能直接看到 `"wwiseVibration":true`）要找到这个音频设备，靠的是 **containerID 匹配**：

1. 从手柄的 HID 设备拿到 `PKEY_Device_ContainerId`（标识"同一个物理设备"的 GUID）；
2. 枚举所有音频输出端点，比对哪个端点的 containerID 相同；
3. 找到后打开 4 声道流，往里播低频 = 震动。

而 Wine 在 macOS 上：

- 音频端点由 `winecoreaudio.drv` 创建，**从不写 containerID**（Wine 全树 `PKEY_Device_ContainerId` 只出现在 setupapi/cfgmgr32，mmdevapi 一次都没用）；
- 也**不写** `PKEY_AudioEndpoint_PhysicalSpeakers`（四声道）这个属性——Windows 上那步"配置扬声器"才会写它。

结果：Wwise 比对失败 → 认为"这台机器没有手柄震动设备" → **静默关闭震动**，连音频流都不会尝试打开（用 CoreAudio 探针盯了 40 秒，手柄音频设备全程 idle）。

关键发现：**Wine 的设备属性是直接存在注册表里、读取时现查的**（`devenum.c` 的 `MMDevPropStore_GetPropValue` → `RegGetValueW`）。所以不需要编译 Wine，往对端点的属性键里补上这些值就行。

## 修法

对 DualSense 那个音频端点（`HKLM\...\MMDevices\Audio\Render\{...}\Properties`）写入：

| 属性 | 值 | 作用 |
| --- | --- | --- |
| `{8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C},2`（ContainerId） | `{e06fec9a-6f35-a171-1aea-042ea77b613a}` | 与 HID 设备对上号，Wwise 才认得出 |
| `{1DA5D803-D492-4EDD-8C23-E0C0FFEE7F0E},3`（PhysicalSpeakers） | `0x33` | 四声道（FL/FR/BL/BR） |
| `{1DA5D803-D492-4EDD-8C23-E0C0FFEE7F0E},6`（FullRangeSpeakers） | `0xF` | 四个声道全音域 |

那个 GUID 不是随手编的：winebus 给 HID 设备算 containerID 的算法是 `SHA1(父设备字符串)` 取前 16 字节（见 `dlls/winebus.sys/main.c` 的 `parent_hash`），而 macOS IOHID 后端的父设备字符串固定是 `/bus/iohid`。脚本里现场算，不写死。

## 用法

```bash
# 默认自动找 Yaagl 的 wine 和 prefix
python3 fix_dualsense_haptics.py

# 只看当前端点状态
python3 fix_dualsense_haptics.py --list

# 撤销（删掉写入的三个属性）
python3 fix_dualsense_haptics.py --undo

# 其它 Wine（CrossOver 等）手动指定
python3 fix_dualsense_haptics.py --wine "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine" --prefix "$HOME/Library/Application Support/CrossOver/Bottles/<瓶名>"
```

写完**完全退出游戏再重开**（设备列表是启动时枚举的）。

脚本只动你 prefix 里的注册表，**不碰 Wine 本体**，随时可 `--undo`。

## 属性会丢？装个守护

实测发现一个坑：Wine 给音频端点分配的设备 GUID 是**按 CoreAudio 的设备 UID 算的**，而 DualSense 的 UID 里带了 USB location（换口、重新枚举就会变，例如 `...:1100000:1` → `...:100000:1`）。UID 一变，Wine 就新建一个端点键，我们之前写的属性留在旧的死键上——表现就是「昨天还好好的，今天又没震动了」。

所以提供了守护脚本，游戏运行时每 10 秒检查一次，缺了就补：

```bash
./install-watcher.sh       # 安装 launchd 任务（每 10s 检查，只在游戏运行时动手）
./install-watcher.sh --uninstall
```

> 安装需要在**你自己的终端**里跑（本工具装不了 launchd 任务，权限不够）。

日志：`/tmp/wine-dualsense-haptics.log`。

第一次装上守护后，可能那一局仍然不震（属性补上时游戏已经读完设备列表了），**再开一局就好**。

## 环境（实测通过）

- macOS 26 / Apple Silicon（M5 Pro）
- Yaagl + wine-11.0（游戏是 Windows 版原神，走 DXMT）
- DualSense 手柄 **USB 有线**连接
- 原神 7.2.0

## 已验证 / 未验证

- ✅ 有线 + 原神：震动恢复（探索、战斗、开宝箱都有）
- ⚠️ 三个属性里哪个是决定性的**没有逐项隔离**。按 Wwise 的实现推测是 ContainerId，但为了保险脚本三个一起写。
- ⚠️ 蓝牙未测试。原神官方明确说不支持蓝牙下的 DualSense 震动，所以蓝牙大概率仍然不震（跟本修复无关）。
- ⚠️ 其它 Wwise 游戏（幽灵线东京、死亡循环等，以及任何用 containerID 找手柄音频端点的游戏）大概率同样受益，但没逐个测。
- ⚠️ 每次 Wine 重新枚举设备时属性有可能被重写；如果哪天又没震动了，重跑一次脚本即可。
- ⚠️ **换 USB 口 / 重新插拔会让 Wine 生成新的设备 GUID**，旧属性失效。这属于已知问题，用上面的守护脚本兜底。

## License

MIT
