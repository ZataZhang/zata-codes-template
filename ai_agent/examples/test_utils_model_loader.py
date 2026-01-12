"""
测试 AIagent.utils.model_loader 模块的功能

此脚本测试模型加载器中的核心功能，包括：
- 模型凭据解析
- 模型列表查询
- 多提供商支持验证
"""

import sys
from pathlib import Path
from typing import List, Tuple, Optional

from ai_agent.utils.model_loader import resolve_model_credentials, list_models

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def test_resolve_model_credentials():
    """测试 resolve_model_credentials 函数

    测试单个模型的凭据解析功能，包括提供商、基础URL和API密钥的获取。
    """
    model_name = "qwen"

    try:
        # 调用函数获取凭据
        credentials: List[Tuple[str, Optional[str], Optional[str]]] = (
            resolve_model_credentials(model_name)
        )

        if not credentials:
            print(f"⚠️  警告: 模型 '{model_name}' 没有找到有效的凭据配置")
            return False

        print(f"🔍 模型 '{model_name}' 的可用凭据:")
        print("-" * 60)

        for i, (provider, base_url, api_key) in enumerate(credentials, 1):
            print(f"{i}. 📡 提供商: {provider}")
            print(f"   🌐 基础URL: {base_url or '默认'}")
            print(f"   🔑 API密钥: {'✅ 已配置' if api_key else '❌ 未配置'}")
            print()

        return True

    except Exception as e:
        print(f"❌ 错误: 获取模型 '{model_name}' 凭据时发生异常: {e}")
        return False


def test_list_models():
    """测试 list_models 函数

    测试获取提供商的所有可用模型列表。
    """
    print("📋 测试模型列表功能:")
    print("=" * 60)

    # 测试不同的提供商
    test_providers = ["dashscope", "openai", "anthropic"]

    for provider in test_providers:
        print(f"\n🔍 测试提供商: {provider}")
        print("-" * 40)

        try:
            models = list_models(provider)
            if models:
                print(f"✅ 找到 {len(models)} 个模型:")
                for i, model in enumerate(models, 1):
                    name = model.get("name", "未知")
                    desc = model.get("description", "无描述")
                    print(f"  {i}. {name}")
                    if desc != "无描述":
                        print(f"     📝 {desc}")
                    print()
            else:
                print(f"❌ 提供商 '{provider}' 没有配置模型")

        except Exception as e:
            print(f"❌ 错误: 获取提供商 '{provider}' 模型列表时发生异常: {e}")


def test_list_models_by_category():
    """测试按类别获取模型列表

    测试获取特定提供商和类别的模型列表。
    """
    print("🏷️  测试按类别获取模型:")
    print("=" * 60)

    # 测试 dashscope 的不同类别
    categories = [
        "omni_models",
        "vision_models",
        "text_embeddings",
        "multimodal_embeddings",
    ]

    for category in categories:
        print(f"\n📂 类别: {category}")
        print("-" * 40)

        try:
            models = list_models("dashscope", category)
            if models:
                print(f"✅ 找到 {len(models)} 个模型:")
                for i, model in enumerate(models, 1):
                    name = model.get("name", "未知")
                    desc = model.get("description", "无描述")
                    print(f"  {i}. {name}")
                    if desc != "无描述":
                        print(f"     📝 {desc}")
                    print()
            else:
                print(f"ℹ️  类别 '{category}' 下没有模型")

        except Exception as e:
            print(f"❌ 错误: 获取类别 '{category}' 时发生异常: {e}")


def test_multiple_models():
    """测试多个模型的凭据解析

    测试多个常用模型的凭据配置状态。
    """
    test_models = ["qwen", "gpt-4", "claude-3", "qwen-turbo"]

    print("🔄 测试多个模型的凭据解析:")
    print("=" * 60)

    for model in test_models:
        print(f"\n🤖 测试模型: {model}")
        print("-" * 30)

        try:
            credentials = resolve_model_credentials(model)
            if credentials:
                for provider, base_url, api_key in credentials:
                    status = "✅ 已配置" if api_key else "❌ 未配置"
                    url_info = f" ({base_url})" if base_url else ""
                    print(f"  📡 {provider}{url_info}: {status}")
            else:
                print("  ℹ️  无可用凭据")
        except Exception as e:
            print(f"  ❌ 错误: {e}")


def test_model_config_summary():
    """测试模型配置摘要

    显示当前配置的所有提供商和模型的概览。
    """
    print("📊 模型配置摘要:")
    print("=" * 60)

    try:
        from AIagent.utils.model_loader import load_models_config

        config = load_models_config()
        total_models = 0

        print(f"📡 配置的提供商数量: {len(config)}")
        print()

        for provider, provider_config in config.items():
            print(f"🔍 提供商: {provider}")
            print("-" * 30)

            provider_models = 0
            for category, models in provider_config.items():
                if isinstance(models, list):
                    print(f"  📂 {category}: {len(models)} 个模型")
                    provider_models += len(models)
                    # 显示前几个模型名称
                    if len(models) > 0:
                        sample_names = [m.get("name", "未知") for m in models[:3]]
                        print(f"     💡 示例: {', '.join(sample_names)}")
                        if len(models) > 3:
                            print(f"     ... 还有 {len(models) - 3} 个模型")
                        print()

            total_models += provider_models
            print(f"  📊 总计: {provider_models} 个模型")
            print()

        print("🎯 全局统计:")
        print(f"  📡 提供商: {len(config)}")
        print(f"  🤖 模型总数: {total_models}")

    except Exception as e:
        print(f"❌ 错误: 获取配置摘要时发生异常: {e}")


def run_all_tests():
    """运行所有测试函数"""
    print("🚀 开始全面测试 AIagent 模型加载器...")
    print("=" * 80)
    print()

    test_functions = [
        ("凭据解析测试", test_resolve_model_credentials),
        ("模型列表测试", test_list_models),
        ("类别模型测试", test_list_models_by_category),
        ("多模型凭据测试", test_multiple_models),
        ("配置摘要测试", test_model_config_summary),
    ]

    results = []
    for test_name, test_func in test_functions:
        print(f"📋 执行: {test_name}")
        print("-" * 50)
        try:
            result = test_func()
            if result is True or result is None:  # 有些函数不返回结果
                print(f"✅ {test_name} 完成")
                results.append(True)
            else:
                print(f"⚠️  {test_name} 有警告")
                results.append(False)
        except Exception as e:
            print(f"❌ {test_name} 失败: {e}")
            results.append(False)
        print()

    # 汇总结果
    passed = sum(1 for r in results if r)
    total = len(results)

    print("📊 测试结果汇总:")
    print("=" * 50)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")

    if passed == total:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败，请检查配置")

    return passed == total


if __name__ == "__main__":
    run_all_tests()
