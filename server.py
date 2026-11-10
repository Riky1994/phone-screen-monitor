#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PhoneDeck - 把旧手机变成 PC 性能看板（PC 端服务）

用法:
    python server.py            # 默认 8787 端口
    python server.py --port 9000

手机浏览器访问 http://<本机局域网IP>:8787 即可，无需安装任何 App。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "libs"))

try:
    import psutil
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少 psutil，请确认 libs/ 目录完整\n")
    raise

try:  # 一次内核查询的快速进程枚举；失败则退回 psutil
    import fastproc  # type: ignore
except Exception:
    fastproc = None  # type: ignore

try:  # 驱动自带的 NVML，读显卡不用起子进程
    import gpu_nvml  # type: ignore
except Exception:
    gpu_nvml = None  # type: ignore

try:  # 从 RTSS 共享内存读游戏帧率（装了 MSI Afterburner 才有）
    import fps_rtss  # type: ignore
except Exception:
    fps_rtss = None  # type: ignore

# LibreHardwareMonitor 的可选数据源（用于 CPU 温度 / 风扇 / 功耗）
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "server.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 1_000_000:
            LOG_FILE.write_text("", encoding="utf-8")
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def cpu_model() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        return " ".join(name.split())
    except Exception:
        import platform

        return platform.processor() or "CPU"


def lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for _nic, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family != socket.AF_INET:
                    continue
                if a.address.startswith(("127.", "169.254.")):
                    continue
                if a.address not in ips:
                    ips.append(a.address)
    except Exception:
        pass

    def rank(ip: str) -> int:
        if ip.startswith("192.168."):
            return 0
        if ip.startswith("10."):
            return 1
        if re.match(r"172\.(1[6-9]|2\d|3[01])\.", ip):
            return 2
        return 3

    return sorted(ips, key=rank)


def _num(raw: str | None):
    """把 nvidia-smi 返回的字符串数值转成 float，无法解析返回 None。"""
    if raw is None:
        return None
    s = raw.strip()
    if not s or s.upper() in {"N/A", "[N/A]", "NA", "[NOT SUPPORTED]", "NONE"}:
        return None
    m = re.match(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def read_gpu():
    """读取 NVIDIA 显卡状态：优先 NVML（无子进程），否则退回 nvidia-smi。"""
    if gpu_nvml is not None:
        data = gpu_nvml.read()
        if data is not None:
            return data

    fields = [
        "name",
        "temperature.gpu",
        "utilization.gpu",
        "utilization.memory",
        "memory.used",
        "memory.total",
        "power.draw",
        "clocks.current.graphics",
        "clocks.current.memory",
        "fan.speed",
    ]
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=" + ",".join(fields), "--format=csv,noheader,nounits"],
            capture_output=True,
            timeout=3,
            creationflags=NO_WINDOW,
        )
        line = out.stdout.decode("utf-8", "replace").strip().splitlines()[0]
    except Exception:
        return None
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < len(fields):
        parts += [""] * (len(fields) - len(parts))
    return {
        "name": parts[0],
        "temp": _num(parts[1]),
        "util": _num(parts[2]),
        "memUtil": _num(parts[3]),
        "memUsed": _num(parts[4]),
        "memTotal": _num(parts[5]),
        "power": _num(parts[6]),
        "clock": _num(parts[7]),
        "clockMem": _num(parts[8]),
        "fan": _num(parts[9]),
    }


# --------------------------------------------------------------------------- #
# 电池 / 天气 / 帧率（第 3、2 页用）
# --------------------------------------------------------------------------- #
WMO_DESC = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴",
}

_weather_cache = {"data": None, "ts": 0.0, "loc": None}

# 天气定位：直接写死坐标，比 IP 定位准（IP 经常落到省会）。
# 换地方只改这三行即可；也可以在坐标处填 None 让它退回 IP 定位。
# 留空 = 自动定位（国内 IP 库能到市级，自动定位最多也就到市）。
# 想锁定到具体某个乡镇/县，把 name 和 lat/lon 填上即可，例如：
#   {"name": "梅州·大埔", "lat": 24.3483, "lon": 116.6954}
WEATHER_PLACE = {"name": "", "lat": None, "lon": None}


def read_battery():
    try:
        b = psutil.sensors_battery()
    except Exception:
        return None
    if b is None:
        return None
    left = None
    try:
        if not b.power_plugged and b.secsleft not in (
            psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN
        ):
            left = int(b.secsleft)
    except Exception:
        pass
    return {"pct": round(float(b.percent)), "plugged": bool(b.power_plugged), "left": left}


def _geocode(name: str):
    """把城市名换成经纬度（open-meteo 免费、无 key）。"""
    try:
        q = name.replace("市", "").replace("县", "").replace("区", "").strip()
        if not q:
            return None
        url = ("https://geocoding-api.open-meteo.com/v1/search?count=1&language=zh&format=json&name="
               + urllib.parse.quote(q))
        with urllib.request.urlopen(url, timeout=8) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        r = (d.get("results") or [None])[0]
        if r and r.get("latitude") and r.get("longitude"):
            return float(r["latitude"]), float(r["longitude"])
    except Exception:
        pass
    return None


def _locate():
    """自动定位：配置写死 → 国内 IP 库（市级，比国外库准）→ 国外库 → 兜底。"""
    if WEATHER_PLACE.get("lat") and WEATHER_PLACE.get("lon"):
        return WEATHER_PLACE["lat"], WEATHER_PLACE["lon"], WEATHER_PLACE.get("name") or ""

    # 1) pconline：国内库，能判到市（实测 119.125.x.x → 广东省梅州市）
    try:
        raw = urllib.request.urlopen(
            "https://whois.pconline.com.cn/ipJson.jsp?json=true", timeout=8
        ).read().decode("gbk", "replace")
        d = json.loads(raw.strip())
        city = (d.get("city") or "").strip()
        if city:
            coords = _geocode(city)
            if coords:
                return coords[0], coords[1], city
    except Exception:
        pass

    # 2) ip-api：国外库，只作兜底
    try:
        with urllib.request.urlopen(
            "http://ip-api.com/json/?fields=status,city,lat,lon", timeout=8
        ) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        if d.get("status") == "success" and d.get("lat"):
            return float(d["lat"]), float(d["lon"]), str(d.get("city") or "")
    except Exception:
        pass

    # 3) 都没拿到就用大埔县城坐标兜底
    return 24.3483, 116.6954, "梅州·大埔"


def read_weather():
    """10 分钟缓存，取不到就返回上一次的结果。"""
    now = time.time()
    if _weather_cache["data"] is not None and now - _weather_cache["ts"] < 600:
        return _weather_cache["data"]
    _weather_cache["ts"] = now
    try:
        if _weather_cache["loc"] is None:
            _weather_cache["loc"] = _locate()
        lat, lon, city = _weather_cache["loc"]
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
            "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            "weather_code,wind_speed_10m&timezone=auto" % (lat, lon)
        )
        req = urllib.request.Request(url, headers={"User-Agent": "PhoneDeck/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        cur = d.get("current") or {}
        code = int(cur.get("weather_code", -1))
        data = {
            "city": city or "本地",
            "temp": cur.get("temperature_2m"),
            "feels": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind": cur.get("wind_speed_10m"),
            "desc": WMO_DESC.get(code, "未知"),
        }
        _weather_cache["data"] = data
        return data
    except Exception:
        return _weather_cache["data"]


def read_fps():
    if fps_rtss is None:
        return None
    return fps_rtss.read_fps()


# --------------------------------------------------------------------------- #
# 采样器
# --------------------------------------------------------------------------- #
class BackgroundPoller(threading.Thread):
    """把「可能很慢」的采集项放到独立线程：nvidia-smi 在笔记本独显休眠时会卡住，
    LibreHardwareMonitor 没开时 TCP 探测会等到超时，进程枚举有几百个进程时也不稳定。
    任何一个卡住都不应该拖慢 CPU/内存的每秒刷新。"""

    def __init__(self, fn, interval: float, name: str) -> None:
        super().__init__(name=name, daemon=True)
        self._fn = fn
        self._interval = interval
        self._lock = threading.Lock()
        self._data = None

    def run(self) -> None:
        while True:
            try:
                data = self._fn()
                if data is not None:
                    with self._lock:
                        self._data = data
            except Exception:
                pass
            time.sleep(self._interval)

    def get(self):
        with self._lock:
            return self._data


def make_top_reader(n: int = 8):
    """进程 TOP（按整机 CPU 占比排序）。

    优先用一次内核查询（fastproc）：逐进程 OpenProcess 在本机被安全软件拖慢到
    ~3.5ms/个，360+ 个进程扫一遍要 2.7 秒 CPU；快速路径只要 1ms 以内。
    拿不到时退回 psutil，功能不变、只是慢。
    """
    ncpu = psutil.cpu_count(logical=True) or 1
    state = {"prev": {}, "t": time.time()}
    # System / Registry / 内存压缩 这类没有普通进程语义，列表里没意义
    skip_names = {"system", "idle", "registry", "memory compression", "memcompression", "secure system"}

    def via_fastproc():
        rows = fastproc.list_processes()
        now = time.time()
        dt = max(now - state["t"], 0.2)
        state["t"] = now
        prev = state["prev"]
        cur = {}
        out = []
        for r in rows:
            pid = r["pid"]
            name = r["name"] or "?"
            secs = r["cpu"] / 1e7  # 100ns -> 秒
            cur[pid] = secs
            if pid <= 4 or name.lower() in skip_names:
                continue
            before = prev.get(pid)
            share = 0.0 if before is None else (secs - before) / dt / ncpu * 100.0
            out.append({
                "name": name,
                "pid": pid,
                "cpu": round(max(0.0, share), 2),
                "mem": r["ws"],
            })
        state["prev"] = cur
        out.sort(key=lambda x: (-x["cpu"], -x["mem"]))
        return {"top": out[:n], "procs": len(rows)}

    def via_psutil():
        rows = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                cpu = p.cpu_percent(None)
                name = (p.info.get("name") or "?").strip()
                rss = p.info["memory_info"].rss if p.info.get("memory_info") else 0
            except Exception:
                continue
            if p.info["pid"] <= 4 or not name:
                continue
            rows.append({"name": name, "pid": p.info["pid"], "cpu": round(cpu / ncpu, 2), "mem": rss})
        rows.sort(key=lambda r: (-r["cpu"], -r["mem"]))
        try:
            count = len(psutil.pids())
        except Exception:
            count = len(rows)
        return {"top": rows[:n], "procs": count}

    def reader():
        if fastproc is not None:
            try:
                return via_fastproc()
            except Exception:
                pass
        return via_psutil()

    return reader


class Sampler:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict = {
            "ok": False,
            "t": 0,
            "host": socket.gethostname(),
            "cpuModel": cpu_model(),
            "os": "",
            "boot": psutil.boot_time(),
            "cpu": {"pct": 0, "cores": [], "temp": None, "power": None, "threads": psutil.cpu_count(logical=True)},
            "mem": {"total": 0, "used": 0, "pct": 0, "swapPct": 0},
            "gpu": None,
            "disk": [],
            "io": {"read": 0, "write": 0},
            "net": {"down": 0, "up": 0, "iface": ""},
            "top": [],
            "procs": 0,
            "restricted": False,
            "fan": None,
            "lhm": False,
            "battery": None,
            "weather": None,
            "fps": None,
            "ip": "",
        }
        self._prev_io = None
        self._prev_net = None
        self._net_down = 0
        self._net_up = 0
        self._gpu = BackgroundPoller(read_gpu, 1.0, "gpu")
        self._procs = BackgroundPoller(make_top_reader(8), 2.0, "procs")
        self._batt = BackgroundPoller(read_battery, 10.0, "batt")
        self._weather = BackgroundPoller(read_weather, 60.0, "weather")
        self._fps = BackgroundPoller(read_fps, 1.0, "fps")
        self._ip = (lan_ips() or [""])[0]
        self._prev_t = time.time()
        self._primary_nic = self._find_primary_nic()

    @staticmethod
    def _find_primary_nic() -> str:
        ips = set(lan_ips())
        try:
            for nic, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET and a.address in ips:
                        return nic
        except Exception:
            pass
        return ""

    def snapshot(self) -> dict:
        with self._lock:
            return self._data

    def run(self) -> None:
        import platform

        self._data["os"] = f"{platform.system()} {platform.release()}"
        psutil.cpu_percent(interval=None, percpu=True)  # 预热
        self._gpu.start()
        self._procs.start()
        self._batt.start()
        self._weather.start()
        self._fps.start()
        tick = 0
        while True:
            try:
                self._sample(tick)
            except Exception as exc:  # 采样异常不影响服务
                log(f"sample error: {exc!r}")
            tick += 1

    def _sample(self, tick: int) -> None:
        cores = psutil.cpu_percent(interval=0.85, percpu=True)
        mem = psutil.virtual_memory()
        try:
            swap = psutil.swap_memory()
        except Exception:
            swap = None

        io = psutil.disk_io_counters()
        try:
            net = psutil.net_io_counters(pernic=True)
        except Exception:
            net = {}
        now = time.time()
        dt = max(now - self._prev_t, 0.2)

        r_speed = w_speed = 0.0
        if io and self._prev_io:
            r_speed = max(0.0, (io.read_bytes - self._prev_io.read_bytes) / dt)
            w_speed = max(0.0, (io.write_bytes - self._prev_io.write_bytes) / dt)
        self._prev_io = io

        down = up = 0.0
        iface = self._primary_nic
        if net:
            if iface not in net:
                iface = max(net, key=lambda k: net[k].bytes_sent + net[k].bytes_recv)
            if self._prev_net and iface in self._prev_net:
                d_recv = max(0, net[iface].bytes_recv - self._prev_net[iface].bytes_recv)
                d_sent = max(0, net[iface].bytes_sent - self._prev_net[iface].bytes_sent)
                down, up = d_recv / dt, d_sent / dt
                self._net_down += d_recv
                self._net_up += d_sent
            self._prev_net = net
        self._prev_t = now

        gpu = self._gpu.get()
        gpu = dict(gpu) if gpu else None

        disks = []
        if tick % 5 == 0:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except Exception:
                    continue
                if usage.total <= 0:
                    continue
                fs = (part.fstype or "").upper()
                if fs in {"CDFS", "UDF"}:
                    continue
                disks.append(
                    {
                        "mount": part.device.rstrip("\\") or part.device,
                        "total": usage.total,
                        "used": usage.used,
                        "pct": round(usage.percent, 1),
                    }
                )
            self._disks = disks
        disks = getattr(self, "_disks", [])

        topinfo = self._procs.get() or {"top": [], "procs": 0}
        top = topinfo.get("top", [])
        nproc = topinfo.get("procs", 0)

        data = {
            "ok": True,
            "t": round(now, 3),
            "host": self._data["host"],
            "cpuModel": self._data["cpuModel"],
            "os": self._data["os"],
            "boot": self._data["boot"],
            "uptime": round(now - self._data["boot"], 1),
            "cpu": {
                "pct": round(sum(cores) / max(len(cores), 1), 1),
                "cores": [round(c, 1) for c in cores],
                "threads": len(cores),
                "phys": psutil.cpu_count(logical=False) or len(cores),
            },
            "mem": {
                "total": mem.total,
                "used": mem.used,
                "pct": round(mem.percent, 1),
                "swapPct": round(swap.percent, 1) if swap else None,
            },
            "gpu": gpu,
            "disk": disks,
            "io": {"read": r_speed, "write": w_speed},
            "net": {"down": down, "up": up, "iface": iface, "totalDown": self._net_down, "totalUp": self._net_up},
            "top": top,
            "procs": nproc,
            "restricted": nproc < 40,
            "fan": None,
            "lhm": False,
            "battery": self._batt.get(),
            "weather": self._weather.get(),
            "fps": self._fps.get(),
            "ip": self._ip,
        }
        with self._lock:
            self._data = data


# --------------------------------------------------------------------------- #
# 一键加速：整理各进程的内存工作集，把闲置页推回备用列表，释放物理内存
#
# 说明：这里不结束任何进程，也不会去动系统关键进程；只能整理当前用户自己的
# 进程（非管理员权限跨不过去），所以安全边界是「最多让别人的程序慢一瞬」。
# --------------------------------------------------------------------------- #
BOOST_TOKEN = secrets.token_urlsafe(18)
BOOST_MIN_INTERVAL = 15.0
BOOST_MIN_WS = 40 * 1024 * 1024  # 小于 40MB 的进程不值得动
_boost_state = {"last": 0.0, "running": False}

# 系统 / 会话关键进程一律不碰
BOOST_SKIP = {
    "system", "idle", "registry", "memory compression", "secure system",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "dwm.exe", "fontdrvhost.exe", "audiodg.exe", "spoolsv.exe",
}


def boost_memory() -> dict:
    """整理工作集，返回释放量等统计。"""
    import ctypes
    from ctypes import wintypes

    before = psutil.virtual_memory()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.SetProcessWorkingSetSize.argtypes = [
        wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t
    ]
    kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    # PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION
    access = 0x0100 | 0x0400
    minus_one = ctypes.c_size_t(-1).value
    me = os.getpid()
    trimmed = 0
    locked = 0

    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            pid = info["pid"]
            name = (info.get("name") or "").lower()
            mem = info.get("memory_info")
            if pid <= 4 or pid == me or mem is None:
                continue
            if name in BOOST_SKIP or mem.rss < BOOST_MIN_WS:
                continue
            handle = kernel32.OpenProcess(access, False, pid)
            if not handle:
                locked += 1
                continue
            try:
                if kernel32.SetProcessWorkingSetSize(handle, minus_one, minus_one):
                    trimmed += 1
                else:
                    locked += 1
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            continue

    time.sleep(0.8)  # 等系统回收完再量
    after = psutil.virtual_memory()
    freed = max(0, (before.total - before.available) - (after.total - after.available))
    return {
        "ok": True,
        "trimmed": trimmed,
        "locked": locked,
        "freed": int(freed),
        "beforePct": round(before.percent, 1),
        "afterPct": round(after.percent, 1),
    }


# --------------------------------------------------------------------------- #
# HTTP 服务
# --------------------------------------------------------------------------- #
WEB_DIR = BASE / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "PhoneDeck/1.0"
    protocol_version = "HTTP/1.1"

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _send_json(self, obj: dict, code: int = 200) -> None:
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", code)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            try:
                body = (WEB_DIR / "index.html").read_bytes()
                # 把本次运行的加速令牌发给页面（跨站读不到，天然挡掉伪造请求）
                body = body.replace(b"__BOOST_TOKEN__", BOOST_TOKEN.encode("ascii"))
            except Exception:
                self.send_error(500, "index.html missing")
                return
            self._send(body, "text/html; charset=utf-8")
        elif path == "/api/stats":
            body = json.dumps(SAMPLER.snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
        elif path == "/health":
            body = json.dumps({"ok": True, "t": time.time(), "pid": os.getpid()}).encode("utf-8")
            self._send(body, "application/json")
        elif path == "/favicon.ico":
            self._send(b"", "image/x-icon")
        else:
            self.send_error(404)

    def log_message(self, fmt: str, *args) -> None:  # 静默，避免刷日志
        pass

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except Exception:
            length = 0
        if length:
            try:
                self.rfile.read(length)  # 读掉请求体，避免 keep-alive 串包
            except Exception:
                pass

        if path != "/api/boost":
            self.send_error(404)
            return

        if self.headers.get("X-Boost-Token") != BOOST_TOKEN:
            self._send_json({"ok": False, "error": "forbidden"}, 403)
            return

        now = time.time()
        wait = BOOST_MIN_INTERVAL - (now - _boost_state["last"])
        if wait > 0:
            self._send_json({"ok": False, "error": "cooldown", "retryAfter": int(wait) + 1}, 429)
            return
        if _boost_state["running"]:
            self._send_json({"ok": False, "error": "busy"}, 409)
            return

        _boost_state["running"] = True
        t0 = time.time()
        try:
            result = boost_memory()
        except Exception as exc:
            result = {"ok": False, "error": "failed", "detail": str(exc)}
        finally:
            _boost_state["running"] = False
            _boost_state["last"] = time.time()
        result["took"] = round(time.time() - t0, 2)
        if result.get("ok"):
            log(f"一键加速: 整理 {result['trimmed']} 个进程, 释放 {result['freed'] // 1048576} MB, "
                f"占用 {result['beforePct']}% -> {result['afterPct']}%")
        self._send_json(result)


class QuietServer(ThreadingHTTPServer):
    """客户端主动断开（关页面、切后台）是常态，不要往日志里刷 traceback。"""

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        exc = sys.exc_info()[1]
        benign = (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError, OSError)
        if isinstance(exc, benign):
            return
        log(f"request error from {client_address}: {exc!r}")


SAMPLER = Sampler()


def already_running(port: int) -> bool:
    """端口上已有实例且它还在正常采样（时间戳新鲜）才算「正在运行」。

    残留的僵死实例可能还占着端口、还能回 HTTP，但采样线程已停；
    这种情况必须放行新实例去接管，否则用户会一直看到一张不动的看板。
    """
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.2) as resp:
            data = json.loads(resp.read(256).decode("utf-8", "replace"))
    except Exception:
        return False
    if not isinstance(data, dict) or not data.get("ok"):
        return False
    try:
        return abs(time.time() - float(data.get("t", 0))) <= 8
    except Exception:
        return False


def main() -> None:
    port = 8787
    args = sys.argv[1:]
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except Exception:
            pass

    if already_running(port):
        log(f"端口 {port} 上已有 PhoneDeck 在运行，本次不再重复启动")
        print(f"已在运行: http://127.0.0.1:{port}")
        return

    sampler_thread = threading.Thread(target=SAMPLER.run, name="sampler", daemon=True)
    sampler_thread.start()

    httpd = None
    for p in range(port, port + 10):
        try:
            httpd = QuietServer(("0.0.0.0", p), Handler)
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        log(f"端口 {port}-{port + 9} 全部被占用，退出")
        sys.exit(1)

    httpd.daemon_threads = True
    (LOG_DIR / "server.pid").write_text(str(os.getpid()), encoding="utf-8")

    log("PhoneDeck 已启动")
    log(f"本机地址: http://127.0.0.1:{port}")
    ips = lan_ips()
    for ip in ips:
        log(f"手机访问: http://{ip}:{port}")
    try:
        runnable = f"http://{ips[0]}:{port}" if ips else f"http://127.0.0.1:{port}"
        (BASE / "address.txt").write_text(runnable, encoding="utf-8")
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("收到中断，退出")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
