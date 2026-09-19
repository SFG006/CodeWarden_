import docker
from docker.models import containers
from fastapi import FastAPI , HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="CodeWarden API"
)
client = docker.from_env()

class ExecuteRequest(BaseModel):
    code : str
    language : str = "python"

@app.get("/execute")
def execute_code(payload: ExecuteRequest):
    if payload.language != "python":
        raise HTTPException(status_code=400, detail="Only Python is supported for NOW")
    try:
        # Spin up the sandbox with strict hardware and network limitations
        container = client.containers.run(
            image="python:3.9-alpine",
            command=["timeout", "3", "python", "-c", payload.code],
            detach=True,
            mem_limit="128m",
            memswap_limit="128m",
            cpu_period=100000,
            cpu_quota=50000,
            network_mode="none",
            user="1000"
        )
    except Exception as e:
        pass
