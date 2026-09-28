"""Test-only HTTP service. No RAG, external calls, or browser automation.

Manual failure demo: python -m tests.fake_specialist --scenario timeout --port 8001
"""

import argparse
import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

SCENARIOS = (
    "success",
    "failed",
    "timeout",
    "bad-json",
    "malformed",
    "http-error",
    "unsupported",
)


def create_app(scenario="success"):
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown test scenario: {scenario}")
    app = FastAPI(title="TEST ONLY: simulated Specialist")
    tasks = {}

    @app.post("/tasks")
    def submit(payload: dict):
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"polls": 0, "question": payload.get("question")}
        return {
            "task_id": task_id,
            "status": "submitted",
            "result": None,
            "error": None,
        }

    @app.get("/tasks/{task_id}")
    def get(task_id: str):
        if task_id not in tasks:
            return JSONResponse({"detail": "Task not found"}, status_code=404)
        tasks[task_id]["polls"] += 1
        task = {"task_id": task_id, "status": "working", "result": None, "error": None}
        if scenario == "http-error":
            return JSONResponse({"detail": "Simulated HTTP error"}, status_code=500)
        if scenario == "bad-json":
            return Response("not JSON", media_type="application/json")
        if scenario == "malformed":
            return {**task, "status": "unknown"}
        if scenario == "timeout" or tasks[task_id]["polls"] == 1:
            return task
        if scenario == "failed":
            return {
                **task,
                "status": "failed",
                "error": "Simulated Specialist failure.",
            }
        category = "Email" if scenario == "unsupported" else "Network"
        return {
            **task,
            "status": "completed",
            "result": {
                "category": category,
                "resolution": "Simulated resolution: reconnect the device.",
                "sources": ["email.md" if scenario == "unsupported" else "network.md"],
            },
        }

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="timeout")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    print(f"TEST ONLY: {args.scenario} simulation. No RAG or Groq is used.", flush=True)
    uvicorn.run(create_app(args.scenario), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
