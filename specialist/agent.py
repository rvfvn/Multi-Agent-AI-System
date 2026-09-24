import time
import uuid 

tasks = {}

def create_task(question: str) -> dict:
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "task_id": task_id,
        "status": "submitted",
        "question": question,
        "result": None,
        "error": None,

    }

    return tasks[task_id]

def get_task(task_id: str):
    return tasks.get(task_id)

def process_task(task_id: str):
    try:
        tasks[task_id]["status"] = "working"

        time.sleep(2) # for testing so it does not change immediately

        question = tasks[task_id]["question"]

        # temp fake specialist result - will be replaced by a real RAG call

        result = {
            "category": "Network",
            "resolution": (
                "Reconnect the device to the network and verify "
                "that the user can access the required resources."
                
            ),
            "sources": ["network.md"],
            "original_question": question, 
        }

        tasks[task_id]["result"] = result
        tasks[task_id]["status"] = "completed"

    except Exception as exc:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(exc)



