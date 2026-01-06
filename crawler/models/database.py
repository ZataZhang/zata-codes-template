"""数据库模型示例

展示如何使用 SQLAlchemy 定义数据模型。
根据实际需求修改或扩展这些模型。
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, func

from utils.database import Base


class CrawlerData(Base):
    """爬虫数据模型示例

    用于存储爬取的数据。根据实际需求修改字段。

    Attributes:
        id (int): 主键ID
        source (str): 数据来源
        title (str): 标题
        content (str): 内容
        url (str): 来源URL
        created_at (datetime): 创建时间
        updated_at (datetime): 更新时间
    """

    __tablename__ = "crawler_data"

    __table_args__ = {"comment": "爬虫数据表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    source = Column(String(255), nullable=False, comment="数据来源")
    title = Column(String(255), comment="标题")
    content = Column(Text, comment="内容")
    url = Column(String(512), comment="来源URL")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self):
        return (
            f"<CrawlerData(id={self.id}, source='{self.source}', title='{self.title}')>"
        )


class CrawlerLog(Base):
    """爬虫日志模型示例

    用于记录爬取过程的日志。

    Attributes:
        id (int): 主键ID
        crawler_name (str): 爬虫名称
        status (str): 执行状态 (SUCCESS, ERROR, etc.)
        message (str): 日志消息
        error_detail (str): 错误详情（可选）
        created_at (datetime): 创建时间
    """

    __tablename__ = "crawler_log"

    __table_args__ = {"comment": "爬虫执行日志表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    crawler_name = Column(String(255), nullable=False, comment="爬虫名称")
    status = Column(String(50), nullable=False, comment="执行状态")
    message = Column(Text, comment="日志消息")
    error_detail = Column(Text, comment="错误详情")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )

    def __repr__(self):
        return f"<CrawlerLog(id={self.id}, crawler_name='{self.crawler_name}', status='{self.status}')>"
