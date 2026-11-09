# -*- coding: utf-8 -*-
"""通过 NVML 读取显卡状态。

驱动自带的 nvml.dll 直接给出利用率/温度/显存/功耗/频率，不需要每秒启动
nvidia-smi 子进程（那一步每次要 ~47ms CPU 和一次进程创建）。
"""
import ctypes
from ctypes import POINTER, Structure, byref, c_char_p, c_uint, c_ulonglong, c_void_p


class _Util(Structure):
    _fields_ = [("gpu", c_uint), ("memory", c_uint)]


class _Mem(Structure):
    _fields_ = [("total", c_ulonglong), ("free", c_ulonglong), ("used", c_ulonglong)]


_lib = None
_handle = None
_failed = False


def _init() -> bool:
    global _lib, _handle, _failed
    if _handle is not None:
        return True
    if _failed:
        return False
    try:
        lib = ctypes.WinDLL("nvml.dll")
        lib.nvmlInit_v2.restype = ctypes.c_int
        if lib.nvmlInit_v2() != 0:
            _failed = True
            return False
        lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [c_uint, POINTER(c_void_p)]
        lib.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
        handle = c_void_p()
        if lib.nvmlDeviceGetHandleByIndex_v2(0, byref(handle)) != 0:
            _failed = True
            return False
        lib.nvmlDeviceGetName.argtypes = [c_void_p, c_char_p, c_uint]
        lib.nvmlDeviceGetUtilizationRates.argtypes = [c_void_p, POINTER(_Util)]
        lib.nvmlDeviceGetTemperature.argtypes = [c_void_p, c_uint, POINTER(c_uint)]
        lib.nvmlDeviceGetMemoryInfo.argtypes = [c_void_p, POINTER(_Mem)]
        lib.nvmlDeviceGetPowerUsage.argtypes = [c_void_p, POINTER(c_uint)]
        lib.nvmlDeviceGetClockInfo.argtypes = [c_void_p, c_uint, POINTER(c_uint)]
        lib.nvmlDeviceGetFanSpeed.argtypes = [c_void_p, POINTER(c_uint)]
        _lib, _handle = lib, handle
        return True
    except Exception:
        _failed = True
        return False


def read():
    """返回与 nvidia-smi 版本同结构的 dict；不可用时返回 None。"""
    if not _init():
        return None
    try:
        name = ctypes.create_string_buffer(96)
        _lib.nvmlDeviceGetName(_handle, name, 96)

        util = _Util()
        if _lib.nvmlDeviceGetUtilizationRates(_handle, byref(util)) != 0:
            return None

        temp = c_uint()
        rc_temp = _lib.nvmlDeviceGetTemperature(_handle, 0, byref(temp))  # 0 = GPU

        mem = _Mem()
        _lib.nvmlDeviceGetMemoryInfo(_handle, byref(mem))

        power = c_uint()
        rc_power = _lib.nvmlDeviceGetPowerUsage(_handle, byref(power))

        clk = c_uint()
        rc_clk = _lib.nvmlDeviceGetClockInfo(_handle, 0, byref(clk))  # 0 = 图形核心
        clk_mem = c_uint()
        _lib.nvmlDeviceGetClockInfo(_handle, 2, byref(clk_mem))  # 2 = 显存

        fan = c_uint()
        rc_fan = _lib.nvmlDeviceGetFanSpeed(_handle, byref(fan))

        return {
            "name": name.value.decode("utf-8", "replace"),
            "temp": float(temp.value) if rc_temp == 0 else None,
            "util": float(util.gpu),
            "memUtil": float(util.memory),
            "memUsed": mem.used / 1048576.0,
            "memTotal": mem.total / 1048576.0,
            "power": round(power.value / 1000.0, 2) if rc_power == 0 else None,
            "clock": float(clk.value) if rc_clk == 0 else None,
            "clockMem": float(clk_mem.value) if rc_clk == 0 else None,
            "fan": float(fan.value) if rc_fan == 0 else None,
        }
    except Exception:
        return None


if __name__ == "__main__":
    import time

    d = read()
    print(d)
    t0 = time.process_time()
    for _ in range(100):
        read()
    print(f"100 次读取 CPU {(time.process_time() - t0) * 1000:.1f} ms")
