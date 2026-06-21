import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from manager.single_instance import acquire  # noqa: E402
from manager.app import WidgetHost  # noqa: E402

if __name__ == "__main__":
    if not acquire():
        print("桌面小组件已在运行(单实例),不重复启动。", file=sys.stderr)
        sys.exit(0)
    sys.exit(WidgetHost().run())
