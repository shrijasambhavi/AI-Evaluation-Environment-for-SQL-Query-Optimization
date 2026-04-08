# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class SqlEnvAction(Action):
    """Action for the SQL Query Reviewer & Optimizer environment."""
    action_type: str = Field(
        ...,
        description="Either 'test' (to execute query and see result) or 'submit' (final answer submission)"
    )
    query: str = Field(
        ...,
        description="The SQL query to test or submit"
    )


class SqlEnvObservation(Observation):
    """Observation from the SQL environment."""
    task_description: str = Field(default="", description="Objective of the task")
    schema_info: str = Field(default="", description="Database schema details")
    initial_query: Optional[str] = Field(default=None, description="The flawed initial query (if any)")
    feedback: str = Field(default="", description="Execution result, output rows, or error trace")
    done: bool = Field(default=False, description="Whether the episode has ended")
    reward: float = Field(default=0.0, description="Reward for the last action")
    done: bool = Field(default=False, description="Whether the episode has ended")
    reward: float = Field(default=0.0, description="Reward for the last action")
