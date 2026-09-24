from fastapi import BackgroundTasks, FastAPI, HTTPException

from specialist.agent import create_task, get_task, process_task
from specialist.models import TaskRequest, TaskResponse


app = FastAPI(title="Specialist Agent A2A Service")


@app.get("/")
def root():
    return {
        "message": "Specialist agent is running"
    }

@app.post("/tasks", response_model=TaskResponse)
def submit_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks
):
    task = create_task(request.question)

    background_tasks.add_task(
        process_task,
        task["task_id"],
    )

    return task

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def retrieve_task(task_id: str):
    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task