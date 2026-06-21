#!/usr/bin/env bash
# 构建自包含 .deb:把 app + 一个含 PySide6-Essentials 的 venv 装进 /opt/vitrine。
# 用法: packaging/build-deb.sh [版本号]   (默认 0.1.0)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
VERSION="${1:-0.1.0}"
ARCH="$(dpkg --print-architecture)"
PKG="vitrine"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
DEST="$STAGE/opt/vitrine"

echo "==> 准备目录结构"
mkdir -p "$DEST" "$STAGE/DEBIAN" "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps"

echo "==> 拷贝应用源码"
cp -r "$ROOT/main.py" "$ROOT/src" "$ROOT/ui" "$ROOT/widgets" "$ROOT/requirements.txt" "$DEST/"
# 去掉源码里的 __pycache__
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> 创建虚拟环境并安装依赖(PySide6-Essentials + psutil + requests + python-xlib)"
python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install --upgrade pip >/dev/null
"$DEST/venv/bin/pip" install \
  "PySide6-Essentials>=6.6" "psutil>=5.9" "requests>=2.31" "python-xlib>=0.33"

echo "==> 瘦身 venv(移除 pip/setuptools/缓存,运行期不需要)"
"$DEST/venv/bin/pip" uninstall -y pip setuptools wheel >/dev/null 2>&1 || true
find "$DEST/venv" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEST/venv" -name '*.dist-info' -path '*pip*' -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> 安装启动器 / desktop / 图标"
install -m755 "$HERE/vitrine.launcher" "$STAGE/usr/bin/vitrine"
install -m644 "$HERE/vitrine.desktop" "$STAGE/usr/share/applications/vitrine.desktop"
install -m644 "$HERE/vitrine.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/vitrine.svg"

echo "==> 生成 DEBIAN/control"
SIZE="$(du -sk "$STAGE" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" -e "s/@ARCH@/$ARCH/" -e "s/@SIZE@/$SIZE/" \
  "$HERE/control.template" > "$STAGE/DEBIAN/control"

# 安装后刷新桌面/图标缓存(非致命)
cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
[ -x "$(command -v update-desktop-database)" ] && update-desktop-database -q /usr/share/applications || true
[ -x "$(command -v gtk-update-icon-cache)" ] && gtk-update-icon-cache -qtf /usr/share/icons/hicolor || true
exit 0
POSTINST
chmod 755 "$STAGE/DEBIAN/postinst"

echo "==> 构建 deb"
mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
echo ""
echo "✅ 构建完成: $OUT"
dpkg-deb --info "$OUT" | sed 's/^/   /'
echo "   安装: sudo apt install $OUT   (或 sudo dpkg -i $OUT && sudo apt -f install)"
