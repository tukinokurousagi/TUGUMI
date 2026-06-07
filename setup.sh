#!/bin/bash
# TUGUMI セットアップスクリプト - Termux環境用

echo "=========================================="
echo "TUGUMI - 自律型AIエージェント"
echo "セットアップスクリプト"
echo "=========================================="
echo ""

# Python環境確認
echo "1️⃣ Python環境を確認しています..."
if ! command -v python3 &> /dev/null; then
    echo "✗ Python3が見つかりません。インストールしてください。"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"
echo ""

# 仮想環境作成
echo "2️⃣ 仮想環境を作成しています..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ 仮想環境を作成しました"
else
    echo "✓ 仮想環境が既に存在します"
fi
echo ""

# 仮想環境を有効化
echo "3️⃣ 仮想環境を有効化しています..."
source venv/bin/activate
echo "✓ 仮想環境を有効化しました"
echo ""

# 依存パッケージをインストール
echo "4️⃣ 依存パッケージをインストール中（時間がかかります）..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ 依存パッケージのインストールが完了しました"
else
    echo "✗ パッケージインストールに失敗しました"
    exit 1
fi
echo ""

# ディレクトリ作成
echo "5️⃣ 必要なディレクトリを作成しています..."
mkdir -p ~/.tugumi/logs
mkdir -p /storage/emulated/0/TUGUMIDesk 2>/dev/null || mkdir -p ~/TUGUMIDesk
echo "✓ ディレクトリを作成しました"
echo ""

# llama.cpp サーバー確認
echo "6️⃣ llama.cpp サーバーを確認しています..."
if curl -s http://0.0.0.0:8080/health > /dev/null 2>&1; then
    echo "✓ LLMサーバーが起動しています"
else
    echo "⚠️  LLMサーバーが起動していません"
    echo "   以下のコマンドでllama.cppサーバーを起動してください:"
    echo "   ./main -m model.gguf --host 0.0.0.0 --port 8080"
fi
echo ""

echo "=========================================="
echo "✓ セットアップが完了しました"
echo "=========================================="
echo ""
echo "【使用方法】"
echo ""
echo "1. 仮想環境を有効化:"
echo "   source venv/bin/activate"
echo ""
echo "2. 対話型モードで実行:"
echo "   python tugumi_agent.py --interactive"
echo ""
echo "3. タスクを指定して実行:"
echo "   python tugumi_agent.py --task \"タスク内容\""
echo ""
echo "4. ステータス確認:"
echo "   python tugumi_agent.py --status"
echo ""
echo "【ログとデータの保存先】"
echo "  ログ: ~/.tugumi/logs/"
echo "  データ: ~/TUGUMIDesk/ (または /storage/emulated/0/TUGUMIDesk/)"
echo ""
