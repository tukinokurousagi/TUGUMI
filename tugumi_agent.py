#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TUGUMI - 自律型AIエージェント
Autonomous AI Agent using LangGraph, LangChain, and local LLM via llama.cpp

実装詳細:
- LangGraph: タスク実行フローの管理
- LangChain: LLM統合とプロンプト処理
- subprocess: 外部ツール/パッケージの実行管理
- ローカルLLM: llama.cppサーバー (http://0.0.0.0:8080)

エージェントループ:
1. 目標理解: ユーザー指示の分析
2. 計画立案: タスクの分解とステップ化
3. ツール活用: 検索、スクレイピング、コマンド実行
4. 結果評価: 実行結果の検証
5. 自己修正: エラーからの学習と修正
"""

import os
import sys
import json
import time
import subprocess
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import threading
import queue

# LangChain & LangGraph
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph
from typing import TypedDict

# ツール
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup


class TaskStatus(Enum):
    """タスク実行状態"""
    IDLE = "idle"
    RUNNING = "running"
    THINKING = "thinking"
    SEARCHING = "searching"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class TUGUMILogger:
    """TUGUMI専用ロガー - ログ出力とファイル記録"""
    
    def __init__(self):
        self.log_dir = Path.home() / ".tugumi" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # データディレクトリ設定
        if os.path.exists("/storage/emulated/0"):
            self.data_dir = Path("/storage/emulated/0/TUGUMIDesk")
        else:
            self.data_dir = Path.home() / "TUGUMIDesk"
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # ログファイル設定
        log_file = self.log_dir / f"tugumi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TUGUMI")
        
        # 起動ログ
        self.logger.info("=" * 70)
        self.logger.info("TUGUMI Agent Started - 自律型AIエージェント起動")
        self.logger.info(f"Log Directory: {log_file}")
        self.logger.info(f"Data Directory: {self.data_dir}")
        self.logger.info("=" * 70)
    
    def log(self, level: str, message: str):
        """ログレベルに応じてログを記録"""
        level = level.upper()
        if level == "INFO":
            self.logger.info(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "DEBUG":
            self.logger.debug(message)
        elif level == "CRITICAL":
            self.logger.critical(message)


class ProgressTracker:
    """進捗状況・ヘルスチェック - リアルタイム監視"""
    
    def __init__(self):
        self.current_status = TaskStatus.IDLE
        self.current_task = ""
        self.subtask = ""
        self.progress_percentage = 0
        self.lock = threading.Lock()
        self.status_history = []
        self.last_update = datetime.now()
        self.frozen_check_threshold = 30  # 秒
    
    def update(self, status: TaskStatus, task: str = "", subtask: str = "", progress: int = 0):
        """進捗状況を更新"""
        with self.lock:
            self.current_status = status
            self.current_task = task
            self.subtask = subtask
            self.progress_percentage = min(progress, 100)
            self.last_update = datetime.now()
            
            status_entry = {
                "timestamp": self.last_update.isoformat(),
                "status": status.value,
                "task": task,
                "subtask": subtask,
                "progress": progress
            }
            self.status_history.append(status_entry)
            
            # 最新100件のみ保持
            if len(self.status_history) > 100:
                self.status_history = self.status_history[-100:]
    
    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        with self.lock:
            is_frozen = False
            seconds_since_update = (datetime.now() - self.last_update).total_seconds()
            
            if (self.current_status == TaskStatus.RUNNING or 
                self.current_status == TaskStatus.EXECUTING or
                self.current_status == TaskStatus.THINKING) and \
                seconds_since_update > self.frozen_check_threshold:
                is_frozen = True
            
            return {
                "status": self.current_status.value,
                "task": self.current_task,
                "subtask": self.subtask,
                "progress": self.progress_percentage,
                "timestamp": datetime.now().isoformat(),
                "last_update_seconds_ago": seconds_since_update,
                "is_frozen": is_frozen,
                "history_length": len(self.status_history)
            }


class AgentState(TypedDict):
    """LangGraph エージェント状態"""
    task: str
    goal: str
    plan: List[str]
    current_step: int
    tool_results: Dict[str, Any]
    observations: List[str]
    final_result: Optional[str]
    error_log: List[str]
    attempts: int
    max_attempts: int


class ToolExecutor:
    """ツール実行エンジン - 複数のツールをサポート"""
    
    def __init__(self, logger: TUGUMILogger, progress: ProgressTracker):
        self.logger = logger
        self.progress = progress
        self.ddgs = DDGS()
        self.data_dir = logger.data_dir
    
    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Web検索 (DuckDuckGo) - 自動で必要な知識を検索"""
        self.logger.log("DEBUG", f"🔍 Web検索開始: {query}")
        self.progress.update(TaskStatus.SEARCHING, subtask=f"Web検索: {query[:30]}")
        
        try:
            results = self.ddgs.text(query, max_results=max_results)
            self.logger.log("INFO", f"✓ 検索完了: {len(results)}件の結果")
            return results
        except Exception as e:
            self.logger.log("ERROR", f"✗ Web検索失敗: {str(e)}")
            return []
    
    def fetch_and_scrape(self, url: str) -> Optional[str]:
        """URLからコンテンツをフェッチしてスクレイピング"""
        self.logger.log("DEBUG", f"📄 スクレイピング開始: {url}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"スクレイピング: {url[:40]}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=20)
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # スクリプトとスタイルを削除
            for script in soup(["script", "style"]):
                script.decompose()
            
            # テキストを抽出
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            content = '\n'.join(lines)
            
            self.logger.log("INFO", f"✓ スクレイピング完了: {len(content)}文字")
            return content[:5000]  # 最初の5000文字
        except Exception as e:
            self.logger.log("ERROR", f"✗ スクレイピング失敗: {str(e)}")
            return None
    
    def save_article(self, title: str, content: str) -> bool:
        """記事をファイルに保存"""
        try:
            filename = f"article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = self.data_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Title: {title}\n")
                f.write(f"Saved: {datetime.now().isoformat()}\n")
                f.write("=" * 70 + "\n\n")
                f.write(content)
            
            self.logger.log("INFO", f"✓ 記事を保存: {filepath}")
            return True
        except Exception as e:
            self.logger.log("ERROR", f"✗ 記事保存失敗: {str(e)}")
            return False
    
    def install_package(self, package: str) -> Tuple[bool, str]:
        """Pythonパッケージをインストール - 必要なライブラリを自動取得"""
        self.logger.log("INFO", f"📦 パッケージインストール開始: {package}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"インストール: {package}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", package],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self.logger.log("INFO", f"✓ パッケージインストール成功: {package}")
                return True, f"Installed: {package}"
            else:
                self.logger.log("ERROR", f"✗ パッケージインストール失敗: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            self.logger.log("ERROR", f"✗ パッケージインストール タイムアウト: {package}")
            return False, "Installation timeout"
        except Exception as e:
            self.logger.log("ERROR", f"✗ パッケージインストール例外: {str(e)}")
            return False, str(e)
    
    def execute_command(self, command: str, timeout: int = 60) -> Tuple[bool, str]:
        """シェルコマンドを実行 - subprocess経由の外部ツール実行"""
        self.logger.log("DEBUG", f"⚙️  コマンド実行: {command}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"コマンド: {command[:40]}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            status = "✓" if success else "✗"
            self.logger.log("DEBUG", f"{status} コマンド完了 (コード: {result.returncode})")
            return success, output
        except subprocess.TimeoutExpired:
            self.logger.log("ERROR", f"✗ コマンド実行タイムアウト: {command}")
            return False, "Command timeout"
        except Exception as e:
            self.logger.log("ERROR", f"✗ コマンド実行例外: {str(e)}")
            return False, str(e)


class LocalLLMInterface:
    """ローカルLLM (llama.cpp) インターフェース - ヘルスチェック機能付き"""
    
    def __init__(self, base_url: str = "http://0.0.0.0:8080", logger: Optional[TUGUMILogger] = None):
        self.base_url = base_url
        self.logger = logger
        self.last_response_time = 0.0
        self.is_healthy = False
        self._verify_connection()
    
    def _verify_connection(self):
        """接続確認"""
        if self.logger:
            self.logger.log("DEBUG", f"LLMサーバー接続確認: {self.base_url}")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            self.is_healthy = response.status_code == 200
            if self.logger:
                status = "✓ 接続成功" if self.is_healthy else "✗ 接続失敗"
                self.logger.log("INFO", f"LLMサーバー: {status}")
        except Exception as e:
            self.is_healthy = False
            if self.logger:
                self.logger.log("WARNING", f"LLMサーバー接続失敗: {str(e)}")
    
    def check_health(self) -> bool:
        """LLMサーバーのヘルスチェック"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            self.is_healthy = response.status_code == 200
            return self.is_healthy
        except Exception:
            self.is_healthy = False
            return False
    
    def generate(self, prompt: str, timeout: int = 300) -> str:
        """テキスト生成 - タイムアウト対応"""
        if not self.check_health():
            if self.logger:
                self.logger.log("ERROR", "✗ LLMサーバーが応答しません")
            return ""
        
        try:
            start_time = time.time()
            if self.logger:
                self.logger.log("DEBUG", "🧠 LLM推論開始...")
            
            payload = {
                "prompt": prompt,
                "n_predict": 512,
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "stop": ["ユーザー:", "User:"]
            }
            
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            self.last_response_time = elapsed
            
            if response.status_code == 200:
                result = response.json().get("content", "")
                if self.logger:
                    self.logger.log("DEBUG", f"✓ LLM推論完了 ({elapsed:.2f}秒)")
                return result.strip()
            else:
                if self.logger:
                    self.logger.log("ERROR", f"✗ LLM推論失敗: {response.status_code}")
                return ""
        except requests.Timeout:
            if self.logger:
                self.logger.log("ERROR", f"✗ LLM推論タイムアウト (>{timeout}秒) - フリーズの可能性あり")
            return ""
        except Exception as e:
            if self.logger:
                self.logger.log("ERROR", f"✗ LLM推論例外: {str(e)}")
            return ""


class TUGUMIAgent:
    """TUGUMI - 完全な自律型AIエージェント"""
    
    def __init__(self):
        self.logger = TUGUMILogger()
        self.progress = ProgressTracker()
        self.llm = LocalLLMInterface(logger=self.logger)
        self.tools = ToolExecutor(self.logger, self.progress)
        self.memory = {"conversations": [], "learned": []}
        self.graph = self._build_agent_graph()
        self.logger.log("INFO", "✓ TUGUMIエージェント初期化完了")
    
    def _build_agent_graph(self):
        """LangGraphを使用してエージェントグラフを構築"""
        workflow = StateGraph(AgentState)
        
        # ノード定義
        workflow.add_node("understand_goal", self._understand_goal)
        workflow.add_node("plan_task", self._plan_task)
        workflow.add_node("execute_tool", self._execute_tool)
        workflow.add_node("evaluate_result", self._evaluate_result)
        workflow.add_node("self_correct", self._self_correct)
        workflow.add_node("complete_task", self._complete_task)
        
        # エッジ定義
        workflow.set_entry_point("understand_goal")
        workflow.add_edge("understand_goal", "plan_task")
        workflow.add_edge("plan_task", "execute_tool")
        workflow.add_conditional_edges(
            "execute_tool",
            self._should_evaluate,
            {
                "evaluate": "evaluate_result",
                "complete": "complete_task"
            }
        )
        workflow.add_conditional_edges(
            "evaluate_result",
            self._should_correct,
            {
                "correct": "self_correct",
                "complete": "complete_task"
            }
        )
        workflow.add_edge("self_correct", "execute_tool")
        
        return workflow.compile()
    
    def _understand_goal(self, state: AgentState) -> AgentState:
        """フェーズ1: 目標理解 - ユーザー指示を分析"""
        self.logger.log("DEBUG", "📋 [フェーズ1] 目標理解開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="目標理解中")
        
        prompt = f"""ユーザーの指示を分析し、達成すべき明確な目標を定義してください。

【ユーザーの指示】
{state['task']}

【分析内容】
1. 達成目標: ユーザーが本当に求めていることは何か?
2. 背景・文脈: 指示の背景情報は?
3. 制約条件: 時間制限、技術的制約などはあるか?
4. 成功条件: 何があれば成功と言えるか?

【回答形式】
目標: [明確で測定可能な目標]
背景: [背景情報]
制約: [制約条件]
成功条件: [成功の定義]
"""
        
        response = self.llm.generate(prompt, timeout=120)
        if not response:
            self.logger.log("ERROR", "✗ LLMからの応答がありません")
            state["error_log"].append("目標理解: LLM生成失敗")
            state["final_result"] = "LLMサーバーのエラーにより処理できません"
            return state
        
        state["goal"] = response
        state["observations"].append(f"【目標定義】\n{response[:300]}")
        self.logger.log("INFO", f"✓ 目標定義完了")
        
        return state
    
    def _plan_task(self, state: AgentState) -> AgentState:
        """フェーズ2: 計画立案 - タスクを実行可能なステップに分解"""
        self.logger.log("DEBUG", "📝 [フェーズ2] 計画立案開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="計画立案中")
        
        prompt = f"""以下の目標を達成するための詳細な実行計画を立案してください。

【目標】
{state['goal']}

【立案要件】
1. 実行可能なステップリスト (5-10ステップ)
2. 各ステップの目的と詳細
3. 使用するツール (Web検索、スクレイピング、コマンド実行など)
4. 各ステップの成功条件
5. 予想される問題と対策

【回答形式】
ステップ1: [内容]
  目的: [何を達成するか]
  ツール: [使用ツール]
  成功条件: [成功の定義]
  
(以下、ステップ2以降も同様)
"""
        
        response = self.llm.generate(prompt, timeout=120)
        if not response:
            state["error_log"].append("計画立案: LLM生成失敗")
            return state
        
        # ステップを抽出
        lines = response.split('\n')
        steps = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and (line_stripped.startswith("ステップ") or 
                                 (len(line_stripped) > 5 and line_stripped[0].isdigit())):
                steps.append(line_stripped)
        
        state["plan"] = steps if steps else ["計画実行"]
        state["observations"].append(f"【立案計画】{len(state['plan'])}ステップ")
        self.logger.log("INFO", f"✓ 計画立案完了: {len(state['plan'])}ステップ")
        
        return state
    
    def _execute_tool(self, state: AgentState) -> AgentState:
        """フェーズ3: ツール活用 - 計画に基づいてツールを実行"""
        self.logger.log("DEBUG", "🛠️  [フェーズ3] ツール実行開始")
        
        if state["current_step"] >= len(state["plan"]):
            return state
        
        current_plan = state["plan"][state["current_step"]]
        self.progress.update(
            TaskStatus.EXECUTING,
            task=state["task"],
            subtask=f"ステップ {state['current_step'] + 1}/{len(state['plan'])}",
            progress=int((state["current_step"] + 1) / len(state["plan"]) * 100)
        )
        
        self.logger.log("INFO", f"ステップ {state['current_step'] + 1}/{len(state['plan'])}")
        
        # アクションを決定
        action_prompt = f"""以下のステップを実行するための具体的なアクションを決定してください。

【ステップ】
{current_plan}

【背景】
{state['goal']}

【指示】
具体的で実行可能なアクション1つを決定してください。
- Web検索が必要なら: 検索: [キーワード]
- スクレイピングが必要なら: スクレイピング: [URL]
- パッケージが必要なら: インストール: [パッケージ名]
- コマンド実行が必要なら: コマンド: [コマンド]
- その他の処理なら説明してください

【回答】
"""
        
        action = self.llm.generate(action_prompt, timeout=60).strip()
        self.logger.log("DEBUG", f"決定アクション: {action[:100]}")
        
        # アクション実行
        result = self._execute_action(action, state)
        
        state["tool_results"][f"step_{state['current_step']}"] = result
        state["observations"].append(f"ステップ {state['current_step'] + 1}: {result[:150]}")
        state["current_step"] += 1
        
        return state
    
    def _execute_action(self, action: str, state: AgentState) -> str:
        """アクションを実行 - 複数のツールに対応"""
        action_lower = action.lower()
        
        try:
            if "検索" in action_lower or "search" in action_lower:
                query = self._extract_query(action)
                if not query:
                    return "検索クエリが抽出できませんでした"
                
                results = self.tools.search_web(query, max_results=5)
                if results:
                    summary = f"検索結果 ({len(results)}件):\n"
                    for i, result in enumerate(results[:3], 1):
                        title = result.get('title', 'No title')[:50]
                        summary += f"{i}. {title}\n"
                    return summary
                else:
                    return "検索結果がありません"
            
            elif "スクレイピング" in action_lower or "scrape" in action_lower:
                url = self._extract_url(action)
                if not url:
                    return "URLが抽出できませんでした"
                
                content = self.tools.fetch_and_scrape(url)
                return content if content else "スクレイピング失敗"
            
            elif "インストール" in action_lower or "install" in action_lower:
                package = self._extract_package(action)
                if not package:
                    return "パッケージ名が抽出できませんでした"
                
                success, output = self.tools.install_package(package)
                return f"インストール {'成功' if success else '失敗'}: {output[:200]}"
            
            elif "コマンド" in action_lower or "command" in action_lower or "実行" in action_lower:
                command = self._extract_command(action)
                if not command:
                    return "コマンドが抽出できませんでした"
                
                success, output = self.tools.execute_command(command, timeout=30)
                return f"コマンド {'成功' if success else '失敗'}:\n{output[:300]}"
            
            else:
                # デフォルト処理
                return f"アクション実行: {action[:100]}"
        
        except Exception as e:
            self.logger.log("ERROR", f"アクション実行例外: {str(e)}\n{traceback.format_exc()}")
            state["error_log"].append(f"アクション実行エラー: {str(e)}")
            return f"エラー: {str(e)}"
    
    def _extract_query(self, action: str) -> str:
        """検索クエリを抽出"""
        if ":" in action:
            return action.split(":", 1)[1].strip()
        parts = action.split()
        return " ".join(parts[-3:]) if len(parts) > 1 else action
    
    def _extract_url(self, action: str) -> Optional[str]:
        """URLを抽出"""
        import re
        urls = re.findall(r'https?://[^\s]+', action)
        return urls[0] if urls else None
    
    def _extract_package(self, action: str) -> Optional[str]:
        """パッケージ名を抽出"""
        parts = action.split()
        for i, part in enumerate(parts):
            if part.lower() in ["install", "インストール"] and i + 1 < len(parts):
                return parts[i + 1]
        if ":" in action:
            return action.split(":", 1)[1].strip()
        return None
    
    def _extract_command(self, action: str) -> Optional[str]:
        """コマンドを抽出"""
        if ":" in action:
            return action.split(":", 1)[1].strip()
        return None
    
    def _should_evaluate(self, state: AgentState) -> str:
        """評価が必要か判定"""
        if state["current_step"] >= len(state["plan"]):
            return "complete"
        return "evaluate"
    
    def _evaluate_result(self, state: AgentState) -> AgentState:
        """フェーズ4: 結果評価 - 実行結果を検証"""
        self.logger.log("DEBUG", "✅ [フェーズ4] 結果評価開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="結果評価中")
        
        last_result = state["tool_results"].get(f"step_{state['current_step'] - 1}", "")
        
        eval_prompt = f"""以下の実行結果を評価してください:

【元の目標】
{state['goal']}

【実行ステップ】
{state['plan'][state['current_step'] - 1] if state['current_step'] > 0 else '不明'}

【実行結果】
{last_result[:200]}

【評価項目】
1. このステップは成功しているか? (はい/いいえ)
2. 進捗は出ているか? (具体的にどこが進んだ?)
3. 次のステップに進めるか?
4. 修正が必要な場合、その内容は?

【回答形式】
成功: [はい/いいえ]
進捗: [具体的内容]
次: [進める/修正必要]
修正内容: [必要があれば記載]
"""
        
        evaluation = self.llm.generate(eval_prompt, timeout=60).strip()
        self.logger.log("DEBUG", f"評価結果: {evaluation[:100]}")
        state["observations"].append(f"評価: {evaluation[:150]}")
        
        return state
    
    def _should_correct(self, state: AgentState) -> str:
        """自己修正が必要か判定"""
        if state["attempts"] >= state["max_attempts"]:
            return "complete"
        
        last_obs = state["observations"][-1] if state["observations"] else ""
        last_result = state["tool_results"].get(f"step_{state['current_step'] - 1}", "")
        
        if "失敗" in last_obs or "エラー" in last_obs or "失敗" in last_result or "エラー" in last_result:
            return "correct"
        
        return "complete"
    
    def _self_correct(self, state: AgentState) -> AgentState:
        """フェーズ5: 自己修正 - 失敗から学習して修正"""
        self.logger.log("DEBUG", "🔧 [フェーズ5] 自己修正開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="自己修正中")
        
        state["attempts"] += 1
        self.logger.log("WARNING", f"自己修正試行 {state['attempts']}/{state['max_attempts']}")
        
        error_info = "\n".join(state["error_log"][-3:]) if state["error_log"] else "エラー情報なし"
        last_result = state["tool_results"].get(f"step_{state['current_step'] - 1}", "")
        
        correct_prompt = f"""以前の失敗から学んで、アプローチを修正してください。

【元の目標】
{state['goal']}

【現在のステップ】
{state['plan'][state['current_step'] - 1] if state['current_step'] > 0 else '不明'}

【失敗内容】
{last_result[:200]}

【エラーログ】
{error_info}

【試行回数】
{state['attempts']}/{state['max_attempts']}

【指示】
失敗原因を分析し、修正されたアプローチを提案してください。
別のツール、別の検索キーワード、別のアプローチなど、
創意工夫して問題を解決してください。

【修正提案】
"""
        
        correction = self.llm.generate(correct_prompt, timeout=60).strip()
        self.logger.log("INFO", f"修正提案: {correction[:100]}")
        
        # 計画を修正
        if state["current_step"] > 0:
            state["plan"][state["current_step"] - 1] = correction
        state["observations"].append(f"修正提案: {correction[:150]}")
        
        return state
    
    def _complete_task(self, state: AgentState) -> AgentState:
        """フェーズ6: タスク完了 - 最終結果を生成"""
        self.logger.log("DEBUG", "🏁 [フェーズ6] タスク完了")
        self.progress.update(TaskStatus.COMPLETED, task=state["task"], progress=100)
        
        summary_prompt = f"""タスク実行の最終結果をまとめてください:

【元のユーザー指示】
{state['task']}

【達成目標】
{state['goal']}

【実行ステップ数】
{len(state['plan'])}

【実行結果サマリー】
{chr(10).join(state['observations'][-5:])}

【最終結果】
ユーザーの指示に対する完全な答え、得られた知見、実行内容をまとめてください。

"""
        
        final_result = self.llm.generate(summary_prompt, timeout=120).strip()
        state["final_result"] = final_result if final_result else "タスクを完了しました"
        
        # 学習情報を保存
        learning = {
            "task": state["task"],
            "goal": state["goal"],
            "result": state["final_result"],
            "timestamp": datetime.now().isoformat(),
            "attempts": state["attempts"],
            "steps": len(state["plan"])
        }
        self.memory["learned"].append(learning)
        
        self.logger.log("INFO", f"✓ タスク完了: {len(state['plan'])}ステップで実行完了")
        
        # 結果をファイルに保存
        try:
            result_file = self.tools.data_dir / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(f"Task: {state['task']}\n")
                f.write(f"Goal: {state['goal']}\n")
                f.write(f"Result: {state['final_result']}\n")
                f.write(f"Attempts: {state['attempts']}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            self.logger.log("INFO", f"✓ 結果を保存: {result_file}")
        except Exception as e:
            self.logger.log("ERROR", f"結果保存失敗: {str(e)}")
        
        return state
    
    def execute_task(self, user_instruction: str) -> Dict[str, Any]:
        """ユーザー指示に基づいてタスクを実行 - メインエントリーポイント"""
        self.logger.log("INFO", "=" * 70)
        self.logger.log("INFO", f"🚀 タスク開始: {user_instruction}")
        self.logger.log("INFO", "=" * 70)
        
        # 初期状態
        initial_state: AgentState = {
            "task": user_instruction,
            "goal": "",
            "plan": [],
            "current_step": 0,
            "tool_results": {},
            "observations": [],
            "final_result": None,
            "error_log": [],
            "attempts": 0,
            "max_attempts": 3
        }
        
        try:
            # LangGraphでエージェントループを実行
            final_state = self.graph.invoke(initial_state)
            
            result = {
                "success": True,
                "task": user_instruction,
                "goal": final_state.get("goal", ""),
                "plan_steps": len(final_state.get("plan", [])),
                "result": final_state.get("final_result", "完了"),
                "attempts": final_state.get("attempts", 0),
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.log("INFO", f"✓ タスク実行完了")
            self.logger.log("INFO", "=" * 70)
            return result
        
        except Exception as e:
            self.logger.log("ERROR", f"✗ タスク実行中に例外発生: {str(e)}")
            self.logger.log("ERROR", traceback.format_exc())
            
            result = {
                "success": False,
                "task": user_instruction,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
    
    def get_status(self) -> Dict[str, Any]:
        """エージェントの現在状態を取得 - 進捗監視用"""
        return self.progress.get_status()
    
    def interactive_mode(self):
        """対話型モード - ユーザーと対話"""
        print("\n" + "=" * 70)
        print("🤖 TUGUMI - 自律型AIエージェント")
        print("=" * 70)
        print(f"LLMサーバー: http://0.0.0.0:8080")
        print(f"データディレクトリ: {self.tools.data_dir}")
        print("\n【コマンド】")
        print("  - タスク入力: 実行したいタスクを入力")
        print("  - status: 現在の状態を表示")
        print("  - exit/quit: 終了")
        print("=" * 70 + "\n")
        
        while True:
            try:
                user_input = input("TUGUMI> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\n拓磨様へ: ご利用ありがとうございました。TUGUMIを終了します。\n")
                    break
                
                if user_input.lower() == 'status':
                    status = self.get_status()
                    print("\n" + "=" * 70)
                    print("現在の状態:")
                    print(json.dumps(status, indent=2, ensure_ascii=False))
                    print("=" * 70 + "\n")
                    continue
                
                # タスク実行
                print(f"\n処理中... (進捗: {self.get_status()['progress']}%)")
                
                result = self.execute_task(user_input)
                
                print("\n" + "=" * 70)
                print("✓ タスク実行結果:")
                print("=" * 70)
                if result.get("success"):
                    print(f"目標: {result.get('goal', '')[:100]}")
                    print(f"ステップ数: {result.get('plan_steps', 0)}")
                    print(f"試行回数: {result.get('attempts', 0)}")
                    print(f"\n【結果】\n{result.get('result', '')}")
                else:
                    print(f"エラー: {result.get('error', '')}")
                print("=" * 70 + "\n")
            
            except KeyboardInterrupt:
                print("\n\n中断します。\n")
                break
            except Exception as e:
                print(f"\nエラー: {str(e)}\n")
                self.logger.log("ERROR", f"対話型モード例外: {str(e)}")


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='TUGUMI - 自律型AIエージェント',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python tugumi_agent.py --interactive
  python tugumi_agent.py --task "Pythonの最新トレンドについて調べて、結果をファイルに保存してください"
  python tugumi_agent.py --status
        """
    )
    parser.add_argument('--task', type=str, help='実行するタスク')
    parser.add_argument('--interactive', action='store_true', help='対話型モード')
    parser.add_argument('--status', action='store_true', help='ステータス表示のみ')
    
    args = parser.parse_args()
    
    # エージェント初期化
    agent = TUGUMIAgent()
    
    if args.status:
        status = agent.get_status()
        print("\n" + json.dumps(status, indent=2, ensure_ascii=False))
    
    elif args.task:
        result = agent.execute_task(args.task)
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.interactive or (not args.task and not args.status):
        agent.interactive_mode()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
