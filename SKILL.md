---
name: phone-screen-monitor
description: 把闲置手机变成电脑的实时性能看板（CPU 每核占用、内存、显卡温度/功耗、磁盘、网络、进程 TOP，外加一键内存加速）。在 Windows 上部署一个本地 HTTP 服务，手机浏览器直接打开即可，无需安装 App。当用户提到"旧手机改监控屏""手机看电脑性能""性能看板""第二块屏监控"或想复刻这套看板时使用。
metadata:
  display_name: 手机屏监控电脑性能
  version: 1.2.0
  platform: windows
---

# 手机屏监控电脑性能（PhoneDeck）

## 这是什么

在 Windows 电脑上跑一个单进程的小服务（Python 标准库 + 一个 psutil），
手机连同一个 Wi-Fi、浏览器打开 `http://<电脑IP>:8787` 就能看到实时看板：
CPU 总/每核、内存、显卡（占用/温度/显存/功耗/频率）、磁盘、读写速度、网络上下行、进程 TOP，
外加 120 秒趋势曲线、三页分页（系统 / 游戏 / 生活，纯手势滑动换页，无翻页按钮）、横竖屏切换、5 套皮肤、一键加速。

手机端零安装；电脑端只有一个 pythonw 进程，实测整机 CPU 占用 **0.1%**、内存约 25 MB。

## 什么时候用

- 用户有一台闲置手机/平板，想当电脑的性能监控屏
- 想要"不联网、不装 App、局域网直连"的监控方案
- 已经在用这个看板，需要在新电脑上复刻一份

## 前置条件

| 项 | 要求 |
|---|---|
| 系统 | Windows 10 / 11 x64（依赖 Windows API，不支持 Linux/macOS） |
| Python | 3.9+；或机器上有 DSH 自带的运行时（`%USERPROFILE%\.dsh\dsh-runtimes\...`） |
| 网络 | 手机与电脑同一路由器（电脑走网线没问题） |
| 显卡 | 可选。NVIDIA 走 NVML 读温度/功耗；没有显卡或 AMD 只是少几项指标 |
| 权限 | 启动不需要管理员；放行防火墙需要一次 UAC |

## 部署（三步）

1. **放下文件**：把整个文件夹复制到目标目录（路径可以含中文，例如 `D:\手机屏监控电脑性能看板`）。
2. **右键 `setup.ps1` →「使用 PowerShell 运行」**（或 `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`）。
   它会依次：找到 Python → 校验 `libs/psutil` → 建桌面快捷方式 → 申请 UAC 放行 TCP 8787-8796 → 启动服务 → 打印手机地址。
3. **手机打开打印出来的地址**（形如 `http://192.168.1.85:8787`），或扫 `qr.png`。

之后日常只需双击桌面快捷方式 / `启动看板.bat`。

## 验证清单

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health    # {"ok":true,"t":<时间戳>,"pid":<PID>}
Invoke-RestMethod http://127.0.0.1:8787/api/stats # cpu/mem/gpu/disk/io/net/top/procs
Invoke-WebRequest http://<局域网IP>:8787/          # 200，且内容里 boost-token 已被替换
netstat -ano | findstr :8787                       # LISTENING
```

`/health` 里的 `t` 必须是"现在"附近的时间——这是判断实例是否还活着（而不是僵死占着端口）的依据。

## 性能红线（改代码前必读）

这套看板的第一版实测 CPU 占单核 **66%（整机 4.2%）**，原因有两个，都已修掉，**不要改回去**：

1. **进程枚举**：`psutil.process_iter` + `memory_info` + `cpu_percent` 会对每个进程 `OpenProcess`。
   在装了安全软件/反外挂驱动的机器上单次 3.5 ms，360+ 个进程一轮 2.9 秒 CPU。
   → 改用 `fastproc.py`：一次 `NtQuerySystemInformation(SystemProcessInformation)` 拿全量
   （实测 < 1 ms），按 PID 差分算 CPU 占比；`psutil` 只作兜底。
2. **显卡**：每秒 `subprocess` 拉起 `nvidia-smi`，单次 47 ms CPU + 一次进程创建。
   → 改用 `gpu_nvml.py`：`ctypes` 加载 `nvml.dll` 直读（100 次读取 0.2 ms），`nvidia-smi` 只作兜底。

优化后实测：20 秒消耗 0.33 秒 CPU（单核 1.65%，整机 0.103%）、工作集 25 MB、无子进程。
改动任何采集代码后，请用同样的方法复测（见 `references/measure.md`）。

## 目录结构

```
手机屏监控电脑性能/
├─ setup.ps1            一键部署（检查 + 快捷方式 + 防火墙 + 启动）
├─ 启动看板.bat          日常启动（失败会停住窗口，不会一闪而过）
├─ 停止看板.bat          停止后台服务
├─ 允许手机访问.bat       放行防火墙 TCP 8787-8796（需 UAC，一次即可）
├─ 安装开机自启.bat / 移除开机自启.bat
├─ server.py            采集 + HTTP 服务（标准库 + psutil）
├─ fastproc.py          快速进程枚举（NtQuerySystemInformation）
├─ gpu_nvml.py          显卡直读（NVML），失败回退 nvidia-smi
├─ web/index.html       手机端页面（单文件，无 CDN 依赖）
├─ scripts/             .bat 的具体实现（PowerShell）
├─ libs/psutil          内置依赖，不污染系统 Python
├─ tools/               自检与二维码脚本
└─ README.md            面向使用者的完整说明
```

## 关键实现约定

- **单实例**：启动时若 8787 已被同版本实例占用且 `/health` 时间戳新鲜，则直接退出，不重复起。
- **端口顺延**：8787 被别的程序占用时自动试 8788/8789…，并把真实地址写进 `address.txt`（防火墙规则已覆盖 8787-8796）。
- **写操作只有一键加速**：`POST /api/boost` 必须带页面 `<meta name="boost-token">` 注入的 `X-Boost-Token`，
  否则 403；15 秒冷却；只整理当前用户进程的工作集，不结束任何进程。
- **页面无外部依赖**：不引 CDN、不引字体，断网可用。

## 常见故障

| 症状 | 原因 | 处理 |
|---|---|---|
| 手机打不开，电脑上能打开 | 防火墙没放行 | 双击 `允许手机访问.bat`，UAC 点「是」 |
| 手机和电脑都打不开 | 服务没在跑 | 双击 `启动看板.bat`；失败时窗口会停住并显示日志尾部 |
| 地址变了 | 电脑 IP 被重新分配 | 重开 `启动看板.bat`，看新打印的地址 / 重新生成 `qr.png` |
| 进程 TOP 显示「受限视图」 | 服务以受限权限启动 | 退出后用桌面快捷方式正常启动 |
| 启动窗口一闪就没 | 旧版脚本 | 现版本失败会 `pause`；若仍闪，直接命令行运行 `scripts\start.ps1` |

## 已知限制

- 仅 Windows；采集依赖 `psutil`、`NtQuerySystemInformation`、`nvml.dll`。
- 手机端是 HTTP（非 HTTPS），浏览器不提供 Wake Lock，需在手机上把「休眠」设为永不。
- 局域网内无鉴权：能访问到页面的人就能看到进程列表（写操作仍受令牌保护）。不要在不可信网络里开。

## 参考

- `README.md` —— 面向使用者的完整说明（含皮肤、横竖屏、一键加速的细节）
- `references/measure.md` —— 如何复测 CPU 占用
- `tools/check.py`、`tools/test_orient.js`、`tools/test_chart.js` —— 页面自检三件套
