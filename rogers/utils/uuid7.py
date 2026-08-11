"""UUIDv7 生成器（RFC 9562，Python 3.12 无内置 uuid7，自实现免依赖）。

UUIDv7 由 48bit 毫秒时间戳 + 版本位 + 随机位组成，按时间单调递增，
作为高频写入表的主键默认值可显著降低 B-tree 页分裂与索引碎片化
（替代随机 uuid4）。仅影响新增行，列类型仍为 UUID。
"""
import secrets
import time
from uuid import UUID


def uuid7() -> UUID:
    """生成一个按时间有序的 UUIDv7（RFC 9562）。

    布局：48bit 毫秒时间戳 | 4bit 版本(7) | 12bit rand_a | 2bit 变体(10) | 62bit rand_b。
    同一毫秒内由随机位区分，整体按时间毫秒级有序，足够降低 B-tree 碎片。
    """
    millis = int(time.time() * 1000)
    timestamp = millis & 0xFFFFFFFFFFFF
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (timestamp << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return UUID(int=value)