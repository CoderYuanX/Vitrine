# managewidgets

桌面小组件管理器(第一版:数据底座 + 管理面板)。X11 优先,GTK3。

## 系统依赖(PyGObject 无法用 pip 装,需系统包)
    # Debian/Deepin 系:
    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1

## 安装(其余依赖装进 venv)
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install psutil websockets tomli-w pytest

## 运行
    .venv/bin/python -m core       # 底座
    .venv/bin/python -m manager    # 面板

## 测试
    .venv/bin/python -m pytest -v
