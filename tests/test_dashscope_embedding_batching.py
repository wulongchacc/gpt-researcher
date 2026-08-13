import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


class FakeEmbeddingsBase:
    pass


langchain_core_module = ModuleType("langchain_core")
langchain_core_embeddings_module = ModuleType("langchain_core.embeddings")
langchain_core_embeddings_module.Embeddings = FakeEmbeddingsBase
langchain_core_module.embeddings = langchain_core_embeddings_module

MODULE_PATH = Path(__file__).parents[1] / "gpt_researcher" / "memory" / "embeddings.py"
SPEC = importlib.util.spec_from_file_location("gpt_researcher_embeddings", MODULE_PATH)
EMBEDDINGS_MODULE = importlib.util.module_from_spec(SPEC)
with patch.dict(
    sys.modules,
    {
        "langchain_core": langchain_core_module,
        "langchain_core.embeddings": langchain_core_embeddings_module,
    },
):
    SPEC.loader.exec_module(EMBEDDINGS_MODULE)
_BatchedEmbeddings = EMBEDDINGS_MODULE._BatchedEmbeddings


class FakeEmbeddings:
    def __init__(self):
        self.document_batches = []

    def embed_documents(self, texts):
        self.document_batches.append(texts)
        return [[float(text)] for text in texts]

    def embed_query(self, text):
        return [float(text)]


class BatchedEmbeddingsTest(unittest.TestCase):
    def test_is_a_langchain_embeddings_instance(self):
        embeddings = _BatchedEmbeddings(FakeEmbeddings(), batch_size=20)

        self.assertIsInstance(embeddings, FakeEmbeddingsBase)

    def test_limits_document_batch_size(self):
        delegate = FakeEmbeddings()
        embeddings = _BatchedEmbeddings(delegate, batch_size=20)
        texts = [str(index) for index in range(21)]

        result = embeddings.embed_documents(texts)

        self.assertEqual(
            [len(batch) for batch in delegate.document_batches], [20, 1]
        )
        self.assertEqual(result, [[float(index)] for index in range(21)])

    def test_delegates_query_embedding(self):
        delegate = FakeEmbeddings()
        embeddings = _BatchedEmbeddings(delegate, batch_size=20)

        self.assertEqual(embeddings.embed_query("7"), [7.0])

    def test_memory_batches_qwen37_dashscope_embeddings(self):
        community_module = ModuleType("langchain_community")
        embeddings_module = ModuleType("langchain_community.embeddings")
        delegate = FakeEmbeddings()
        embeddings_module.DashScopeEmbeddings = lambda **_kwargs: delegate
        community_module.embeddings = embeddings_module

        with patch.dict(
            sys.modules,
            {
                "langchain_community": community_module,
                "langchain_community.embeddings": embeddings_module,
            },
        ):
            embeddings = EMBEDDINGS_MODULE.Memory(
                "dashscope", "qwen3.7-text-embedding"
            ).get_embeddings()

        embeddings.embed_documents([str(index) for index in range(21)])

        self.assertEqual(
            [len(batch) for batch in delegate.document_batches], [20, 1]
        )


if __name__ == "__main__":
    unittest.main()
