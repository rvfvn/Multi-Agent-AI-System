from pathlib import Path

import faiss
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder, SentenceTransformer


class RAGSystem:
    def __init__(
        self,
        knowledge_base_path=None,
        *,
        embedding_model=None,
        reranker=None,
    ):
        if knowledge_base_path is None:
            self.knowledge_base_path = (
                Path(__file__).resolve().parent.parent / "knowledge_base"
            )
        else:
            self.knowledge_base_path = Path(knowledge_base_path)
        self.knowledge_base_path = self.knowledge_base_path.resolve()
        if not self.knowledge_base_path.is_dir():
            raise ValueError(
                f"Knowledge-base directory does not exist or is not a directory: "
                f"{self.knowledge_base_path}"
            )

        self.documents = []
        self.chunks = []
        self.index = None

        self._load_documents()
        self._split_documents()
        if not self.chunks:
            raise ValueError("Knowledge base contains no usable Markdown chunks.")

        # Supplied models allow offline tests without downloading model weights.
        self.embedding_model = (
            embedding_model
            if embedding_model is not None
            else SentenceTransformer("all-MiniLM-L6-v2")
        )
        # Advanced RAG technique: cross-encoder reranking.
        self.reranker = (
            reranker
            if reranker is not None
            else CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        )
        self._create_vector_store()

    def _load_documents(self):
        """Load all Markdown files from the knowledge base."""

        for file_path in self.knowledge_base_path.glob("*.md"):
            text = file_path.read_text(encoding="utf-8")

            self.documents.append({
                "source": file_path.name,
                "content": text
            })

        print(f"Loaded {len(self.documents)} documents.")

    def _split_documents(self):
        """Split documents into smaller chunks."""

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

        for document in self.documents:
            chunks = splitter.split_text(document["content"])

            for chunk in chunks:
                self.chunks.append({
                    "source": document["source"],
                    "content": chunk
                })

        print(f"Created {len(self.chunks)} chunks.")

    def _create_vector_store(self):
        """Create FAISS vector index."""

        texts = [chunk["content"] for chunk in self.chunks]

        embeddings = self.embedding_model.encode(
            texts,
            convert_to_numpy=True
        )

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)

        print("FAISS vector store created.")

    def retrieve(self, query, top_k=5):
        """Retrieve and rerank relevant chunks."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a nonblank string.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer.")
        query = query.strip()
        candidate_count = min(top_k, len(self.chunks))
        if candidate_count == 0:
            return []

        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True
        )

        _distances, indices = self.index.search(
            query_embedding,
            candidate_count
        )

        candidates = []

        for index in indices[0]:
            if 0 <= index < len(self.chunks):
                candidates.append(self.chunks[index])

        if not candidates:
            return []

        # Cross-encoder reranking
        pairs = [
            (query, candidate["content"])
            for candidate in candidates
        ]

        scores = self.reranker.predict(pairs)

        ranked = sorted(
            zip(scores, candidates),
            key=lambda x: x[0],
            reverse=True
        )

        return [
            {
                "source": candidate["source"],
                "content": candidate["content"],
                "score": float(score)
            }
            for score, candidate in ranked
        ]