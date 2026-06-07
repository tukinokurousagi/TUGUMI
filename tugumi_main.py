#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TUGUMI - 自律型AIエージェント
Autonomous AI Agent using LangGraph, LangChain, and local LLM via llama.cpp
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

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.schema import HumanMessage
from langgraph.graph import StateGraph
from typing import TypedDict

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
    """TUGUMI専用ロガー"""
    
    def __init__(self):
        self.log_dir = Path.home() / ".tugumi" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = Path("/storage/emulated/0/TUGUMIDesk") if os.path.exists("/storage/emulated/0") else Path.home() / "TUGUMIDesk"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
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
        self.logger.info("TUGUMI Agent Started")
    
    def log(self, level: str, message: str):
        """ログを記録"""
        if level.upper() == "INFO":
            self.logger.info(message)
        elif level.upper() == "ERROR":
            self.logger.error(message)
        elif level.upper() == "WARNING":
            self.logger.warning(message)
        elif level.upper() == "DEBUG":
            self.logger.debug(message)


class ProgressTracker:
    """進捗状況トラッカー"""
    
    def __init__(self):
        self.current_status = TaskStatus.IDLE
        self.current_task = ""
        self.subtask = ""
        self.progress_percentage = 0
        self.lock = threading.Lock()
    
    def update(self, status: TaskStatus, task: str = "", subtask: str = "", progress: int = 0):
        """進捗を更新"""
        with self.lock:
            self.current_status = status
            self.current_task = task
            self.subtask = subtask
            self.progress_percentage = progress
    
    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        with self.lock:
            return {
                "status": self.current_status.value,
                "task": self.current_task,
                "subtask": self.subtask,
                "progress": self.progress_percentage,
                "timestamp": datetime.now().isoformat()
            }


class AgentState(TypedDict):
    """エージェント状態"""
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
    """ツール実行エンジン"""
    
    def __init__(self, logger: TUGUMILogger, progress: ProgressTracker):
        self.logger = logger
        self.progress = progress
        self.ddgs = DDGS()
        self.data_dir = logger.data_dir
    
    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Web検索 (DuckDuckGo)"""
        self.logger.log("DEBUG", f"Web検索開始: {query}")
        self.progress.update(TaskStatus.SEARCHING, subtask=f"Web検索: {query}")
        
        try:
            results = self.ddgs.text(query, max_results=max_results)
            self.logger.log("INFO", f"検索完了: {len(results)}件")
            return results
        except Exception as e:
            self.logger.log("ERROR", f"Web検索失敗: {str(e)}")
            return []
    
    def fetch_and_scrape(self, url: str) -> Optional[str]:
        """URLからコンテンツをフェッチしてスクレイピング"""
        self.logger.log("DEBUG", f"スクレイピング開始: {url}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"スクレイピング: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=500)
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            content = '\n'.join(lines)
            
            self.logger.log("INFO", f"スクレイピング完了: {len(content)}文字")
            return content[:5000]
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
                f.write("=" * 60 + "\n\n")
                f.write(content)
            
            self.logger.log("INFO", f"記事を保存: {filepath}")
            return True
        except Exception as e:
            self.logger.log("ERROR", f"記事保存失敗: {str(e)}")
            return False
    
    def install_package(self, package: str) -> bool:
        """Pythonパッケージをインストール"""
        self.logger.log("INFO", f"パッケージインストール開始: {package}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"パッケージインストール: {package}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode == 0:
                self.logger.log("INFO", f"パッケージインストール成功: {package}")
                return True
            else:
                self.logger.log("ERROR", f"パッケージインストール失敗: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.log("ERROR", f"パッケージインストール タイムアウト: {package}")
            return False
        except Exception as e:
            self.logger.log("ERROR", f"パッケージインストール例外: {str(e)}")
            return False
    
    def execute_command(self, command: str, timeout: int = 600) -> Tuple[bool, str]:
        """シェルコマンドを実行"""
        self.logger.log("DEBUG", f"コマンド実行: {command}")
        self.progress.update(TaskStatus.EXECUTING, subtask=f"コマンド実行: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout + result.stderr
            self.logger.log("DEBUG", f"コマンド完了: {result.returncode}")
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            self.logger.log("ERROR", f"コマンド実行タイムアウト: {command}")
            return False, "Command timeout"
        except Exception as e:
            self.logger.log("ERROR", f"コマンド実行例外: {str(e)}")
            return False, str(e)


class LocalLLMInterface:
    """ローカルLLM (llama.cpp) インターフェース"""
    
    def __init__(self, base_url: str = "http://0.0.0.0:8080", logger: Optional[TUGUMILogger] = None):
        self.base_url = base_url
        self.logger = logger
    
    def check_health(self) -> bool:
        """LLMサーバーのヘルスチェック"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=600)
            return response.status_code == 200
        except Exception as e:
            if self.logger:
                self.logger.log("WARNING", f"LLMヘルスチェック失敗: {str(e)}")
            return False
    
    def generate(self, prompt: str, timeout: int = 300) -> str:
        """テキスト生成"""
        if not self.check_health():
            if self.logger:
                self.logger.log("ERROR", "LLMサーバーが応答しません")
            return ""
        
        try:
            start_time = time.time()
            if self.logger:
                self.logger.log("DEBUG", "LLM生成開始...")
            
            payload = {
                "prompt": prompt,
                "n_predict": 512,
                "temperature": 0.7,
                "top_p": 0.95
            }
            
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json().get("content", "")
                if self.logger:
                    self.logger.log("DEBUG", f"LLM生成完了 ({elapsed:.2f}秒)")
                return result
            else:
                if self.logger:
                    self.logger.log("ERROR", f"LLM生成失敗: {response.status_code}")
                return ""
        except requests.Timeout:
            if self.logger:
                self.logger.log("ERROR", f"LLM生成タイムアウト (>{timeout}秒)")
            return ""
        except Exception as e:
            if self.logger:
                self.logger.log("ERROR", f"LLM生成例外: {str(e)}")
            return ""


class TUGUMIAgent:
    """TUGUMI自律型AIエージェント"""
    
    def __init__(self):
        self.logger = TUGUMILogger()
        self.progress = ProgressTracker()
        self.llm = LocalLLMInterface(logger=self.logger)
        self.tools = ToolExecutor(self.logger, self.progress)
        self.memory = {"conversations": [], "learned": []}
        self.graph = self._build_agent_graph()
        self.logger.log("INFO", "TUGUMIエージェント初期化完了")
    
    def _build_agent_graph(self):
        """エージェントグラフを構築"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("understand_goal", self._understand_goal)
        workflow.add_node("plan_task", self._plan_task)
        workflow.add_node("execute_tool", self._execute_tool)
        workflow.add_node("evaluate_result", self._evaluate_result)
        workflow.add_node("self_correct", self._self_correct)
        workflow.add_node("complete_task", self._complete_task)
        
        workflow.set_entry_point("understand_goal")
        workflow.add_edge("understand_goal", "plan_task")
        workflow.add_edge("plan_task", "execute_tool")
        workflow.add_conditional_edges(
            "execute_tool",
            self._should_evaluate,
            {"evaluate": "evaluate_result", "complete": "complete_task"}
        )
        workflow.add_conditional_edges(
            "evaluate_result",
            self._should_correct,
            {"correct": "self_correct", "complete": "complete_task"}
        )
        workflow.add_edge("self_correct", "execute_tool")
        
        return workflow.compile()
    
    def _understand_goal(self, state: AgentState) -> AgentState:
        """目標理解"""
        self.logger.log("DEBUG", "目標理解フェーズ開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="目標理解中")
        
        prompt = f"""ユーザーの指示を分析してください:
{state['task']}

目標を1行で定義してください:"""
        
        response = self.llm.generate(prompt, timeout=600)
        if not response:
            state["error_log"].append("LLM生成失敗")
            state["final_result"] = "LLMサーバーのエラー"
            return state
        
        state["goal"] = response.strip()
        state["observations"].append(f"目標定義: {response}")
        self.logger.log("INFO", f"目標定義完了: {response}")
        
        return state
    
    def _plan_task(self, state: AgentState) -> AgentState:
        """計画立案"""
        self.logger.log("DEBUG", "計画立案フェーズ開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="計画立案中")
        
        prompt = f"""以下の目標達成のためのステップを立案してください:
{state['goal']}

ステップを番号付きで列挙してください:"""
        
        response = self.llm.generate(prompt, timeout=600)
        if not response:
            state["error_log"].append("計画立案失敗")
            return state
        
        lines = response.split('\n')
        steps = [line.strip() for line in lines if line.strip() and (line.strip()[0].isdigit() or "ステップ" in line)]
        
        state["plan"] = steps if steps else ["デフォルトステップ"]
        state["observations"].append(f"計画立案: {len(state['plan'])}ステップ")
        self.logger.log("INFO", f"計画立案完了: {len(state['plan'])}ステップ")
        
        return state
    
    def _execute_tool(self, state: AgentState) -> AgentState:
        """ツール実行"""
        self.logger.log("DEBUG", "ツール実行フェーズ開始")
        
        if state["current_step"] >= len(state["plan"]):
            return state
        
        current_plan = state["plan"][state["current_step"]]
        self.progress.update(
            TaskStatus.EXECUTING,
            task=state["task"],
            subtask=f"ステップ {state['current_step'] + 1}/{len(state['plan'])}",
            progress=int((state["current_step"] + 1) / len(state["plan"]) * 100)
        )
        
        self.logger.log("INFO", f"ステップ {state['current_step'] + 1} 実行")
        
        action_prompt = f"""以下を実行するアクションを決定してください:
{current_plan}

アクションを1行で述べてください:"""
        
        action = self.llm.generate(action_prompt, timeout=600).strip()
        self.logger.log("DEBUG", f"決定アクション: {action}")
        
        result = self._execute_action(action, state)
        
        state["tool_results"][f"step_{state['current_step']}"] = result
        state["observations"].append(f"ステップ {state['current_step'] + 1} 結果: {result[:200]}")
        state["current_step"] += 1
        
        return state
    
    def _execute_action(self, action: str, state: AgentState) -> str:
        """アクション実行"""
        action_lower = action.lower()
        
        try:
            if "検索" in action_lower or "search" in action_lower:
                query = self._extract_query(action)
                results = self.tools.search_web(query)
                if results:
                    summary = f"検索結果 ({len(results)}件)"
                    return summary
                return "検索結果なし"
            
            elif "スクレイピング" in action_lower:
                url = self._extract_url(action)
                if url:
                    content = self.tools.fetch_and_scrape(url)
                    return content or "スクレイピング失敗"
                return "URLなし"
            
            elif "インストール" in action_lower:
                package = self._extract_package(action)
                if package:
                    success = self.tools.install_package(package)
                    return f"インストール {'成功' if success else '失敗'}"
                return "パッケージなし"
            
            elif "コマンド" in action_lower:
                command = self._extract_command(action)
                if command:
                    success, output = self.tools.execute_command(command)
                    return f"コマンド実行 {'成功' if success else '失敗'}"
                return "コマンドなし"
            
            else:
                return f"アクション: {action}"
        
        except Exception as e:
            self.logger.log("ERROR", f"アクション実行例外: {str(e)}")
            return f"エラー: {str(e)}"
    
    def _extract_query(self, action: str) -> str:
        """検索クエリを抽出"""
        parts = action.split(":")
        return parts[-1].strip() if ":" in action else action.split()[-1]
    
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
        return None
    
    def _extract_command(self, action: str) -> Optional[str]:
        """コマンドを抽出"""
        return action.split(":", 1)[1].strip() if ":" in action else None
    
    def _should_evaluate(self, state: AgentState) -> str:
        """評価判定"""
        if state["current_step"] >= len(state["plan"]):
            return "complete"
        return "evaluate"
    
    def _evaluate_result(self, state: AgentState) -> AgentState:
        """結果評価"""
        self.logger.log("DEBUG", "結果評価フェーズ開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="結果評価中")
        
        last_result = state["tool_results"].get(f"step_{state['current_step'] - 1}", "")
        
        eval_prompt = f"""実行結果を評価してください:
{last_result[:200]}

成功しているか1単語で答えてください:"""
        
        evaluation = self.llm.generate(eval_prompt, timeout=600).strip()
        self.logger.log("DEBUG", f"評価: {evaluation}")
        state["observations"].append(f"評価: {evaluation}")
        
        return state
    
    def _should_correct(self, state: AgentState) -> str:
        """修正判定"""
        if state["attempts"] >= state["max_attempts"]:
            return "complete"
        
        last_obs = state["observations"][-1] if state["observations"] else ""
        if "失敗" in last_obs or "エラー" in last_obs:
            return "correct"
        
        return "complete"
    
    def _self_correct(self, state: AgentState) -> AgentState:
        """自己修正"""
        self.logger.log("DEBUG", "自己修正フェーズ開始")
        self.progress.update(TaskStatus.THINKING, task=state["task"], subtask="自己修正中")
        
        state["attempts"] += 1
        self.logger.log("WARNING", f"自己修正試行 {state['attempts']}/{state['max_attempts']}")
        
        correct_prompt = f"""失敗からの修正提案:

修正アプローチを1行で提案してください:"""
        
        correction = self.llm.generate(correct_prompt, timeout=600).strip()
        self.logger.log("INFO", f"修正: {correction}")
        
        if state["current_step"] > 0:
            state["plan"][state["current_step"] - 1] = correction
        state["observations"].append(f"修正: {correction}")
        
        return state
    
    def _complete_task(self, state: AgentState) -> AgentState:
        """タスク完了"""
        self.logger.log("DEBUG", "タスク完了フェーズ開始")
        self.progress.update(TaskStatus.COMPLETED, task=state["task"], progress=100)
        
        summary_prompt = f"""タスク実行の最終結果をまとめてください:

指示: {state['task']}
実行ステップ数: {len(state['plan'])}

完了報告を日本語で1-2行で述べてください:"""
        
        final_result = self.llm.generate(summary_prompt, timeout=600).strip()
        state["final_result"] = final_result
        
        learning = {
            "task": state["task"],
            "result": final_result,
            "timestamp": datetime.now().isoformat(),
            "attempts": state["attempts"]
        }
        self.memory["learned"].append(learning)
        
        self.logger.log("INFO", f"タスク完了: {final_result}")
        
        return state
    
    def execute_task(self, user_instruction: str) -> Dict[str, Any]:
        """タスク実行"""
        self.logger.log("INFO", f"タスク開始: {user_instruction}")
        
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
            final_state = self.graph.invoke(initial_state)
            
            result = {
                "success": True,
                "task": user_instruction,
                "goal": final_state.get("goal", ""),
                "result": final_state.get("final_result", "完了"),
                "attempts": final_state.get("attempts", 0),
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.log("INFO", f"タスク実行完了")
            return result
        
        except Exception as e:
            self.logger.log("ERROR", f"タスク実行例外: {str(e)}\n{traceback.format_exc()}")
            
            result = {
                "success": False,
                "task": user_instruction,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
    
    def get_status(self) -> Dict[str, Any]:
        """ステータス取得"""
        return self.progress.get_status()
    
    def interactive_mode(self):
        """対話型モード"""
        print("\nTUGUMI - 自律型AIエージェント")
        print("対話型モード")
        print("タスクを入力してください (終了: exit/quit)\n")
        
        while True:
            try:
                user_input = input("TUGUMI> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit']:
                    print("\nご利用ありがとうございました。")
                    break
                
                if user_input.lower() == 'status':
                    status = self.get_status()
                    print(f"\n状態: {json.dumps(status, ensure_ascii=False)}\n")
                    continue
                
                print("\n実行中...")
                result = self.execute_task(user_input)
                
                print("\n結果:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print()
            
            except KeyboardInterrupt:
                print("\n\n中断します。")
                break
            except Exception as e:
                print(f"\nエラー: {str(e)}\n")
                self.logger.log("ERROR", f"対話型モード例外: {str(e)}")


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TUGUMI - 自律型AIエージェント')
    parser.add_argument('--task', type=str, help='実行するタスク')
    parser.add_argument('--interactive', action='store_true', help='対話型モード')
    parser.add_argument('--status', action='store_true', help='ステータス表示')
    
    args = parser.parse_args()
    
    agent = TUGUMIAgent()
    
    if args.status:
        status = agent.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    
    elif args.task:
        result = agent.execute_task(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.interactive or (not args.task and not args.status):
        agent.interactive_mode()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
