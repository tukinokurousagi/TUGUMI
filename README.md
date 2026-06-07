# TUGUMI - 自律型AIエージェント

```
   ████████╗██╗   ██╗ ██████╗ ██╗   ██╗███╗   ███╗██╗
   ╚══██╔══╝██║   ██║██╔════╝ ██║   ██║████╗ ████║██║
      ██║   ██║   ██║██║  ███╗██║   ██║██╔████╔██║██║
      ██║   ██║   ██║██║   ██║██║   ██║██║╚██╔╝██║██║
      ██║   ╚██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║██║
      ╚═╝    ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝
```

## 概要

TUGUMIは、**LangGraph**、**LangChain**、**subprocess**を使用してローカルLLM (llama.cpp) を活用した、完全な**自律型AIエージェント**です。

AndroidのTermux環境でも実行でき、ユーザーの指示を受けただけで、自動的にタスクを理解・計画・実行・修正する、ビジネスシーンで今すぐ使える自己学習型エージェントです。

## 主な特徴

### 🎯 完全なエージェントループ実装

1. **目標理解**: ユーザーの指示から達成すべき目標を正確に把握
2. **計画立案**: 目標達成に必要なステップを自動分解
3. **ツール活用**: 適切なツールを選択・使用してタスク実行
4. **結果評価**: 実行結果を評価し、必要に応じて計画を修正
5. **適応的実行**: フィードバックを基に次のアクションを決定
6. **自己修正**: 失敗から自動的に学習して修正

### 🛠️ 複数のツール統合

- **Web検索**: DuckDuckGo (DDGS) による自動検索
- **スクレイピング**: URLからコンテンツを抽出・要約
- **パッケージ管理**: 必要なPythonライブラリの自動インストール
- **コマンド実行**: subprocess経由で外部ツールを実行
- **ログ・メモリ管理**: タスク履歴の自動記録と学習

### 📊 リアルタイムモニタリング

- **進捗状況の可視化**: 現在のタスク状態をリアルタイムで表示
- **ヘルスチェック機能**: LLMサーバーの状態を常時監視
- **タイムアウト対応**: 長時間推論のフリーズ検出
- **エラー自動リカバリー**: 最大3回までの自動修正試行

### 🧠 ローカルLLM連携

- **llama.cppサーバー**: http://0.0.0.0:8080 に接続
- **長時間推論対応**: タイムアウトなしで長い思考処理に対応
- **カスタマイズ可能**: パラメータ調整で推論を最適化

## システム構成

```
TUGUMI
├── TUGUMILogger          # ログ管理・ファイル記録
├── ProgressTracker       # 進捗状況・ヘルスチェック
├── ToolExecutor          # Web検索、スクレイピング、コマンド実行
├── LocalLLMInterface     # llama.cpp連携
├── TUGUMIAgent (Main)    # メインエージェント
│   ├── LangGraph         # 実行フロー管理
│   ├── AgentLoop         # 5フェーズループ
│   └── 自己修正機能      # 失敗からの学習
```

## インストール

### 必須要件

- Python 3.8以上
- llama.cpp サーバー (起動済み)
- Termux環境 (Android) または Linux/Mac

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone https://github.com/tukinokurousagi/TUGUMI.git
cd TUGUMI

# 2. セットアップスクリプトを実行
chmod +x setup.sh
./setup.sh

# 3. 仮想環境を有効化
source venv/bin/activate

# 4. llama.cpp サーバーを起動
./main -m model.gguf --host 0.0.0.0 --port 8080
```

## 使用方法

### 対話型モード (推奨)

```bash
python tugumi_main.py --interactive
```

```
TUGUMI> Pythonの最新トレンドについて調べて、結果をファイルに保存してください
実行中...
[進捗表示]
結果:
{
  "success": true,
  "task": "Pythonの最新トレンドについて調べて、結果をファイルに保存してください",
  "goal": "Pythonの最新トレンドを調査して、結果をテキストファイルに保存する",
  "result": "Pythonの最新トレンドについて調査し、約5000文字の記事を /storage/emulated/0/TUGUMIDesk/article_YYYYMMDD_HHMMSS.txt に保存しました。",
  "attempts": 1,
  "timestamp": "2026-06-07T12:30:00Z"
}
```

### コマンドラインでタスク指定

```bash
python tugumi_main.py --task "GitHubの最新情報をWeb検索して、結果をまとめてください"
```

### ステータス確認

```bash
python tugumi_main.py --status
```

```json
{
  "status": "executing",
  "task": "GitHubの最新情報をWeb検索して、結果をまとめてください",
  "subtask": "ステップ 2/5",
  "progress": 40,
  "timestamp": "2026-06-07T12:30:00Z"
}
```

## ファイル構成

```
TUGUMI/
├── tugumi_main.py              # メインエージェント実装
├── requirements.txt            # 依存パッケージリスト
├── setup.sh                    # Termux環境セットアップスクリプト
├── README.md                   # このファイル
├── .tugumi/
│   └── logs/
│       └── tugumi_YYYYMMDD_HHMMSS.log  # 実行ログ
└── ~/TUGUMIDesk/ (または /storage/emulated/0/TUGUMIDesk/)
    └── article_YYYYMMDD_HHMMSS.txt    # 保存した記事
    └── result_YYYYMMDD_HHMMSS.txt     # タスク実行結果
```

## エージェントループの詳細

### フェーズ1: 目標理解 (Understand Goal)

```
入力: ユーザーの指示
処理: LLMが指示を分析し、達成すべき明確な目標を定義
出力: 目標定義 (goal)
```

例:
```
指示: "GitHubの最新トレンドについて調べてください"
目標: "GitHub上での最新トレンド・人気リポジトリ・開発トレンドを調査し、ユーザーに提供する"
```

### フェーズ2: 計画立案 (Plan Task)

```
入力: 目標定義
処理: LLMが目標達成に必要なステップを自動分解
出力: 実行計画 (plan) - 複数のステップのリスト
```

例:
```
1. "GitHub検索"で最新トレンドを検索
2. "スクレイピング"で結果ページから詳細情報を抽出
3. "要約作成"で結果を整理
4. "ファイル保存"でテキストファイルに保存
```

### フェーズ3: ツール活用 (Execute Tool)

```
入力: 実行計画の各ステップ
処理: LLMがアクションを決定 → 適切なツールを実行
      - Web検索 (DDGS)
      - スクレイピング (BeautifulSoup)
      - パッケージインストール (pip)
      - コマンド実行 (subprocess)
出力: 実行結果
```

### フェーズ4: 結果評価 (Evaluate Result)

```
入力: 実行結果
処理: LLMが結果を評価 (成功/失敗、進捗状況など)
出力: 評価結果
```

### フェーズ5: 自己修正 (Self Correct)

```
条件: 失敗または進捗なしの場合 (最大3試行)
処理: LLMが失敗原因を分析し、修正されたアプローチを提案
出力: 修正計画
→ フェーズ3に戻って再実行
```

### フェーズ6: タスク完了 (Complete Task)

```
入力: 全ステップの実行結果
処理: LLMが最終結果をまとめる
出力: 完了報告 + 結果ファイル保存 + 学習情報記録
```

## ログとモニタリング

### ログ出力

```bash
# リアルタイムログ表示
tail -f ~/.tugumi/logs/tugumi_YYYYMMDD_HHMMSS.log
```

### ログ内容例

```
2026-06-07 12:30:00 - TUGUMI - INFO - タスク開始: Pythonの最新トレンドについて調べて...
2026-06-07 12:30:01 - TUGUMI - DEBUG - 目標理解フェーズ開始
2026-06-07 12:30:02 - TUGUMI - INFO - 目標定義完了: Pythonの最新トレンドを調査...
2026-06-07 12:30:03 - TUGUMI - DEBUG - 計画立案フェーズ開始
2026-06-07 12:30:04 - TUGUMI - INFO - 計画立案完了: 3ステップ
2026-06-07 12:30:05 - TUGUMI - DEBUG - ツール実行フェーズ開始
2026-06-07 12:30:06 - TUGUMI - INFO - ステップ 1 実行: Web検索
2026-06-07 12:30:07 - TUGUMI - DEBUG - Web検索開始: Python 2026 トレンド
2026-06-07 12:30:10 - TUGUMI - INFO - 検索完了: 5件
```

### 進捗状況のモニタリング

```python
# Pythonコードから進捗確認
agent = TUGUMIAgent()
status = agent.get_status()
print(status)
# => {
#      "status": "executing",
#      "progress": 60,
#      "task": "...",
#      "subtask": "ステップ 3/5"
#    }
```

## Termux環境でのセットアップ

### 前提条件

```bash
# Termux内で実行
pkg update
pkg install python3
pkg install python3-pip
pkg install git
```

### インストール

```bash
# llama.cpp をインストール
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make

# TUGUMIをクローン
cd ~
git clone https://github.com/tukinokurousagi/TUGUMI.git
cd TUGUMI

# セットアップ実行
chmod +x setup.sh
./setup.sh
```

### llama.cpp サーバー起動

```bash
# Termux内の別ウィンドウで実行
cd ~/llama.cpp
./main -m ~/models/model.gguf --host 0.0.0.0 --port 8080
```

### TUGUMI実行

```bash
source venv/bin/activate
python tugumi_main.py --interactive
```

## トラブルシューティング

### LLMサーバーに接続できない

```
エラー: LLMサーバーが応答しません
```

**原因**: llama.cppサーバーが起動していない

**対処**:
```bash
# サーバーが起動しているか確認
curl http://0.0.0.0:8080/health

# 起動していなければ起動
./llama.cpp/main -m model.gguf --host 0.0.0.0 --port 8080
```

### パッケージインストール失敗

```
エラー: パッケージインストール タイムアウト
```

**対処**:
```bash
# 手動でインストール
pip install beautifulsoup4
pip install requests
```

### ログファイルが見つからない

```bash
# ログディレクトリを確認
ls -la ~/.tugumi/logs/

# または
ls -la ~/TUGUMIDesk/
```

## パフォーマンスチューニング

### LLM推論時間を短縮

```python
# tugumi_main.py内で調整
payload = {
    "prompt": prompt,
    "n_predict": 256,        # ← トークン数を減らす
    "temperature": 0.5,      # ← 値を下げる (高速化)
    "top_p": 0.85            # ← 値を下げる (高速化)
}
```

### タイムアウト値を調整

```python
# 長い推論に対応
response = self.llm.generate(prompt, timeout=600)  # 10分に延長
```

## セキュリティ考慮事項

⚠️ **ローカル環境での使用を想定**

- LLMサーバーは認証なしで起動
- ネットワークに公開しないこと
- 機密情報を扱うタスクは慎重に

```bash
# ファイアウォール設定 (Linuxの例)
sudo ufw allow from 127.0.0.1 to 127.0.0.1 port 8080
```

## カスタマイズ例

### 新しいツールの追加

```python
class ToolExecutor:
    def translate_text(self, text: str, target_lang: str) -> str:
        """テキスト翻訳機能を追加"""
        try:
            # 翻訳処理
            self.logger.log("DEBUG", f"翻訳開始: {target_lang}")
            # ...
            return translated_text
        except Exception as e:
            self.logger.log("ERROR", f"翻訳失敗: {str(e)}")
            return ""
```

その後、`_execute_action`メソッドに処理を追加:

```python
elif "翻訳" in action_lower:
    text = self._extract_text(action)
    language = self._extract_language(action)
    result = self.tools.translate_text(text, language)
    return result
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## サポート

問題が発生した場合は、以下をご確認ください:

1. ログファイルの確認: `~/.tugumi/logs/`
2. llama.cppサーバーの状態確認
3. 依存パッケージの確認: `pip list`
4. ディスク容量の確認: `df -h`

## 今後の予定

- [ ] WebUIダッシュボード
- [ ] マルチスレッド化
- [ ] データベース統合 (SQLite)
- [ ] 音声入出力対応
- [ ] モデル切り替え機能
- [ ] APIサーバー化

---

**Version**: 1.0.0
**Last Updated**: 2026-06-07
**Maintained by**: tukinokurousagi
