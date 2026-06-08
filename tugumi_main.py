#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TUGUMI - 自律型AIエージェント
Autonomous AI Agent using local LLM via llama.cpp

Note: To avoid LangChain version incompatibilities this implementation
uses a lightweight, direct HTTP interface to a local llama.cpp server
and does not depend on the LangChain API. LangGraph is still used for
workflow orchestration.
"""

import os
import sys
import json
import time
import subprocess
import logging
import traceback
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import threading

# LangGraph (workflow orchestration)
from langgraph.graph import StateGraph, END
from typing import TypedDict

# その他のライブラリ
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup


class TaskStatus(Enum):
    """タスク状態"""
    IDLE = "idle"
    RUNNING = "running"
    THINKING = "thinking"
    SEARCHING = "searching"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class TUGUMILogger:
    """TUGUMI専用ロガー - ログ管理・ファイル記録"""
    
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
        
        # ロガー初期化（重複ハンドラ対策）
        logger = logging.getLogger("TUGUMI")
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

        self.logger = logger
        self.log("INFO", "=" * 70)
        self.log("INFO", "TUGUMI Agent Started - 自律型AIエージェント起動")
        self.log("INFO", f"Log Dir: {log_file}")
        self.log("INFO", f"Data Dir: {self.data_dir}")
        self.log("INFO", "=" * 70)
    
    def log(self, level: str, message: str):
        """ログを記録"""
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
    """進捗状況トラッカー - リアルタイム監視"""
    
    def __init__(self):
        self.current_status = TaskStatus.IDLE
        self.current_task = ""
        self.subtask = ""
        self.progress_percentage = 0
        self.lock = threading.Lock()
        self.last_update = datetime.now()
        self.frozen_check_threshold = 60  # seconds
    
    def update(self, status: TaskStatus, task: str = "", subtask: str = "", progress: int = 0):
        """進捗を更新"""
        with self.lock:
            self.current_status = status
            self.current_task = task
            self.subtask = subtask
            self.progress_percentage = min(max(int(progress), 0), 100)
            self.last_update = datetime.now()
    
    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        with self.lock:
            seconds_since_update = (datetime.now() - self.last_update).total_seconds()
            is_frozen = (self.current_status in (TaskStatus.RUNNING, TaskStatus.EXECUTING, TaskStatus.THINKING)) and seconds_since_update > self.frozen_check_threshold
            return {
                "status": self.current_status.value,
                "task": self.current_task,
                "subtask": self.subtask,
                "progress": self.progress_percentage,
                "timestamp": datetime.now().isoformat(),
                "last_update_seconds_ago": seconds_since_update,
                "is_frozen": is_frozen
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
        try:
            self.ddgs = DDGS(timeout=20)
        except Exception as e:
            self.logger.log("WARNING", f"DDGS初期化警告: {str(e)}")
            self.ddgs = None
        self.data_dir = logger.data_dir
    
    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Web検索 (DuckDuckGo) - 自動で必要な知識を検索"""
        self.logger.log("DEBUG", f"Web検索開始: {query}")
        self.progress.update(TaskStatus.SEARCHING, subtask=f"Web検索: {query[:40]}")
        
        if not self.ddgs:
            self.logger.log("ERROR", "DDGS が初期化されていません")
            return []
        
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            self.logger.log("INFO", f"検索完了: {len(results)}件")
            return results
        except Exception as e:
            self.logger.log("ERROR", f"Web検索失敗: {str(e)}")
            return []
    
    def fetch_and_scrape(self, url: str) -> Optional[str]:
        """URLからコンテンツをフェッチしてスクレイピング"""
        self.logger.log("DEBUG", f"スクレイピング開始: {url}")
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
            
            self.logger.log("INFO", f"スクレイピング完了: {len(content)}文字")
            return content[:5000]  # 最初の5000文字
        except Exception as e:
            self.logger.log("ERROR", f"スクレイピング失敗: {str(e)}")
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
            
            self.logger.log("INFO", f"記事を保存: {filepath}")
            return True
        except Exception as e:
            self.logger.log("ERROR", f"記事保存失敗: {str(e)}")
            return False
    
    def install_package(self, package: str) -> Tuple[bool, str]:
        """Pythonパッケージをインストール - 必要なライブラリを自動取得"""
        self.logger.log("INFO", f"パッケージインストール開始: {package}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"インストール: {package}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                self.logger.log("INFO", f"パッケージインストール成功: {package}")
                return True, f"Installed: {package}"
            else:
                self.logger.log("ERROR", f"パッケージインストール失敗: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            self.logger.log("ERROR", f"パッケージインストール タイムアウト: {package}")
            return False, "Installation timeout"
        except Exception as e:
            self.logger.log("ERROR", f"パッケージインストール例外: {str(e)}")
            return False, str(e)
    
    def execute_command(self, command: str, timeout: int = 60) -> Tuple[bool, str]:
        """シェルコマンドを実行 - subprocess経由の外部ツール実行"""
        self.logger.log("DEBUG", f"コマンド実行: {command}")
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
            self.logger.log("ERROR", f"コマンド実行タイムアウト: {command}")
            return False, "Command timeout"
        except Exception as e:
            self.logger.log("ERROR", f"コマンド実行例外: {str(e)}")
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
                self.logger.log("DEBUG", "LLM推論開始...")
            
            payload = {
                "prompt": prompt,
                "n_predict": 512,
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "repeat_penalty": 1.1,
                # if the llama.cpp server expects other fields, adjust accordingly
            }
            
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            self.last_response_time = elapsed
            
            if response.status_code == 200:
                # Many llama.cpp http frontends return the text under different keys; try common ones
                data = response.json()
                result = data.get("content") or data.get("text") or data.get("response") or data.get("result") or ""
                if self.logger:
                    self.logger.log("DEBUG", f"✓ LLM推論完了 ({elapsed:.2f}秒)")
                return result.strip() if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            else:
                if self.logger:
                    self.logger.log("ERROR", f"✗ LLM推論失敗: {response.status_code} {response.text}")
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
        workflow.add_edge("complete_task", END)
        
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
            state["final_result"] = None
HANDLE_ERROR_PLACEHOLDER
