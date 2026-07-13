from pydantic import BaseModel


class WorkerHeartbeat(BaseModel):
    queue_name: str
    status: str
