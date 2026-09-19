#!/usr/bin/env python3
"""
PhaseChangeDB 跨平台一键免配置启动器
===================================
任何用户从 GitHub 下载本仓库后，只需在终端执行：
    python run_demo.py

特性：
- 零外部依赖：无需安装 Docker、无需配置 MySQL、无需安装 Node.js/pnpm
- 自动检测：本地若有 MySQL 则连接真实数据库；若无则自动切换为内置科学演示数据集
- 内置前端：自动托管 app/static 预编译生产界面
- 自动打开浏览器：服务就绪后自动拉起默认浏览器访问 http://localhost:8000
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def check_python_version() -> None:
    if sys.version_info < (3, 11):  # noqa: UP036
        print(f"[错误] PhaseChangeDB 需要 Python 3.11 或更高版本，当前版本为 {sys.version}")
        sys.exit(1)


def check_dependencies() -> None:
    missing = []
    for pkg in ["fastapi", "uvicorn", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[提示] 检测到缺少必要运行依赖: {', '.join(missing)}")
        print("[提示] 正在自动安装轻量运行依赖 (pip install)...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "sqlalchemy", "starlette"])
            print("[✓] 依赖安装完成！\n")
        except Exception as e:
            print(f"[错误] 依赖自动安装失败: {e}")
            print(f"请手动在终端执行: pip install {' '.join(missing)} sqlalchemy starlette")
            sys.exit(1)


def is_mysql_available(host: str = "127.0.0.1", port: int = 3306, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def open_browser_delayed(url: str, delay_seconds: float = 1.2) -> None:
    def _open():
        time.sleep(delay_seconds)
        print(f"\n[🚀 浏览器直达] 正在自动为您打开界面: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def main() -> None:
    check_python_version()

    print("=" * 66)
    print("      PhaseChangeDB 相变材料科学数据与发现平台 (一键启动器)     ")
    print("=" * 66)

    root_dir = Path(__file__).resolve().parent
    os.chdir(root_dir)
    sys.path.insert(0, str(root_dir))

    check_dependencies()

    static_dir = root_dir / "app" / "static"
    if not (static_dir / "index.html").is_file():
        print(f"[警告] 未在 {static_dir} 检测到预编译前端，将仅以纯 API 模式运行。")
    else:
        print("[✓] 前端预编译界面就绪 (app/static - 零 Node.js 依赖)")

    # 检测数据库
    if is_mysql_available():
        print("[✓] 检测到本地 MySQL 8.4 数据库服务运行正常，使用真实数据库。")
        os.environ.setdefault("PCM_DEMO_MODE", "0")
    else:
        print("[ℹ] 未检测到本地 MySQL 服务，已自动启动【内置科学演示模式 (Demo Mode)】。")
        print("    内置包含真实的 GeTe / Sb2Te3 物性数据点、3D 知识图谱与箱线对比看板，免配置直接体验！")
        os.environ["PCM_DEMO_MODE"] = "1"

    host = "127.0.0.1"
    port = 8000
    target_url = f"http://{host}:{port}"

    open_browser_delayed(target_url, delay_seconds=1.5)

    import uvicorn

    print(f"\n[⚡ 服务启动] 访问地址: {target_url}")
    print("[提示] 按 Ctrl+C 可安全停止服务。\n")

    try:
        uvicorn.run("app.main:app", host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n\n[👋 已停止] PhaseChangeDB 服务已退出，感谢使用！")


if __name__ == "__main__":
    main()
