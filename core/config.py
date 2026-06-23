import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import tomllib
import tomli_w

logger = logging.getLogger(__name__)

DEFAULT_PORT = 35355
INTERVAL_MIN = 0.5
INTERVAL_MAX = 3600.0


# 说明:自启状态以 XDG `~/.config/autostart/*.desktop` 文件为单一事实来源(见 Task 11),
# 不在 config.toml 里重复保存,避免两处状态不一致(与 spec §3.6 一致)。
@dataclass
class Config:
    port: int = DEFAULT_PORT
    providers_enabled: dict[str, bool] = field(default_factory=lambda: {"system": True, "time": True})
    intervals: dict[str, float] = field(default_factory=dict)   # topic -> 覆盖间隔;缺省走 provider 默认

    @classmethod
    def default(cls) -> "Config":
        return cls()

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "providers_enabled": self.providers_enabled,
            "intervals": self.intervals,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        base = cls.default()
        return cls(
            port=int(d.get("port", base.port)),
            providers_enabled={**base.providers_enabled, **d.get("providers_enabled", {})},
            intervals={str(k): float(v) for k, v in d.get("intervals", {}).items()},
        )


def default_config_path() -> Path:
    return Path.home() / ".config" / "managewidgets" / "config.toml"


def load_config(path: Path) -> tuple[Config, list[dict]]:
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        return Config.from_dict(data), []
    except FileNotFoundError:
        return Config.default(), []
    except (tomllib.TOMLDecodeError, ValueError, OSError):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = path.with_name(f"{path.name}.bak.{ts}")
        try:
            path.rename(backup)
        except OSError:
            backup = None
        notice = {
            "code": "config_reset",
            "message": f"配置文件损坏,已重置;原文件备份为 {backup.name if backup else '(备份失败)'}",
        }
        logger.warning("config corrupt, reset; backup=%s",
                       backup.name if backup else "(backup failed)")
        return Config.default(), [notice]


def save_config(cfg: Config, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tomli_w.dumps(cfg.to_dict()).encode("utf-8"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
