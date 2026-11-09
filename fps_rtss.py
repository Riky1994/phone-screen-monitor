# -*- coding: utf-8 -*-
"""从 RTSS 共享内存读取当前帧率。

Windows 没有系统级的帧率接口，游戏帧率只能从外部工具拿：
RTSS（RivaTuner Statistics Server，MSI Afterburner 附带）会把逐帧统计
写进名为 RTSSSharedMemoryV2 的共享内存，这里直接映射读取，不需要任何依赖。

没装 RTSS / 没在跑时返回 None，前端显示「—」。
"""
import ctypes
import time
from ctypes import wintypes

_FILE_MAP_READ = 0x0004
_SIG = 0x53535452  # 'RTSS' 小端序
_MAX_ENTRY_SIZE = 8192
_MAX_ARR = 512

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.OpenFileMappingW.restype = wintypes.HANDLE
_k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.c_size_t]
_k32.MapViewOfFile.restype = ctypes.c_void_p
_k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]

_state = {"prev": {}}  # pid -> (frames, time1)


def _u32(p):
    return ctypes.c_uint32.from_address(p).value


def read_fps():
    """返回 {"fps": float, "app": str, "pid": int} 或 None。"""
    handle = _k32.OpenFileMappingW(_FILE_MAP_READ, False, "RTSSSharedMemoryV2")
    if not handle:
        return None
    view = _k32.MapViewOfFile(handle, _FILE_MAP_READ, 0, 0, 0)
    if not view:
        _k32.CloseHandle(handle)
        return None
    try:
        if _u32(view) != _SIG:
            return None
        entry_size = _u32(view + 8)
        arr_off = _u32(view + 12)
        arr_size = _u32(view + 16)
        # 结构体字段要合理，否则宁可不读，避免显示乱数
        if not (64 <= entry_size <= _MAX_ENTRY_SIZE) or not (32 <= arr_off <= 65536):
            return None
        if not (0 < arr_size <= _MAX_ARR):
            return None

        now_state = {}
        best = None
        for i in range(arr_size):
            base = view + arr_off + i * entry_size
            pid = _u32(base)
            if pid in (0, 0xFFFFFFFF):
                continue
            name = ctypes.string_at(base + 4, 260).split(b"\x00")[0].decode("ascii", "replace")
            if not name or name.isascii() is False:
                continue
            frames = _u32(base + 276)
            t1 = _u32(base + 272)
            if frames == 0 or t1 == 0:
                continue
            now_state[pid] = (frames, t1)
            prev = _state["prev"].get(pid)
            if not prev:
                continue
            df = frames - prev[0]
            dt = t1 - prev[1]
            if dt <= 0 or df < 0:
                continue
            fps = df * 1000.0 / dt
            if 0 < fps < 2000 and (best is None or fps > best["fps"]):
                best = {"fps": round(fps, 1), "app": name, "pid": pid}
        _state["prev"] = now_state
        return best
    except Exception:
        return None
    finally:
        try:
            _k32.UnmapViewOfFile(view)
        except Exception:
            pass
        _k32.CloseHandle(handle)


if __name__ == "__main__":
    for _ in range(3):
        print(read_fps())
        time.sleep(1.0)
