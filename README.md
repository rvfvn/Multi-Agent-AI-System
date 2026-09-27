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

Run the Requester Agent

The Requester Agent coordinates the end-to-end workflow: it submits a question to the Specialist Agent over the A2A protocol, polls for the result, and uses Playwright to fill out and submit the support ticket form in the mock app.

1. Start the Specialist Agent (Terminal 1)
sh
conda activate ./.conda
uvicorn specialist.server:app --reload

Leave this running. It serves the A2A endpoints at http://127.0.0.1:8000.

2. Run the Requester Agent (Terminal 2)
sh
conda activate ./.conda
python -m requester.agent "My account has been locked, what should I do?"

Add --show-browser to watch Chromium fill and submit the form instead of running headless:

sh
python -m requester.agent "My account has been locked, what should I do?" --show-browser
CLI options
Flag	Default	Description
question	—	The user's support question (required, positional)
--base-url	http://127.0.0.1:8000	Specialist Agent's base URL
--timeout	20.0	Seconds to wait for the Specialist Agent before giving up
--show-browser	off	Run Chromium headed instead of headless
Failure handling

The Requester Agent handles the following failure cases without crashing, and without attempting the browser automation:

Connection failure — the Specialist Agent isn't running or isn't reachable at --base-url. Reproduce by stopping uvicorn and re-running the Requester Agent.
Timeout — the Specialist Agent doesn't reach completed/failed within --timeout seconds. Reproduce with a short timeout, e.g. --timeout 1, against the current Specialist stub (which sleeps 2s before completing).
Specialist failure — the Specialist Agent returns status: "failed".
No usable result — the Specialist Agent completes but the result is missing a category or resolution.

In each case, the Requester Agent prints a clear message describing what happened and exits cleanly.

Known Limitations
The Specialist Agent's RAG pipeline is still in progress. process_task currently returns a hardcoded result (category: "Network") instead of retrieving from knowledge_base/ and calling the LLM. The Requester Agent already works against this contract and requires no changes once the real RAG pipeline is wired in, as long as result keeps the keys category, resolution, sources, and original_question.

## Project Requirements

See the project instructions on Canvas for the complete requirements.
