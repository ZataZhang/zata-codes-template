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
- **文件编码**: 在读取文件时请使用 `-Encoding utf8` 参数

### 开发优先级
- 优先使用 `uv` 命令而不是 `pip` 或 `conda`
