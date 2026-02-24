from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GraphData(BaseModel):
    nodes: list[Any]
    edges: list[Any]


class PipelineCreate(BaseModel):
    name: str
    graph: GraphData


class PipelineUpdate(BaseModel):
    name: str | None = None
    graph: GraphData | None = None


class PipelineResponse(BaseModel):
    pipeline_id: str
    name: str
    graph: Any
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineListItem(BaseModel):
    pipeline_id: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
