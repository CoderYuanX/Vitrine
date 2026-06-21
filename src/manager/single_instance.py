import fcntl
from pathlib import Path

_lock_fp = None


def acquire(name="deepin-widgets"):
    """获取单实例锁,成功返回 True;已有实例在跑返回 False。"""
    global _lock_fp
    p = Path.home() / ".config" / "deepin-widgets" / f".{name}.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    _lock_fp = open(p, "w")
    try:
        fcntl.flock(_lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        _lock_fp.close()
        _lock_fp = None
        return False
