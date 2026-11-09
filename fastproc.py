# -*- coding: utf-8 -*-
"""用一次 NtQuerySystemInformation 拿到全部进程的 CPU 时间与工作集。

逐进程 OpenProcess 在本机要 ~3.5ms/个（杀软/反外挂驱动会拦截），
364 个进程就要 2.7 秒；这里改成一次内核查询，通常 10~30ms。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
_ntdll.NtQuerySystemInformation.argtypes = [
    ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)
]
_ntdll.NtQuerySystemInformation.restype = ctypes.c_long

_SYSTEM_PROCESS_INFORMATION = 5
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
# 结构体字段偏移（x64）
_OFF_NEXT = 0x00
_OFF_PRIVATE_WS = 0x08
_OFF_USER_TIME = 0x28
_OFF_KERNEL_TIME = 0x30
_OFF_NAME_LEN = 0x38
_OFF_NAME_PTR = 0x40
_OFF_PID = 0x50


def _query() -> tuple[ctypes.Array, int]:
    size = 1 << 21
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        need = ctypes.c_ulong(0)
        status = _ntdll.NtQuerySystemInformation(
            _SYSTEM_PROCESS_INFORMATION, buf, size, ctypes.byref(need)
        )
        code = status & 0xFFFFFFFF
        if code == 0:
            return buf, size
        if code == _STATUS_INFO_LENGTH_MISMATCH:
            size = max(need.value + (1 << 16), size * 2)
            continue
        raise OSError(f"NtQuerySystemInformation 失败: 0x{code:08X}")
    raise OSError("NtQuerySystemInformation 缓冲区始终不足")


def list_processes() -> list[dict]:
    """返回 [{pid, name, ws, cpu}]，cpu 为 user+kernel 的 100ns 累计值。"""
    buf, _size = _query()
    base = ctypes.addressof(buf)
    out: list[dict] = []
    off = 0
    while True:
        nxt = ctypes.c_ulong.from_address(base + off + _OFF_NEXT).value
        pid = ctypes.c_void_p.from_address(base + off + _OFF_PID).value or 0
        user = ctypes.c_longlong.from_address(base + off + _OFF_USER_TIME).value
        kern = ctypes.c_longlong.from_address(base + off + _OFF_KERNEL_TIME).value
        ws = ctypes.c_longlong.from_address(base + off + _OFF_PRIVATE_WS).value
        nlen = ctypes.c_ushort.from_address(base + off + _OFF_NAME_LEN).value
        nptr = ctypes.c_void_p.from_address(base + off + _OFF_NAME_PTR).value
        if pid and nptr and nlen:
            try:
                name = ctypes.wstring_at(nptr, nlen // 2)
            except Exception:
                name = ""
        else:
            name = "Idle" if pid == 0 else ""
        if pid:
            out.append({"pid": int(pid), "name": name, "ws": int(ws), "cpu": int(user + kern)})
        if nxt == 0:
            break
        off += nxt
    return out


if __name__ == "__main__":  # 自测：与 psutil 对照
    import sys
    import time

    sys.path.insert(0, r"D:\手机监控电脑性能看板\libs")
    import psutil

    t0 = time.process_time()
    mine = list_processes()
    cost = (time.process_time() - t0) * 1000
    print(f"一次查询耗时: {cost:.1f} ms，进程数 {len(mine)}")

    ref = {p.info["pid"]: p.info["name"] for p in psutil.process_iter(["pid", "name"])}
    m = {x["pid"]: x["name"] for x in mine}
    missing = set(ref) - set(m)
    extra = set(m) - set(ref)
    print(f"psutil 进程数: {len(ref)}   差异: 少 {len(missing)} 多 {len(extra)}")
    if missing:
        print("  少:", [(p, ref[p]) for p in list(missing)[:5]])
    bad = [(p, ref[p], m[p]) for p in set(ref) & set(m) if ref[p] and ref[p].lower() != m[p].lower()]
    print(f"名称不一致: {len(bad)}", bad[:3] if bad else "")

    big = sorted(mine, key=lambda x: -x["ws"])[:5]
    print("\n工作集最大的 5 个：")
    for x in big:
        print(f"  {x['name'][:28]:<28} ws={x['ws'] / 1048576:7.1f} MB  cpu={x['cpu'] / 1e7:8.1f} s")
