from pydantic import BaseModel, field_validator

from nonebot import get_plugin_config


class Config(BaseModel):
    db_host: str = None
    db_port: int = None
    db_user: str = None
    db_password: str = None

    # ai
    api_key: str = None
    chat_model: str = None
    max_tokens: int = 2048
    personality: str = None


config: Config = get_plugin_config(Config)
