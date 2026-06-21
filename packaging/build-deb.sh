#!/usr/bin/env bash
# 构建 Vitrine 的 .deb。
#
#   packaging/build-deb.sh [版本号]            自包含:打包时把 venv(含 PySide6)装进 /opt/vitrine
#   packaging/build-deb.sh --thin [版本号]     瘦包:不带 venv,postinst 联网 pip 安装依赖
#
# 默认版本 0.1.0。产物在 dist/。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

THIN=0
if [ "${1:-}" = "--thin" ]; then THIN=1; shift; fi
VERSION="${1:-0.1.0}"
ARCH="$(dpkg --print-architecture)"
PKG="vitrine"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
DEST="$STAGE/opt/vitrine"

echo "==> 准备目录结构 (mode=$([ $THIN -eq 1 ] && echo thin || echo bundled))"
mkdir -p "$DEST" "$STAGE/DEBIAN" "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps"

echo "==> 拷贝应用源码"
cp -r "$ROOT/main.py" "$ROOT/src" "$ROOT/ui" "$ROOT/widgets" "$ROOT/requirements.txt" "$DEST/"
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

if [ "$THIN" -eq 1 ]; then
  echo "==> thin:仅放置 setup-venv.sh(依赖在安装时联网 pip 拉取)"
  install -m755 "$HERE/setup-venv.sh" "$DEST/setup-venv.sh"
  CONTROL_TPL="$HERE/control-thin.template"
else
  echo "==> bundled:创建虚拟环境并安装依赖(PySide6-Essentials + psutil + requests + python-xlib)"
  python3 -m venv "$DEST/venv"
  "$DEST/venv/bin/pip" install --upgrade pip >/dev/null
  "$DEST/venv/bin/pip" install \
    "PySide6-Essentials>=6.6" "psutil>=5.9" "requests>=2.31" "python-xlib>=0.33"
  echo "==> 瘦身 venv(移除 pip/setuptools/缓存)"
  "$DEST/venv/bin/pip" uninstall -y pip setuptools wheel >/dev/null 2>&1 || true
  find "$DEST/venv" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  CONTROL_TPL="$HERE/control.template"
fi

echo "==> 安装启动器 / desktop / 图标"
install -m755 "$HERE/vitrine.launcher" "$STAGE/usr/bin/vitrine"
install -m644 "$HERE/vitrine.desktop" "$STAGE/usr/share/applications/vitrine.desktop"
install -m644 "$HERE/vitrine.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/vitrine.svg"

echo "==> 生成 DEBIAN/control"
SIZE="$(du -sk "$STAGE" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" -e "s/@ARCH@/$ARCH/" -e "s/@SIZE@/$SIZE/" \
  "$CONTROL_TPL" > "$STAGE/DEBIAN/control"

# 安装后:刷新桌面/图标缓存;thin 模式额外联网建 venv
{
  echo "#!/bin/sh"
  echo "set -e"
  if [ "$THIN" -eq 1 ]; then
    echo 'if [ ! -x /opt/vitrine/venv/bin/python ]; then'
    echo '  sh /opt/vitrine/setup-venv.sh || echo "Vitrine:依赖安装失败(可能无网络)。联网后执行 sudo /opt/vitrine/setup-venv.sh 重试。" >&2'
    echo 'fi'
  fi
  echo '[ -x "$(command -v update-desktop-database)" ] && update-desktop-database -q /usr/share/applications || true'
  echo '[ -x "$(command -v gtk-update-icon-cache)" ] && gtk-update-icon-cache -qtf /usr/share/icons/hicolor || true'
  echo "exit 0"
} > "$STAGE/DEBIAN/postinst"
chmod 755 "$STAGE/DEBIAN/postinst"

# 卸载前:thin 模式删除 postinst 建的 venv(dpkg 不跟踪它)
if [ "$THIN" -eq 1 ]; then
  cat > "$STAGE/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
rm -rf /opt/vitrine/venv
exit 0
PRERM
  chmod 755 "$STAGE/DEBIAN/prerm"
fi

echo "==> 构建 deb"
mkdir -p "$ROOT/dist"
SUFFIX=$([ "$THIN" -eq 1 ] && echo "-thin" || echo "")
OUT="$ROOT/dist/${PKG}_${VERSION}${SUFFIX}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
echo ""
echo "✅ 构建完成: $OUT"
ls -lh "$OUT" | awk '{print "   deb 大小:", $5}'
echo "   安装: sudo apt install $OUT"
[ "$THIN" -eq 1 ] && echo "   注意:thin 包安装时会联网用 pip 拉取 PySide6(约 50-80MB)。"
