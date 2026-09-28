# Two-Agent IT Support System

An IT support assistant that combines Agent-to-Agent communication, Retrieval-Augmented Generation (RAG), and Playwright browser automation.

```text
User question → Requester → Specialist → RAG + Groq
             ← category, resolution, sources
Requester → Playwright → support form → verified ticket
```

The Requester coordinates the workflow through HTTP task submission and polling. The Specialist retrieves support documentation and generates a grounded response. Playwright uses that response to fill the form and verifies the category, resolution, and five-digit ticket ID.

## Setup

Requires **Python 3.11**, Git, and a Groq API key for live answer generation. Run commands from the repository root.

```sh
git clone https://github.com/rvfvn/Multi-Agent-AI-System.git
cd Multi-Agent-AI-System
```

Create and activate a virtual environment:

```sh
# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies and Chromium:

```sh
python -m pip install -r requirements.txt
python -m pip check
python -m playwright install chromium
```

On Linux, missing browser system libraries can be installed with `python -m playwright install --with-deps chromium`.

Alternatively, use Conda instead of a venv:

```sh
conda env create --prefix ./.conda --file environment.yml
conda activate ./.conda
python -m playwright install chromium
```

Activate the chosen environment in each terminal. If an editor reports missing imports, select that environment's Python interpreter.

## Configuration

Copy `.env.example` to `.env` if it does not already exist, then set:

```dotenv
GROQ_API_KEY=your_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

`GROQ_MODEL` is optional; the value above is the default. An alternative model must support the strict JSON-schema response format. Keep API keys private and restart the service after configuration changes.

Embedding and reranking models download on first use. To prepare them and inspect retrieval without Groq or browser automation:

```sh
python -m scripts.demo_rag "I forgot my password and cannot log in."
```

## Run

**Terminal 1 — start the Specialist:**

```sh
python -m uvicorn specialist.server:app --host 127.0.0.1 --port 8000
```

API documentation is available at [localhost:8000/docs](http://127.0.0.1:8000/docs). Use a single worker; Ctrl+C stops the service.

**Terminal 2 — run the Requester:**

```sh
python -m requester.agent "I forgot my password and cannot log into my account." --timeout 180 --show-browser
```

The Requester opens the local form, submits the ticket, verifies the result, and closes Chromium. Omit `--show-browser` for headless execution. Initial model loading can take longer than subsequent requests.

To watch the form being filled and inspect the verified confirmation:

```sh
python -m requester.agent "I forgot my password and cannot log into my account." --timeout 180 --show-browser --slow-mo 500 --keep-open
```

This slows browser actions by 500 milliseconds and keeps the confirmation open after verification. Press **Enter in the Requester terminal** to close it. Both display controls require `--show-browser`; they are off by default and do not change the form or generated answer. The polling timeout does not include this optional pause.

| Option | Default | Description |
| --- | --- | --- |
| `question` | Required | Nonblank support question, maximum 2,000 characters |
| `--base-url` | `http://127.0.0.1:8000` | Specialist service address |
| `--timeout` | `20.0` | Polling budget in seconds |
| `--show-browser` | Off | Display Chromium |
| `--slow-mo` | `0` | Delay browser actions in milliseconds; requires `--show-browser` |
| `--keep-open` | Off | Wait for Enter after successful verification; requires `--show-browser` |

Handled success returns exit code `0`; handled failure returns `1`.

**Frontend:** open `mock_support_app/index.html` directly to inspect the form manually. No frontend server is needed. Manual form entry does not invoke the agents.

## Tests

The tests start any required local services automatically. Run from the repository root with the environment activated.

**Offline tests — no API key, model downloads, or Chromium required:**

```sh
python -m pytest tests/ -q
```

Covers validation, polling, HTTP errors, retrieval with fake models, answer generation with mocked responses, and browser error handling. Local HTTP tests require permission to bind loopback ports. Browser and live tests are skipped by default.

**Browser tests — installed Chromium, no Groq:**

```sh
python -m pytest tests/browser/ --run-browser -q
```

**Live retrieval — real models, no Groq or browser:**

```sh
python -m pytest tests/live/test_rag_live.py --run-live -q
```

**Live end-to-end tests — Groq API key, real models, and Chromium:**

```sh
python -m pytest tests/live/ --run-live --run-browser --live-timeout 180 -q -s
```

Live tests may download models and consume API quota. Offline and browser tests alone do not verify live answer generation.

## Failure and timeout examples

For a repeatable timeout, start the test-only Specialist in one terminal:

```sh
python -m tests.fake_specialist --scenario timeout --port 8001
```

Then run the Requester in another:

```sh
python -m requester.agent "Test timeout handling" --base-url http://127.0.0.1:8001 --timeout 1
```

Expected: a timeout message, exit code `1`, and no browser launch.

To simulate a failed task, stop the test service and restart it with `--scenario failed`, then rerun the Requester with `--timeout 5`. These scenarios use simulated responses, not RAG or Groq.

## RAG and A2A design

- Seven Markdown support documents are split into 500-character chunks with 100-character overlap.
- `all-MiniLM-L6-v2` generates embeddings stored in a FAISS `IndexFlatL2` index.
- The Specialist retrieves up to eight chunks and applies **cross-encoder reranking** with `cross-encoder/ms-marco-MiniLM-L-6-v2`. This advanced technique evaluates query/passage pairs to refine the initial retrieval order.
- Up to three distinct full source documents are supplied to Groq. Structured output is validated, and cited sources must belong to that context. Unsupported answers become failed tasks.
- `POST /tasks` returns a unique task ID and immediate acknowledgment. `GET /tasks/{task_id}` returns `submitted`, `working`, `completed`, or `failed`, with the result or error when available.

## Limitations

- The unchanged form supports **Account Access, Network, Hardware, and Software**. Email and Security remain valid Specialist classifications but are rejected before browser launch. `test_cases.json` describes classification expectations, including Email.
- Tasks and the vector index are held in memory. Restarting loses tasks; restart after changing knowledge-base documents.
- Polling timeout excludes submission and browser work and does not cancel Specialist processing. HTTP timeouts limit connection/read waiting rather than guaranteeing a strict total duration.
- The frontend is a client-side simulation without persistent ticket storage.
- Live results depend on model relevance and Groq availability; valid source references do not guarantee every generated instruction is correct.
