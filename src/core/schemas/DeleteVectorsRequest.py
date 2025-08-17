from pydantic import BaseModel

class DeleteVectorsRequest(BaseModel):
    namespace: str 