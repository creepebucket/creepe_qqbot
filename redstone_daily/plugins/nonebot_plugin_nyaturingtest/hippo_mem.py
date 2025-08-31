from collections.abc import Awaitable, Callable
from datetime import datetime
import numpy as np
from nonebot import logger

from .siliconflow_embeddings import SiliconFlowEmbeddings
from redstone_daily.plugins.utils.database import get_database


class HippoMemory:
    def __init__(
        self,
        llm_model: str,
        llm_base_url: str,
        llm_api_key: str,
        embedding_api_key: str,
        session_id: str,
        collection_name: str = "nyaturingtest_hippo_mem",
    ):
        # 标识当前会话
        self.session_id = session_id
        # MongoDB 集合
        self._db = get_database(collection_name)

        # 用于跟踪上次清理的时间（保留字段）
        self._last_forget = datetime.now()
        # 缓存要索引的文本
        self._cache = ""
        # 简易分词器占位（不使用外部模型）
        self._tokenizer = None
        # 初始化嵌入模型，用于计算是否需要重新检索
        self._embedding_model = SiliconFlowEmbeddings(
            model="BAAI/bge-m3",
            api_key=embedding_api_key,
        )
        self._docs = []
        self._cosine_similarity = 0.0

    def _now_str(self) -> str:
        """返回当前时间的 ISO 格式字符串"""
        return datetime.now().isoformat()

    def clear(self) -> None:
        """
        清除所有记忆（当前会话）
        """
        try:
            self._db.delete_many({"session_id": self.session_id})
        except Exception as e:
            logger.error(f"Failed to delete memory docs: {e}")
        self._docs = []
        self._cosine_similarity = 0.0
        logger.info("已清除所有记忆（MongoDB）")

    def add_text(self, text: str):
        """
        添加文本到缓存

        Args:
            text: 要添加的文本
        """
        self._cache += text + "\n"

    def add_texts(self, texts: list[str]):
        """
        添加文本到缓存

        Args:
            texts: 要添加的文本列表
        """
        for text in texts:
            self.add_text(text)

    def _index(self):
        """
        将缓存的文本切分并写入MongoDB
        """
        if not self._cache:
            logger.info("没有缓存的文本需要索引")
            return
        texts = _split_text_by_tokens(self._cache, self._tokenizer, max_tokens=256, overlap=0)
        batches = _split_texts_by_byte_limit(texts, max_bytes=30_000)
        total = 0
        for batch in batches:
            for piece in batch:
                try:
                    self._db.insert_one({
                        "session_id": self.session_id,
                        "text": piece,
                        "created_at": self._now_str(),
                    })
                    total += 1
                except Exception as e:
                    logger.error(f"Failed to insert memory doc: {e}")
        logger.info(f"已索引 {total} 条文本到MongoDB")
        self._cache = ""

    async def retrieve(self, queries: list[str], k: int = 5) -> list[str]:
        """
        从MongoDB检索与查询相关的文本，基于嵌入相似度

        Args:
            queries: 查询文本列表
            k: 返回的最大结果数
        Returns:
            相关文本列表
        """
        # 检查是否需要重新检索
        if not await self._need_retrieve(queries):
            logger.info("不需要重新检索")
            return self._docs

        # 切入索引（把缓存落库）
        self._index()

        # 读取所有候选文档（可以按需增加限制/分页）
        try:
            cursor = self._db.find({"session_id": self.session_id})
            docs = list(cursor)
        except Exception as e:
            logger.error(f"Failed to fetch memory docs: {e}")
            docs = []

        if not docs:
            self._docs = []
            self._cosine_similarity = 0.0
            return []

        doc_texts = [d.get("text", "") for d in docs if isinstance(d.get("text", None), str)]
        if not doc_texts:
            self._docs = []
            self._cosine_similarity = 0.0
            return []

        # 处理查询切分（每256字符）
        splited_queries = []
        for query in queries:
            splited_queries += _split_text_by_tokens(query, self._tokenizer, max_tokens=256, overlap=0)

        # 向量化
        try:
            doc_vecs = np.array(await self._embedding_model.embed_documents(doc_texts))
            if not splited_queries:
                q_vecs = np.array(await self._embedding_model.embed_documents(queries))
            else:
                q_vecs = np.array(await self._embedding_model.embed_documents(splited_queries))
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

        # 计算查询均值向量
        q_mean = np.mean(q_vecs, axis=0)
        # 计算每个文档与查询的相似度
        doc_norms = np.linalg.norm(doc_vecs, axis=1)
        q_norm = np.linalg.norm(q_mean)
        # 防止除零
        q_norm = q_norm if q_norm != 0 else 1e-12
        sims = (doc_vecs @ q_mean) / (doc_norms * q_norm + 1e-12)

        # 选 Top-K
        top_indices = np.argsort(-sims)[:k]
        selected_docs = [doc_texts[i] for i in top_indices]

        self._docs = selected_docs
        self._cosine_similarity = await _cosine_similarity(
            queries if splited_queries == [] else splited_queries, selected_docs, self._embedding_model.embed_documents
        )
        return self._docs

    async def _need_retrieve(self, new_queries: list[str], scale: float = 0.8) -> bool:
        """
        Arguments:
            new_queries: 新的查询文本
            scale: 触发重新检索的余弦相似度比例的阈值，如0.8代表相似度不如原来的80%则重新检索
        判断是否需要重新检索
        """

        if not self._docs or self._cosine_similarity == 0.0:
            return True
        current_similarity = await _cosine_similarity(new_queries, self._docs, self._embedding_model.embed_documents)

        logger.debug(f"当前余弦相似度: {current_similarity}")
        logger.debug(f"原余弦相似度: {self._cosine_similarity}")
        logger.debug(f"触发比例: {scale}, 当前比例: {current_similarity / self._cosine_similarity}")

        return current_similarity < scale * self._cosine_similarity


async def _cosine_similarity(
    a: list[str], b: list[str], embed: Callable[[list[str]], Awaitable[list[list[float]]]]
) -> float:
    """
    计算两个字符串列表之间的整体余弦相似度
    Args:
        a: 第一个字符串列表
        b: 第二个字符串列表
    Returns:
        余弦相似度值
    """
    # 向量化
    a_vecs = np.array(await embed(a))
    b_vecs = np.array(await embed(b))
    # 计算平均向量
    a_mean = np.mean(a_vecs, axis=0)
    b_mean = np.mean(b_vecs, axis=0)
    return _cosine(a_mean, b_mean)


def _cosine(a, b) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def _split_text_by_tokens(text: str, tokenizer, max_tokens=256, overlap=0) -> list[str]:
    """
    使用固定长度按字符切分文本，支持重叠。
    Args:
        text: 要分割的文本
        tokenizer: 保留参数（未使用）
        max_tokens: 每段最大字符数（默认256）
        overlap: 重叠字符数（默认0）
    Returns:
        分割后的文本块列表
    """
    if max_tokens <= 0:
        return [text]
    chunks = []
    start = 0
    step = max(1, max_tokens - max(0, overlap))
    while start < len(text):
        end = min(start + max_tokens, len(text))
        chunks.append(text[start:end])
        start += step
    return chunks


def _split_texts_by_byte_limit(texts: list[str], max_bytes: int = 30_000) -> list[list[str]]:
    """
    将字符串列表按 UTF-8 编码字节大小切割为多个批次，每批总字节数不超过 max_bytes。

    参数:
        texts (list[str]): 要切割的文本列表。
        max_bytes (int): 每个批次最大字节数（默认为 30,000 字节）。

    返回:
        list[list[str]]: 切割后的文本批次列表。
    """
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_bytes: int = 0

    for text in texts:
        text_bytes = len(text.encode("utf-8"))

        if text_bytes > max_bytes:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_bytes = 0
            batches.append([text])
            continue

        if current_bytes + text_bytes <= max_bytes:
            current_batch.append(text)
            current_bytes += text_bytes
        else:
            batches.append(current_batch)
            current_batch = [text]
            current_bytes = text_bytes

    if current_batch:
        batches.append(current_batch)

    return batches
