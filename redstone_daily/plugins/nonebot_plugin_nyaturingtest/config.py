from pydantic import BaseModel
from redstone_daily.plugins.utils.env_loader import get_env_str, get_env_list


class Config(BaseModel):
    # 仅用于 PluginMetadata 展示与兼容
    nyaturingtest_chat_openai_api_key: str = ""
    nyaturingtest_chat_openai_model: str = "gpt-3.5-turbo"
    nyaturingtest_chat_openai_base_url: str = "https://api.openai.com/v1"
    nyaturingtest_siliconflow_api_key: str = ""
    nyaturingtest_enabled_groups: list[int] = []


class _EnvConfig:
    def __init__(self):
        # OpenAI Chat API 配置
        self.nyaturingtest_chat_openai_api_key: str = get_env_str("NYATURINGTEST_CHAT_OPENAI_API_KEY", "")
        self.nyaturingtest_chat_openai_model: str = get_env_str("NYATURINGTEST_CHAT_OPENAI_MODEL", "gpt-3.5-turbo")
        self.nyaturingtest_chat_openai_base_url: str = get_env_str(
            "NYATURINGTEST_CHAT_OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

        # SiliconFlow API Key（用于嵌入/VLM等）
        self.nyaturingtest_siliconflow_api_key: str = get_env_str("NYATURINGTEST_SILICONFLOW_API_KEY", "")

        # 启用的群列表（逗号分隔），示例："123456,234567"
        groups_raw = get_env_list("NYATURINGTEST_ENABLED_GROUPS", default=[], separator=",")
        groups: list[int] = []
        for g in groups_raw:
            try:
                groups.append(int(g))
            except Exception:
                # 跳过无法解析为整数的项
                pass
        self.nyaturingtest_enabled_groups: list[int] = groups


# 对外暴露的配置实例
plugin_config = _EnvConfig()
