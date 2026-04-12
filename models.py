from typing import Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class SqlEnvAction(Action):
    """Action for the SQL environment"""

    action_type: str = Field(..., description="Either 'test' or 'submit'")
    query: str = Field(..., description="SQL query")


class SqlEnvObservation(Observation):
    """Observation from the SQL environment"""

    task_description: str = Field(default="")
    schema_info: str = Field(default="")
    initial_query: Optional[str] = Field(default=None)
    feedback: str = Field(default="")
