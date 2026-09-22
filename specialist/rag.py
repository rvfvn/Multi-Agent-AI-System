from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer, CrossEncoder
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RAGSystem:
    def __init__(self, knowledge_base_path=None):
        if knowledge_base_path is None:
            self.knowledge_base_path = (
                Path(__file__).resolve().parent.parent / "knowledge_base"
            )
        else:
            self.knowledge_base_path = Path(knowledge_base_path)
        # Embedding model
        self.embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

        # Advanced RAG technique:
        # Cross-encoder reranking
        self.reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

        self.documents = []
        self.chunks = []
        self.index = None

        self._load_documents()
        self._split_documents()
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

        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True
        )

        distances, indices = self.index.search(
            query_embedding,
            top_k
        )

        candidates = []

        for index in indices[0]:
            if index < len(self.chunks):
                candidates.append(self.chunks[index])

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