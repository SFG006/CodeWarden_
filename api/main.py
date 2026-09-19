import docker
from docker.errors import ImageNotFound, DockerException
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="CodeWarden API"
)

try:
    client = docker.from_env()
except Exception:
    client = None

class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"

@app.post("/execute")
def execute_code(payload: ExecuteRequest):
    if payload.language != "python":
        raise HTTPException(status_code=400, detail="Only Python is supported for NOW")
    
    if not client:
        raise HTTPException(status_code=500, detail="Docker daemon is not running or accessible.")

    container = None
    try:
        # Spin up the sandbox with strict hardware and network limitations
        container = client.containers.run(
            image="python:3.9-alpine",
            command=["timeout", "3", "python", "-uc", payload.code], # 'timeout 3' kills script if it hangs
            detach=True,
            mem_limit="128m",
            init=True,
            memswap_limit="128m", # 128 MB total memory, no swap space
            cpu_period=100000,
            cpu_quota=50000, # Cap at 50% of a single CPU core
            network_mode="none", # Disable internet access
            user="1000" # Run as non-root unprivileged user
        )

        # Block the API request until container finishes executing
        result = container.wait()

        # Capture stdout and stderr
        output = container.logs().decode("utf-8").strip()

        # Exit code 143 (SIGTERM) is standard when 'timeout' kills a process
        is_timeout = result["StatusCode"] == 143

        return {
            "status": "timeout" if is_timeout else "success" if result["StatusCode"] == 0 else "error",
            "exit_code": result["StatusCode"],
            "output": output if output else "No output generated."
        }

    except ImageNotFound:
        raise HTTPException(status_code=500, detail="Docker image 'python:3.9-alpine' not found and could not be pulled. Run: docker pull python:3.9-alpine")
    except DockerException as e:
        raise HTTPException(status_code=500, detail=f"Docker engine error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Container execution failed: {str(e)}")
    finally:
        # Always clean up container to prevent leaks
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
