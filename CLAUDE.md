# AI Agent Guidelines

> This document is a project guide for conversational AI such as Claude. For the complete and authoritative specifications, please refer to `AGENTS.md` in the root directory.

## Project Configuration

### Python Package Management
- **Package Manager**: Use `uv` to manage the Python project and dependencies.
- **Project Structure**: Follow standard Python project layouts.
- **Dependency Declaration**: All dependencies must be correctly declared in `pyproject.toml`.

### Development Environment Setup
- **Install Dependencies**: `uv pip install`
- **Run Scripts**: `uv run python script.py`
- **Virtual Environment**: `uv venv`
- **Lock File**: Use `uv lock` to update the dependency lock file.

## Code Standards

### Input/Output & Encoding Standards (CRITICAL FOR WINDOWS)
- **Explicit Encoding**: When reading or writing files using `open()`, `pathlib.Path.read_text()`, or `pathlib.Path.write_text()`, you **MUST** explicitly set `encoding="utf-8"`.
  - *Incorrect*: `open("file.txt", "w")` (Do not use system default)
  - *Correct*: `open("file.txt", "w", encoding="utf-8")`
- **Console Output**: Be aware that Windows consoles (cmd/PowerShell) may default to legacy encodings (CP936/CP1252). Ensure logs and print statements use UTF-8 compatible handling or sanitize special characters if necessary to avoid `????` output.

### Documentation Style (Google Style)
- **Module Docstrings**: Every module must include a module-level docstring describing its function and purpose.
- **Function Docstrings**: All public functions must include a complete docstring, including arguments, return values, and exceptions.
- **Class Docstrings**: Classes must include a docstring describing their purpose.
- **Type Annotations**: Use type annotations for all function arguments and return types.
- **Inline Comments**: Use inline comments to explain the intent behind complex logic, but avoid over-commenting.
- **TODO Comments**: Use the format `# TODO: Description` to mark tasks to be completed.

### AI-Native Code Patterns

To improve the accuracy of LLMs (Large Language Models) in reading and maintaining code, this project adopts the following AI-Native programming design patterns.

#### Core Principles
1.  **Fully Qualified Naming**: Reject generic names like `data`, `item`, or `res`. Variable names must include the source, type, or state of the data (e.g., `raw_user_query_text`).
2.  **Types as Prompts**: Leverage Pydantic models and type annotations as strong logical constraints for the AI.
3.  **Single Static Assignment (SSA) & Immutability**: Avoid repeatedly modifying the same variable. Each processing step should generate a new variable name to keep the data flow clear.

#### AI Agent Standard Code Template
The following code demonstrates how to combine Pydantic with Google Style Docstrings to implement clear Agent logic:

```python
from typing import List
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
import pathlib

# ==========================================
# 1. Type Definitions as Anchors
# ==========================================

class AgentTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class UserQueryContext(BaseModel):
    """Defines the raw context of user input.

    Attributes:
        query_text (str): The raw text input by the user.
        user_id (str): The unique identifier of the user initiating the request.
        request_timestamp (datetime): The timestamp when the request was initiated.
    """
    query_text: str = Field(..., description="The raw text input by the user")
    user_id: str = Field(..., description="The unique identifier of the user initiating the request")
    request_timestamp: datetime = Field(default_factory=datetime.now)

class ExternalToolOutput(BaseModel):
    """Defines the raw data structure returned by external tools (e.g., search, database)."""
    source_tool_name: str
    raw_content_payload: str
    confidence_score: float

class FinalAgentResponse(BaseModel):
    """Defines the structured response output by the Agent to the user."""
    reasoning_trace: str = Field(..., description="The chain of thought process of the Agent")
    final_answer_text: str = Field(..., description="The final answer presented to the user")
    status: AgentTaskStatus

# ==========================================
# 2. Agent Logic Implementation (SSA Logic Flow)
# ==========================================

class KnowledgeRetrievalAgent:
    """Agent responsible for executing knowledge retrieval and QA generation."""

    def execute_task(self, incoming_user_context: UserQueryContext) -> FinalAgentResponse:
        """The main flow for executing the knowledge retrieval task.

        Written in Single Static Assignment (SSA) form to ensure the AI can clearly trace data flow.

        Args:
            incoming_user_context (UserQueryContext): The context object containing user query and metadata.

        Returns:
            FinalAgentResponse: The structured response containing the reasoning process and final answer.
        """

        # [STEP 1] - Intent Parsing
        sanitized_search_intent: str = self._sanitize_input(incoming_user_context.query_text)

        # [STEP 2] - Tool Invocation
        raw_tool_outputs_list: List[ExternalToolOutput] = self._call_search_tool(sanitized_search_intent)

        # [STEP 3] - Information Synthesis
        synthesized_context_str: str = self._format_context(raw_tool_outputs_list)

        # [STEP 4] - Final Response Generation
        final_agent_response_obj: FinalAgentResponse = self._generate_llm_response(
            context=synthesized_context_str,
            original_query=incoming_user_context.query_text
        )

        # [STEP 5] - Logging (Windows Safe)
        # Ensure encoding is explicitly handled if writing to file
        self._log_execution(final_agent_response_obj)

        return final_agent_response_obj

    # --- Internal Methods ---

    def _sanitize_input(self, text: str) -> str:
        """Sanitizes user input text."""
        return text.strip().lower()

    def _call_search_tool(self, query: str) -> List[ExternalToolOutput]:
        """Simulates calling an external search tool."""
        return [
            ExternalToolOutput(
                source_tool_name="google_search",
                raw_content_payload="Python 3.12 features...",
                confidence_score=0.95
            )
        ]

    def _format_context(self, tools_data: List[ExternalToolOutput]) -> str:
        """Formats tool outputs into a string context."""
        return "\n".join([t.raw_content_payload for t in tools_data])

    def _generate_llm_response(self, context: str, original_query: str) -> FinalAgentResponse:
        """Calls the LLM to generate the final response."""
        return FinalAgentResponse(
            reasoning_trace="Analyzed search results...",
            final_answer_text=f"Based on context, here is the answer to '{original_query}'",
            status=AgentTaskStatus.COMPLETED
        )

    def _log_execution(self, response: FinalAgentResponse) -> None:
        """Logs execution details to a file with explicit UTF-8 encoding."""
        log_path = pathlib.Path("agent_execution.log")
        # IMPORTANT: encoding='utf-8' is required for Windows compatibility
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {response.model_dump_json()}\n")

```

### Docstring Format Example

```python
def function_name(param1: str, param2: int) -> bool:
    """Executes a specific function.

    This is a paragraph describing the detailed purpose of the function.

    Args:
        param1 (str): Description of parameter 1.
        param2 (int): Description of parameter 2.

    Returns:
        bool: Description of the return value.

    Raises:
        ValueError: Raised when the parameters are invalid.

    Examples:
        >>> function_name("hello", 42)
        True

        >>> function_name(param1="world", param2=100)
        True
    """
    pass

```

## Platform Specifics

### Windows Environment

* **Shell Syntax**: When running on Windows, use PowerShell syntax for all shell commands.
* **File Encoding (PowerShell)**: When reading files in PowerShell scripts, use `-Encoding utf8` (e.g., `Get-Content ... -Encoding utf8`).
* **Python Output**: To avoid `????` characters in logs or files, always assume the system default encoding is NOT UTF-8. Force `encoding='utf-8'` in all Python I/O operations.

### Development Priorities

* **Tool Priority**: Prioritize using `uv` commands over `pip` or `conda`.

```
