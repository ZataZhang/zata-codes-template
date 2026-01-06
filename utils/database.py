"""通用数据库连接模块

此模块提供 SQLAlchemy 数据库连接和会话管理功能。
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool

from utils.settings import config
from utils.logger import logger

# 创建声明式基类，供模型继承
Base = declarative_base()

# 从配置中获取数据库URL
DATABASE_URL = config.DATABASE_URL

# 如果是 MySQL 数据库，确保使用 pymysql 驱动
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")


def create_database_engine(**kwargs):
    """创建数据库引擎

    Args:
        **kwargs: 传递给 create_engine 的额外参数

    Returns:
        sqlalchemy.engine.Engine: 数据库引擎实例

    Examples:
        >>> engine = create_database_engine(echo=True)
        >>> engine = create_database_engine(pool_size=10)
    """
    default_kwargs = {
        "poolclass": StaticPool,
        "echo": False,  # 设置为 True 可以看到 SQL 语句，便于调试
    }
    default_kwargs.update(kwargs)

    return create_engine(DATABASE_URL, **default_kwargs)


# 创建默认引擎
engine = create_database_engine()

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables(base=None):
    """创建所有表

    Args:
        base: SQLAlchemy 声明式基类，默认使用本模块的 Base

    Examples:
        >>> from utils.database import Base, create_tables
        >>> # 定义模型后
        >>> create_tables()
    """
    if base is None:
        base = Base
    base.metadata.create_all(bind=engine)
    logger.info("数据库表创建成功！")


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（生成器模式）

    用于依赖注入场景（如 FastAPI）

    Yields:
        Session: 数据库会话实例

    Examples:
        >>> from utils.database import get_db
        >>>
        >>> # FastAPI 中使用
        >>> @app.get("/items/")
        >>> def read_items(db: Session = Depends(get_db)):
        >>>     return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database(base=None):
    """初始化数据库

    创建所有表结构

    Args:
        base: SQLAlchemy 声明式基类，默认使用本模块的 Base

    Examples:
        >>> from utils.database import init_database
        >>> init_database()
    """
    create_tables(base)
