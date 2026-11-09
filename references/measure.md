# 复测 CPU 占用

改动采集逻辑后，用下面两步确认没有退化。目标：**整机 ≤ 0.2%**。

## 1. 量服务进程本身

```powershell
$h = Invoke-RestMethod http://127.0.0.1:8787/health
$p1 = Get-Process -Id $h.pid
$c1 = $p1.TotalProcessorTime.TotalSeconds
Start-Sleep -Seconds 20
$p2 = Get-Process -Id $h.pid
$delta = $p2.TotalProcessorTime.TotalSeconds - $c1
"单核占用: {0:N2}%" -f ($delta / 20 * 100)
"整机占用: {0:N3}%" -f ($delta / 20 * 100 / [Environment]::ProcessorCount)
"工作集  : {0:N1} MB" -f ($p2.WorkingSet64 / 1MB)
```

判读：
- `< 2%` 单核：正常（当前约 1.6%，主要是每秒一次的磁盘/网络计数器）
- `> 20%`：某处退回了逐进程 `OpenProcess`，检查 `fastproc` 是否生效

## 2. 拆解各采样步骤

```python
import sys, time
sys.path.insert(0, r"<安装目录>\libs")
import psutil
try:
    import fastproc, gpu_nvml
except ImportError:
    fastproc = gpu_nvml = None

def bench(label, fn, n=3):
    fn()
    t0 = time.process_time()
    for _ in range(n):
        fn()
    print(f"{label:<28} {(time.process_time() - t0) / n * 1000:8.1f} ms")

bench("fastproc 全量枚举", fastproc.list_processes)
bench("NVML 读显卡", gpu_nvml.read, 50)
bench("psutil 全量扫（对照，勿用）",
      lambda: [p.cpu_percent(None) for p in psutil.process_iter(["pid", "memory_info"])], 1)
```

参考值（本机 i7-13620H / 365 进程，装了反外挂驱动）：

| 步骤 | 优化前 | 优化后 |
|---|---|---|
| 进程枚举一轮 | 2869 ms | < 1 ms |
| 显卡一轮 | 47 ms（子进程） | 0.004 ms |
| 整机占用 | 4.17% | 0.103% |

## 3. 顺手确认没有子进程残留

```powershell
Get-Process nvidia-smi -ErrorAction SilentlyContinue   # 应为空
```

如果这里能看到 `nvidia-smi`，说明 `gpu_nvml` 加载失败、退回了子进程路径——检查 `nvml.dll`
是否在 `System32`（NVIDIA 驱动 R450+ 自带），或显卡是不是 NVIDIA。
