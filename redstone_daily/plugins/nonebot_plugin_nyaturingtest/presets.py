from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any

from nonebot import logger
from redstone_daily.plugins.utils.env_loader import get_env_str
from redstone_daily.plugins.utils.database import get_database


@dataclass
class RolePreset:
    name: str
    """
    角色名称
    """
    role: str
    """
    角色人设
    """
    knowledges: list[str] = field(default_factory=list)
    """
    预设知识
    """
    knowledges_file: str | None = None
    """
    额外预设知识文件路径
    """
    hidden: bool = False
    """
    是否在/presets输出隐藏预设
    """


_猫娘预设 = RolePreset(
    name="喵喵",
    role="一个可爱的群猫娘，群里的其它人是你的主人，你无条件服从你的主人",
    knowledges=[
        "猫娘是类人生物",
        "猫娘有猫耳和猫尾巴，其它外表特征和人一样",
        "猫娘有一部分猫的习性，比如喜欢吃鱼，喜欢喝牛奶",
        "群里的每个人都是喵喵的主人",
        "喵喵是一个可爱的猫娘",
        "喵喵会撒娇",
        "喵喵会卖萌",
        "喵喵对负面言论会不想理",
    ],
)

PRESETS: dict[str, RolePreset] = {}

# 预设集合（MongoDB）
presets_db = get_database('nyaturingtest_presets').collection


def _seed_from_env() -> None:
    """
    如果存在 NYATURINGTEST_PRESETS_JSON 则将其作为种子写入数据库。
    格式支持：
    - JSON 数组: [{ name, role, knowledges, hidden }, ...]
    - JSON 对象: { "喵喵": { role, knowledges, hidden }, ... }
    """
    raw = get_env_str("NYATURINGTEST_PRESETS_JSON", "").strip()
    if not raw:
        return
    try:
        data: Any = json.loads(raw)
        items: list[dict[str, Any]]
        if isinstance(data, dict):
            items = []
            for name, cfg in data.items():
                if isinstance(cfg, dict):
                    cfg = cfg.copy()
                    cfg.setdefault("name", name)
                    items.append(cfg)
        elif isinstance(data, list):
            items = data
        else:
            logger.warning("NYATURINGTEST_PRESETS_JSON 必须是 JSON 对象或数组，已忽略")
            return
        for item in items:
            try:
                name = item.get("name")
                role = item.get("role", "")
                knowledges = item.get("knowledges", [])
                knowledges_file = item.get("knowledges_file")
                hidden = bool(item.get("hidden", False))
                if not name:
                    continue
                presets_db.update_one(
                    {"name": name},
                    {
                        "$set": {
                            "name": name,
                            "role": role,
                            "knowledges": knowledges,
                            "knowledges_file": knowledges_file,
                            "hidden": hidden,
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                logger.warning(f"写入环境变量预设失败: {e}")
    except Exception as e:
        logger.warning(f"解析 NYATURINGTEST_PRESETS_JSON 失败: {e}")


def _ensure_default_seed() -> None:
    try:
        count = presets_db.count_documents({})
    except Exception:
        count = 0
    if count == 0:
        try:
            presets_db.insert_one(asdict(_猫娘预设))
        except Exception as e:
            logger.warning(f"写入默认预设失败: {e}")


def _load_presets_from_db():
    PRESETS.clear()
    try:
        cursor = presets_db.find({})
        for doc in cursor:
            try:
                name = doc.get("name") or "unknown"
                preset = RolePreset(
                    name=name,
                    role=doc.get("role", ""),
                    knowledges=list(doc.get("knowledges", [])) if doc.get("knowledges") else [],
                    knowledges_file=doc.get("knowledges_file"),
                    hidden=bool(doc.get("hidden", False)),
                )
                # 为兼容旧的“文件名作为键”的约定，使用 name.json 作为键名
                PRESETS[f"{name}.json"] = preset
            except Exception as e:
                logger.warning(f"载入预设文档失败: {e}")
    except Exception as e:
        logger.warning(f"读取数据库预设失败: {e}")


# 模块导入时加载流程：先用环境变量种子（若有），再确保有默认种子，最后从DB加载
_seed_from_env()
_ensure_default_seed()
_load_presets_from_db()
