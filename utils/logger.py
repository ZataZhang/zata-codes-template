#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""日志配置模块 - 提供单例模式的日志管理器"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from utils.settings import config


class Logger:
    """日志管理器 - 单例模式

    提供统一的日志记录接口，支持控制台和文件双输出。
    自动处理 Windows UTF-8 编码问题。

    Attributes:
        _instance (Optional[Logger]): 单例实例
        _logger (Optional[logging.Logger]): 日志记录器实例

    Examples:
        >>> from utils.logger import logger
        >>> logger.info("这是一条信息日志")
        >>> logger.error("这是一条错误日志")
    """

    _instance: Optional["Logger"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls) -> "Logger":
        """单例模式实现 - 确保只有一个实例

        Returns:
            Logger: 日志管理器单例实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化日志管理器"""
        if self._logger is None:
            self._setup_logger()

    def _setup_logger(self) -> None:
        """设置日志器 - 配置控制台和文件处理器"""
        self._logger = logging.getLogger(config.APP_NAME)
        self._logger.setLevel(getattr(logging, config.LOG_LEVEL))

        # 避免重复添加处理器
        if self._logger.handlers:
            return

        # 创建格式化器
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 控制台处理器 - 处理Unicode编码问题
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
        console_handler.setFormatter(formatter)
        # 在Windows上处理UTF-8编码
        if hasattr(console_handler.stream, "reconfigure"):
            try:
                console_handler.stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass  # 如果reconfigure失败，继续使用默认编码
        self._logger.addHandler(console_handler)

        # 文件处理器 - 按天切分日志文件，避免所有日志写入同一个文件
        try:
            file_handler = TimedRotatingFileHandler(
                filename=str(config.LOG_FILE),
                when="midnight",
                interval=1,
                backupCount=14,
                encoding="utf-8",
                utc=False,
            )
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # 如果无法创建文件处理器，只使用控制台
            print(f"Warning: 无法创建日志文件处理器: {e}")

    def get_logger(self) -> logging.Logger:
        """获取日志器实例

        Returns:
            logging.Logger: 底层的 logging.Logger 实例
        """
        if self._logger is None:
            self._setup_logger()
        return self._logger

    def __getattr__(self, name):
        """委托属性访问到底层的 logger 实例

        允许直接调用 logger.info()、logger.error() 等方法。

        Args:
            name: 属性名称

        Returns:
            底层 logger 实例的对应属性
        """
        if self._logger is None:
            self._setup_logger()
        return getattr(self._logger, name)


# 全局日志器实例
logger = Logger()
