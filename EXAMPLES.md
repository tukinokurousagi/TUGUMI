# TUGUMI 使用例集

## 例1: Web検索と記事保存

```bash
python tugumi_main.py --task "Python 3.12の新機能について最新情報を検索して、詳しくまとめてから結果をファイルに保存してください"
```

**出力結果例**:
```json
{
  "success": true,
  "task": "Python 3.12の新機能について最新情報を検索して、詳しくまとめてから結果をファイルに保存してください",
  "goal": "Python 3.12の新機能をWeb検索で調査し、詳細な情報をテキストファイルに保存する",
  "result": "Python 3.12の最新機能情報を5つの信頼できるソースから収集し、約3000文字の詳細な記事として ~/TUGUMIDesk/article_20260607_123000.txt に保存しました。主な新機能: Per-Interpreter GIL、Type Parameter Syntax、Override Decorators、f-string improvements等が含まれます。",
  "attempts": 1,
  "timestamp": "2026-06-07T12:30:00Z"
}
```

保存されたファイル (`article_20260607_123000.txt`):
```
Title: Python 3.12の新機能
Saved: 2026-06-07T12:30:00Z
============================================================

Python 3.12は2023年10月にリリースされました...
[5000文字の詳細な記事内容]
```

---

## 例2: 技術調査と学習

```bash
python tugumi_main.py --interactive
TUGUMI> LangGraphを初心者向けにわかりやすく説明して、実装例を含めてまとめてください
```

**エージェントの実行フロー**:

```
[フェーズ1] 目標理解
  → LLMが指示を分析: "LangGraphについてのわかりやすい説明と実装例をまとめる"

[フェーズ2] 計画立案
  1. LangGraphの基本概念をWeb検索
  2. 公式ドキュメントをスクレイピング
  3. 実装例をGitHubから検索
  4. 初心者向けの説明を作成
  5. 実装例を構成
  6. 最終的なまとめを作成

[フェーズ3-5] ツール活用と評価
  ✓ ステップ1: Web検索 → 5件の検索結果
  ✓ ステップ2: スクレイピング → 公式ドキュメント取得
  ✓ ステップ3: GitHub検索 → 複数の実装例発見
  ✓ ステップ4: LLM処理 → 説明文作成
  ✓ ステップ5: LLM処理 → 実装例生成
  ✓ ステップ6: LLM処理 → まとめ作成

[フェーズ6] 完了
  → ファイル保存完了
  → 学習情報を記録

結果:
{
  "success": true,
  "result": "LangGraphについてのわかりやすい初心者向け解説と、実装例を含めた約4000文字のドキュメントを作成・保存しました。NodeとEdgeの概念、StateGraph、ConditionalEdges等の各要素について、コード例を交えて説明しました。",
  "attempts": 1
}
```

---

## 例3: エラーハンドリングと自動修正

```bash
python tugumi_main.py --task "最新のAI/ML技術トレンドについてMarkdown形式でレポートを作成してください"
```

**実行中にエラーが発生した場合**:

```
[フェーズ3] ツール実行
  ステップ 3/4: "Markdown形式でのレポート作成" 実行
  → アクション: "markdown-itのインストール"
  
  ✗ エラー: パッケージ不在

[フェーズ4] 結果評価
  評価: "失敗 - 必要なパッケージが見つかりません"

[フェーズ5] 自己修正 (試行 1/3)
  修正提案: "BeautifulSoupを使用してHTML→Markdownに変換"
  → ステップを修正して再実行

  ✓ 成功: HTML記事をMarkdownに変換
  
結果:
{
  "success": true,
  "result": "AI/ML技術トレンドについてのMarkdownレポートを作成・保存しました。3つの主要トレンド（LLM、Diffusion Models、AutoML）について詳細に記述しました。",
  "attempts": 2  # 2回目で成功
}
```

---

## 例4: 複合的なタスク実行

```bash
python tugumi_main.py --task "
1. GitHubのトレンドリポジトリを調査
2. 最新のPythonライブラリを3つピックアップ
3. 各ライブラリについて、機能・使用例・インストール方法をまとめる
4. 比較表を作成
5. 推奨事項を記述
最終結果をファイルに保存してください
"
```

**実行結果**:
```
進捗: 5フェーズを自動実行
- フェーズ1: 複合タスクを5つのサブタスクに分解
- フェーズ2: 各サブタスクの実行計画を立案
- フェーズ3-5: 順次実行と評価
- フェーズ6: 最終レポート作成

最終ファイル (`result_20260607_124500.txt`):
```
Task: 複合的なPythonライブラリ調査レポート
Goal: 最新Pythonライブラリを調査・比較・推奨

【トレンドリポジトリ】
- Repository A: 5000+ stars
- Repository B: 3000+ stars  
- Repository C: 2000+ stars

【ライブラリ比較表】
┌─────────────┬──────────┬─────────┬──────────┐
│ ライブラリ   │ 機能      │ 難易度  │ 推奨度  │
├─────────────┼──────────┼─────────┼──────────┤
│ Library 1   │ ✓✓✓     │ ⭐⭐   │ ⭐⭐⭐  │
│ Library 2   │ ✓✓      │ ⭐⭐⭐ │ ⭐⭐   │
│ Library 3   │ ✓✓✓✓    │ ⭐⭐⭐ │ ⭐⭐⭐  │
└─────────────┴──────────┴─────────┴──────────┘

【推奨事項】
新規プロジェクトではLibrary 1, 3を推奨...
```

---

## 例5: 対話型モードでの段階的タスク実行

```bash
python tugumi_main.py --interactive
```

**セッション例**:

```
TUGUMI> status
状態: {
  "status": "idle",
  "progress": 0,
  "task": "",
  "subtask": ""
}

TUGUMI> 今月のAIニュースを3つまとめてください
実行中...
[進捗: 25%] Web検索中
[進捗: 50%] スクレイピング中
[進捗: 75%] 要約作成中
[進捗: 100%] ファイル保存中

完了しました！

TUGUMI> status
状態: {
  "status": "completed",
  "progress": 100,
  "result": "AIニュースを3件抽出しました"
}

TUGUMI> 前回の結果ファイルをもっと詳しく拡張してください
実行中...
[メモリから学習情報を取得]
[前回のファイルを参照して拡張]

完了しました！

TUGUMI> exit
ご利用ありがとうございました。
```

---

## 例6: スクリプトでの定期実行

**cron設定例** (`crontab -e`):

```bash
# 毎日午前6時に実行
0 6 * * * cd ~/TUGUMI && source venv/bin/activate && python tugumi_main.py --task "今日のTech News Top 3をまとめてください" >> /home/user/tugumi_daily_tasks.log 2>&1
```

**Pythonコードでの実行**:

```python
#!/usr/bin/env python3
from tugumi_main import TUGUMIAgent

# エージェント初期化
agent = TUGUMIAgent()

# 複数タスクを順次実行
tasks = [
    "GitHubの今日のトレンドをまとめてください",
    "Rustプログラミングの最新情報をまとめてください",
    "クラウドコンピューティングのニュースをまとめてください"
]

for task in tasks:
    print(f"\n{'='*60}")
    print(f"実行中: {task}")
    print('='*60)
    
    result = agent.execute_task(task)
    
    print(f"結果: {'成功' if result['success'] else '失敗'}")
    if result['success']:
        print(f"試行回数: {result['attempts']}")
    else:
        print(f"エラー: {result.get('error', '不明')}")
```

---

## 例7: カスタムプロンプトの使用

```python
from tugumi_main import TUGUMIAgent

agent = TUGUMIAgent()

# カスタム指示での実行
custom_task = """
以下の要件に従ってタスクを実行してください:

【要件】
1. 信頼できるソースのみを使用
2. 各情報に必ずURLを記載
3. 箇条書き形式で整理
4. 日本語で統一

【タスク】
ブロックチェーン技術の2024年度の発展と予測をまとめてください
"""

result = agent.execute_task(custom_task)
print(result['result'])
```

---

## 例8: エラーからの自動リカバリー

```
TUGUMI> "This is an error scenario"について調べてください
実行中...

[試行1] Web検索実行 → タイムアウト ✗
  修正提案: キーワードを簡潔に変更

[試行2] Web検索実行: "error handling" → 成功 ✓
  結果: 8件の検索結果

[試行3] スクレイピング → 接続エラー ✗
  修正提案: キャッシュされた結果から要約を作成

[試行4] LLM生成 → 成功 ✓
  結果: 詳細なサマリーを生成

完了しました！
```

---

## パフォーマンス最適化例

### 高速モード（推論時間短縮）

```python
# tugumi_main.py内で以下に変更
payload = {
    "prompt": prompt,
    "n_predict": 256,      # 512 → 256
    "temperature": 0.3,    # 0.7 → 0.3 (より決定的)
    "top_p": 0.80,         # 0.95 → 0.80
    "repeat_penalty": 1.05
}
```

### 詳細モード（より詳細な回答）

```python
# tugumi_main.py内で以下に変更
payload = {
    "prompt": prompt,
    "n_predict": 1024,     # 512 → 1024
    "temperature": 0.9,    # 0.7 → 0.9 (より創造的)
    "top_p": 0.98,         # 0.95 → 0.98
    "top_k": 50            # 40 → 50
}
```

---

## トラブルシューティング例

### 問題: タスクが途中で止まる

```bash
# ログを確認
tail -f ~/.tugumi/logs/tugumi_*.log

# 出力例:
# 2026-06-07 12:30:15 - TUGUMI - ERROR - LLM生成タイムアウト (>60秒)

# 対処: タイムアウト値を増やす
# tugumi_main.py内で: timeout=120 に変更
```

### 問題: メモリ不足

```bash
# メモリ状況確認
free -h

# キャッシュをクリア
sync; echo 3 > /proc/sys/vm/drop_caches

# LLMモデルを軽量版に変更
# llama.cpp起動時: ./main -m model-smaller.gguf
```

### 問題: ネットワークエラー

```bash
# インターネット接続確認
ping -c 3 8.8.8.8

# DNSを変更
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```

---

## ベストプラクティス

1. **長いタスクは明確に分解**
   - エージェントが理解しやすい指示を与える
   - 最大5-6個のステップに分割

2. **信頼できるソースを指定**
   - "信頼できるソースから"と指示を追加
   - 公式ドキュメント、学術論文などを明示

3. **ファイル形式を指定**
   - "Markdown形式で"
   - "JSONフォーマットで"
   - "表形式で"

4. **定期的にログを確認**
   - エージェントの判断を学習・改善
   - パフォーマンス最適化

5. **段階的なテスト**
   - 簡単なタスクから始める
   - 複雑なタスクは複数に分割

---

**Last Updated**: 2026-06-07
**Examples Version**: 1.0.0
