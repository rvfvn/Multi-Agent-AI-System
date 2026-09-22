# Group Project 1: 2 Agent AI System

## Setup

Run these commands from the repository root with Conda installed:

```sh
conda env create --prefix ./.conda --file environment.yml
conda activate ./.conda
python -m playwright install chromium
```

The environment uses Python 3.11 and installs the pinned direct dependencies in
`requirements.txt` (transitive dependencies are resolved by pip). Its local
`.conda/` directory is ignored by Git. To activate it again in a new terminal,
run `conda activate ./.conda` from the repository root.

After pulling dependency changes, activate the environment and run:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pip check
```

Copy `.env.example` to `.env` and set your own `GROQ_API_KEY` there. Never commit
the populated `.env` file.

Dependencies cover the FastAPI/Uvicorn A2A service, HTTP clients, LangChain with
Groq, local sentence-transformer embeddings, FAISS, BM25 hybrid retrieval,
PDF loading, Playwright, and testing/linting. Sentence-transformers also supports
[cross-encoder reranking](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html).
These packages enable the workflow; the agents and
advanced RAG technique still need to be implemented. Embedding/reranking models
download when first loaded, and LLM calls require a valid API key.

Browser installation is a separate step from installing the Python package; see
the [Playwright setup documentation](https://playwright.dev/python/docs/library).

To check the environment and run tests once they are added:

```sh
python -m pip check
python -m pytest
ruff check . --exclude .conda
```

## Run the Mock Application

Open:

mock_support_app/index.html

in your browser.

## Project Requirements

See the project instructions on Canvas for the complete requirements.
