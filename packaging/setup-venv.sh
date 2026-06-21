#!/bin/sh
# 在 /opt/vitrine 下创建虚拟环境并安装运行依赖(需联网,约 50–80MB)。
# 由 thin 包的 postinst 调用,也可在依赖安装失败后手动重跑修复。
set -e
PREFIX=/opt/vitrine

echo "Vitrine:创建虚拟环境并安装依赖(PySide6-Essentials / psutil / requests / python-xlib)…"
python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
"$PREFIX/venv/bin/pip" install \
  "PySide6-Essentials>=6.6" "psutil>=5.9" "requests>=2.31" "python-xlib>=0.33"

# 瘦身:运行期不需要 pip/setuptools
"$PREFIX/venv/bin/pip" uninstall -y pip setuptools wheel >/dev/null 2>&1 || true
find "$PREFIX/venv" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "Vitrine:依赖安装完成。"
