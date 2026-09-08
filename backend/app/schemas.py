from pydantic import BaseModel, Field


class RepositoryRequest(BaseModel):
    url: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)
