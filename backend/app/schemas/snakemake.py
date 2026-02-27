from typing import Optional
from pydantic import BaseModel


class SnakemakeWrapperOut(BaseModel):
    id: str
    tool: str
    subcommand: Optional[str]
    name: Optional[str]
    description: Optional[str]
    input_names: Optional[list[str]]
    output_names: Optional[list[str]]
    category: str
    model_config = {"from_attributes": True}


class SnakemakeWorkflowOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    topics: Optional[list[str]]
    html_url: str
    stars: int
    model_config = {"from_attributes": True}


class SnakemakeCatalogStatus(BaseModel):
    wrappers: int
    workflows: int
    ready: bool
