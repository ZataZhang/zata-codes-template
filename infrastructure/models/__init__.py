"""模型客户端（models）。

封装 LLM API 调用（Anthropic、OpenAI 等）。
实现 core/shared/interfaces 中定义的 IModelClient 接口。
最终承接 ai_agent/utils/model_loader.py 的职责。
"""
