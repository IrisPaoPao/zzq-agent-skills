#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 开始安装 bsq-sql-organize CLI..."

if command -v pipx &> /dev/null; then
    echo "📦 发现 pipx，正在使用 pipx 安装..."
    pipx install -e . --force
    echo "✅ 安装完成！您现在可以在终端任意位置直接运行 'bsq-sql-organize' 了。"
else
    echo "📦 正在使用 pip 安装..."
    python3 -m pip install -e .
    echo "✅ 安装完成！您现在可以在终端任意位置直接运行 'bsq-sql-organize' 了。"
fi
