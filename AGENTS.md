# AI Agent Guidelines

## 项目配置

### Python 包管理
- **包管理器**: 使用 `uv` 来管理 Python 项目和依赖
- **项目结构**: 遵循标准的 Python 项目布局
- **依赖声明**: 所有依赖都在 `pyproject.toml` 中正确声明

### 开发环境设置
- **依赖安装**: `uv pip install`
- **运行脚本**: `uv run python script.py`
- **虚拟环境**: `uv venv`
- **锁定文件**: 使用 `uv lock` 更新依赖锁定文件

## 代码规范

### 注释规范 (Google Style)
- **模块文档字符串**: 每个模块必须包含模块级文档字符串，描述模块的功能和用途
- **函数文档字符串**: 所有公共函数必须包含完整的 docstring，包括参数说明、返回值和异常
- **类文档字符串**: 类必须包含描述其用途的文档字符串
- **类型注解**: 使用类型注解来标注函数参数和返回值类型
- **内联注释**: 对于复杂的逻辑，使用内联注释解释代码意图，但避免过度注释
- **TODO 注释**: 使用 `# TODO: 说明` 格式标记待完成的任务


### AI 友好型代码构建 (AI-Native Patterns)

为了提升 LLM (Large Language Model) 阅读和维护代码的准确性，本项目采用以下 AI 原生编程设计模式。

核心原则
全限定变量命名 (Fully Qualified Naming): 拒绝 data, item, res 等通用命名，必须包含数据的来源、类型或状态（如 raw_user_query_text）。

类型即 Prompt (Types as Prompts): 利用 Pydantic 模型和类型注解作为 AI 的强逻辑约束。

单一赋值与不可变性 (SSA & Immutability): 避免反复修改同一个变量，每个处理步骤应生成新的变量名，保持数据流清晰。
AI Agent 标准代码模版
以下代码展示了如何结合 Pydantic 与 Google Style Docstrings 实现清晰的 Agent 逻辑：

```python
from typing import List
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

# ==========================================
# 1. 类型定义 (Type Definitions as Anchors)
# ==========================================

class AgentTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class UserQueryContext(BaseModel):
    """定义用户输入的原始上下文。

    Attributes:
        query_text (str): 用户输入的原始文本。
        user_id (str): 发起请求的用户唯一标识。
        request_timestamp (datetime): 请求发起的时间戳。
    """
    query_text: str = Field(..., description="用户输入的原始文本")
    user_id: str = Field(..., description="发起请求的用户唯一标识")
    request_timestamp: datetime = Field(default_factory=datetime.now)

class ExternalToolOutput(BaseModel):
    """定义外部工具（如搜索、数据库）返回的原始数据结构。"""
    source_tool_name: str
    raw_content_payload: str
    confidence_score: float

class FinalAgentResponse(BaseModel):
    """定义 Agent 最终输出给用户的结构化回复。"""
    reasoning_trace: str = Field(..., description="Agent 的思考链过程")
    final_answer_text: str = Field(..., description="呈现给用户的最终答案")
    status: AgentTaskStatus

# ==========================================
# 2. Agent 逻辑实现 (SSA Logic Flow)
# ==========================================

class KnowledgeRetrievalAgent:
    """负责执行知识检索和问答生成的智能体。"""

    def execute_task(self, incoming_user_context: UserQueryContext) -> FinalAgentResponse:
        """执行知识检索任务的主流程。

        采用单一赋值形式 (SSA) 编写，确保 AI 能够清晰追踪数据流向。

        Args:
            incoming_user_context (UserQueryContext): 包含用户查询和元数据的上下文对象。

        Returns:
            FinalAgentResponse: 包含思考过程和最终答案的结构化响应。
        """

        # [STEP 1] - 意图解析
        # 不复用变量，创建明确的 "sanitized" 版本
        sanitized_search_intent: str = self._sanitize_input(incoming_user_context.query_text)

        # [STEP 2] - 工具调用
        # 明确区分 "search_results" 的来源和状态
        raw_tool_outputs_list: List[ExternalToolOutput] = self._call_search_tool(sanitized_search_intent)

        # [STEP 3] - 信息合成
        # 将原始工具数据转换为 AI 可读的上下文块
        synthesized_context_str: str = self._format_context(raw_tool_outputs_list)

        # [STEP 4] - 生成最终回复
        # 变量名明确指出了它是 "final_response_object"
        final_agent_response_obj: FinalAgentResponse = self._generate_llm_response(
            context=synthesized_context_str,
            original_query=incoming_user_context.query_text
        )

        return final_agent_response_obj

    # --- 辅助方法 (Internal Methods) ---

    def _sanitize_input(self, text: str) -> str:
        """清洗用户输入文本。"""
        return text.strip().lower()

    def _call_search_tool(self, query: str) -> List[ExternalToolOutput]:
        """模拟调用外部搜索工具。"""
        return [
            ExternalToolOutput(
                source_tool_name="google_search",
                raw_content_payload="Python 3.12 features...",
                confidence_score=0.95
            )
        ]

    def _format_context(self, tools_data: List[ExternalToolOutput]) -> str:
        """格式化工具输出为字符串上下文。"""
        return "\n".join([t.raw_content_payload for t in tools_data])

    def _generate_llm_response(self, context: str, original_query: str) -> FinalAgentResponse:
        """调用 LLM 生成最终回复。"""
        return FinalAgentResponse(
            reasoning_trace="Analyzed search results...",
            final_answer_text=f"Based on context, here is the answer to '{original_query}'",
            status=AgentTaskStatus.COMPLETED
        )
```


### 文档字符串格式
```python
def function_name(param1: str, param2: int) -> bool:
    """执行某个功能的函数。

    这是一个详细描述函数用途的段落。

    Args:
        param1 (str): 参数1的描述
        param2 (int): 参数2的描述

    Returns:
        bool: 返回值的描述

    Raises:
        ValueError: 当参数无效时抛出

    Examples:
        >>> function_name("hello", 42)
        True

        >>> function_name(param1="world", param2=100)
        True
    """
    pass
```

## 平台特定说明

### Windows 环境
- **Shell 语法**: 在 Windows 上运行时，一切 shell 命令请用 PowerShell 语法
- **文件编码**: 在读取文件时请使用 `-Encoding utf8` 参数 例如 : Get-Content -Path dwcrawler\core\crawler.py -Encoding utf8

### 开发优先级
- 优先使用 `uv` 命令而不是 `pip` 或 `conda`
