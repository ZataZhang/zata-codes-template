"""配置文件 - 集中管理所有环境变量和配置"""

import os
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    """配置类 - 集中管理所有配置项

    Attributes:
        BASE_DIR (Path): 项目根目录
        LOG_DIR (Path): 日志文件目录
        LOG_FILE (Path): 日志文件路径
        LOG_LEVEL (str): 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        APP_NAME (str): 应用名称，用于日志记录器命名
    """

    # 目录配置
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent
    LOG_DIR: ClassVar[Path] = BASE_DIR / "logs"
    LOG_FILE: ClassVar[Path] = LOG_DIR / "app.log"

    # 日志配置
    LOG_LEVEL: ClassVar[str] = os.getenv("LOG_LEVEL", "INFO")
    APP_NAME: ClassVar[str] = os.getenv("APP_NAME", "app")

    @classmethod
    def ensure_log_directory(cls) -> None:
        """确保日志目录存在

        如果日志目录不存在则创建。

        Raises:
            OSError: 当无法创建目录时抛出
        """
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = Config()

# 确保日志目录存在
config.ensure_log_directory()
