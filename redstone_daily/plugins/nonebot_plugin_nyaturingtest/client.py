import re
from typing import Any

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def generate_response(self, prompt: str, model: str) -> str | None:
        try:
            response: Any = await self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.5,
                timeout=300,  # 5 minutes timeout
            )
        except Exception:
            return None

        # 兼容不同返回结构
        try:
            if isinstance(response, str):
                content = response
            elif isinstance(response, dict):
                # 可能是字典
                choices = response.get("choices") or []
                content = (
                    (choices[0].get("message", {}) or {}).get("content") if choices else None
                )
            else:
                # OpenAI SDK对象
                content = getattr(response, "choices", [None])[0]
                if content is not None:
                    content = getattr(content, "message", None)
                    content = getattr(content, "content", None)
        except Exception:
            content = None

        if content:
            return remove_leading_think(str(content))
        else:
            return None


def remove_leading_think(text: str) -> str:
    # 匹配开头连续的 <think>...</think> 或 <think/> 块
    pattern = r"^(?:\s*<think>(.*?)</think>\s*|\s*<think\s*/?>\s*)+"
    return re.sub(pattern, "", text, flags=re.DOTALL).lstrip()
