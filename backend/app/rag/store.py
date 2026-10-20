"""向量存储：VectorStore 协议 + faiss 实现。

抽成协议是为了让向量库这一层与 RAG 优化正交——将来想换成 sqlite-vec 或
chroma，只需要新增一个实现类并改 RAG_VECTOR_STORE 配置，管线代码一行不动。

faiss 的 IndexFlatIP 不保存 id 与元数据，所以每个 collection 配一个 sidecar
JSON 存「第 n 行对应哪个 chunk」。当前量级（313 词 + 若干文档）全量重载毫秒级。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

import faiss
import numpy as np

from app.config import get_settings

settings = get_settings()

# 两个 collection：知识库切块与词库词条（词库懒加载）
COLLECTION_KB = "kb_chunks"
COLLECTION_WORD = "word_chunks"


@runtime_checkable
class VectorStore(Protocol):
    """向量存储的最小契约。"""

    def upsert(
        self,
        collection: str,
        ids: list[int],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None: ...

    def query(
        self, collection: str, embedding: list[float], top_k: int = 6
    ) -> list[dict]: ...

    def delete(self, collection: str, ids: list[int]) -> int: ...

    def count(self, collection: str) -> int: ...

    def ids(self, collection: str) -> set[int]: ...


class FaissVectorStore:
    """基于 faiss IndexFlatIP 的精确内积检索。

    向量先做 L2 归一化，内积就等价于余弦相似度。几千条向量下暴力精确检索
    就够了——不存在近似损失，也没有索引构建耗时，比 IVF/HNSW 更合适。
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root or settings.rag_index_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._indexes: dict[str, faiss.Index] = {}
        self._entries: dict[str, list[dict]] = {}

    # ---- 持久化 ----

    def _index_path(self, collection: str) -> Path:
        return self._root / f"{collection}.index"

    def _meta_path(self, collection: str) -> Path:
        return self._root / f"{collection}.json"

    def _load(self, collection: str) -> None:
        if collection in self._indexes:
            return
        index_path = self._index_path(collection)
        meta_path = self._meta_path(collection)
        if index_path.exists() and meta_path.exists():
            self._indexes[collection] = faiss.read_index(str(index_path))
            self._entries[collection] = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            self._indexes[collection] = faiss.IndexFlatIP(settings.embedding_dimension)
            self._entries[collection] = []

    def _save(self, collection: str) -> None:
        faiss.write_index(self._indexes[collection], str(self._index_path(collection)))
        self._meta_path(collection).write_text(
            json.dumps(self._entries[collection], ensure_ascii=False), encoding="utf-8"
        )

    # ---- 契约实现 ----

    def upsert(
        self,
        collection: str,
        ids: list[int],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        if not ids:
            return
        if not (len(ids) == len(embeddings) == len(documents)):
            raise ValueError("ids / embeddings / documents 长度必须一致")

        actual = len(embeddings[0])
        if actual != settings.embedding_dimension:
            # 报错要指向配置而不是 faiss 内部断言：换过 embedding 模型却没同步
            # RAG_EMBEDDING_DIMENSION 时，症状是维度不匹配，根因在配置
            raise ValueError(
                f"向量维度 {actual} 与配置的 embedding_dimension="
                f"{settings.embedding_dimension} 不符，换过 embedding 模型吗？"
            )

        self._load(collection)
        metadatas = metadatas or [{} for _ in ids]

        # 先摘掉同 id 的旧行：文档重新索引时不能留下重复向量
        if ids:
            self.delete(collection, ids)

        matrix = _normalize(np.asarray(embeddings, dtype="float32"))
        self._indexes[collection].add(matrix)
        for item_id, document, metadata in zip(ids, documents, metadatas):
            self._entries[collection].append(
                {"id": item_id, "document": document, "metadata": metadata}
            )
        self._save(collection)

    def query(
        self, collection: str, embedding: list[float], top_k: int = 6
    ) -> list[dict]:
        self._load(collection)
        index = self._indexes[collection]
        if index.ntotal == 0:
            return []
        vector = _normalize(np.asarray([embedding], dtype="float32"))
        scores, positions = index.search(vector, min(top_k, index.ntotal))
        entries = self._entries[collection]
        results: list[dict] = []
        for score, position in zip(scores[0], positions[0]):
            if position < 0 or position >= len(entries):
                continue
            entry = entries[int(position)]
            results.append(
                {
                    "id": entry["id"],
                    "document": entry["document"],
                    "metadata": entry["metadata"],
                    "score": float(score),
                }
            )
        return results

    def delete(self, collection: str, ids: list[int]) -> int:
        """按 id 删除。

        faiss 的 IndexFlat 不支持原地删除，但向量本身存在索引里，
        用 reconstruct_n 取回后重建即可，不需要调用方重新 embed。
        """
        self._load(collection)
        index = self._indexes[collection]
        entries = self._entries[collection]
        targets = set(ids)
        keep_positions = [
            position for position, entry in enumerate(entries) if entry["id"] not in targets
        ]
        removed = len(entries) - len(keep_positions)
        if not removed:
            return 0

        kept_entries = [entries[position] for position in keep_positions]
        rebuilt = faiss.IndexFlatIP(settings.embedding_dimension)
        if keep_positions and index.ntotal:
            vectors = index.reconstruct_n(0, index.ntotal)
            rebuilt.add(np.asarray(vectors)[keep_positions].copy())

        self._indexes[collection] = rebuilt
        self._entries[collection] = kept_entries
        self._save(collection)
        return removed

    def replace_collection(self, collection: str) -> None:
        """整表清空，用于文档重新索引。"""
        self._load(collection)
        self._indexes[collection] = faiss.IndexFlatIP(settings.embedding_dimension)
        self._entries[collection] = []
        self._save(collection)

    def count(self, collection: str) -> int:
        self._load(collection)
        return self._indexes[collection].ntotal

    def ids(self, collection: str) -> set[int]:
        self._load(collection)
        return {entry["id"] for entry in self._entries[collection]}


def _normalize(matrix: np.ndarray) -> np.ndarray:
    """L2 归一化，之后内积即余弦相似度。零向量原样保留避免除零。"""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class NullVectorStore:
    """空实现：embedding 不可用或测试不想碰磁盘时用。"""

    def upsert(self, *args, **kwargs) -> None:
        return None

    def query(self, *args, **kwargs) -> list[dict]:
        return []

    def delete(self, *args, **kwargs) -> int:
        return 0

    def count(self, *args, **kwargs) -> int:
        return 0

    def ids(self, *args, **kwargs) -> set[int]:
        return set()

    def replace_collection(self, *args, **kwargs) -> None:
        return None


_STORE: VectorStore | None = None


def get_store() -> VectorStore:
    """进程内单例。索引文件常驻磁盘，每个进程自己维护一份。"""
    global _STORE
    if _STORE is None:
        _STORE = FaissVectorStore()
    return _STORE


def set_store(store: VectorStore | None) -> None:
    """测试用：注入 NullVectorStore 或临时目录里的实现。"""
    global _STORE
    _STORE = store
