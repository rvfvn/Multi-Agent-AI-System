import logging
import uuid

from threading import Lock

from specialist.answer import answer_support_question


logger = logging.getLogger(__name__)

tasks = {}

task_lock = Lock()


def create_task(question: str) -> dict:
    """Create and store a new task."""

    task_id = str(uuid.uuid4())

    task = {
        "task_id": task_id,
        "status": "submitted",
        "question": question,
        "result": None,
        "error": None,
    }

    with task_lock:
        tasks[task_id] = task
        return task.copy()


def get_task(task_id: str):
    """Retrieve the current task state."""

    with task_lock:
        task = tasks.get(task_id)
        return task.copy() if task else None


def process_task(task_id: str):
    """
    Execute a Specialist task using RAG and Groq.
    FastAPI runs this as a background task.
    """

    try:
        with task_lock:
            tasks[task_id]["status"] = "working"
            question = tasks[task_id]["question"]

        result = answer_support_question(question) # bangggg

        with task_lock:
            tasks[task_id]["result"] = result.model_dump()
            tasks[task_id]["status"] = "completed"

    except Exception as exc:
        logger.exception(
            "Specialist task %s failed",
            task_id,
        )

        with task_lock:
            tasks[task_id]["result"] = None
            tasks[task_id]["error"] = str(exc)
            tasks[task_id]["status"] = "failed"



