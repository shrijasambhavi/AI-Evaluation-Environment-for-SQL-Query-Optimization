# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Sql Env Environment Implementation.

A simple test environment that echoes back messages sent to it.
Perfect for testing HTTP server infrastructure.
"""

from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SqlEnvAction, SqlEnvObservation
    from .tasks import TASKS, Graders
except (ModuleNotFoundError, ImportError):
    from models import SqlEnvAction, SqlEnvObservation
    from server.tasks import TASKS, Graders

class SqlEnvironment(Environment):
    """
    SQL Query Reviewer & Optimizer environment.
    """
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0
        self.conn = None
        self.current_task_key = None
        self.current_task_info = None

    def reset(self, task: str = "easy") -> SqlEnvObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count += 1
        
        # Default to easy if invalid task passed
        if task not in TASKS:
            task = "easy"
            
        self.current_task_key = task
        self.current_task_info = TASKS[task]
        
        # Initialize in-memory database
        if self.conn:
            self.conn.close()
        self.conn = self.current_task_info["setup_fn"]()
        
        return SqlEnvObservation(
            task_description=self.current_task_info["description"],
            schema_info=self.current_task_info["schema_info"],
            initial_query=self.current_task_info["initial_query"],
            feedback="Ready. Submit action_type 'test' to explore or 'submit' to finalize.",
            done=False,
            reward=0.0
        )

    def step(self, action: SqlEnvAction) -> SqlEnvObservation:  # type: ignore[override]
        self._state.step_count += 1
        
        if not self.conn:
            # Recreate DB in case reset wasn't called (shouldn't happen)
            self.reset()

        reward = 0.0
        done = False
        feedback = ""

        if action.action_type == "test":
            # Test the query and return results directly
            try:
                cursor = self.conn.cursor()
                cursor.execute(action.query)
                rows = cursor.fetchmany(10) # limit output to avoid massive prompts
                feedback = f"Execution successful. First 10 rows: {rows}"
                reward = 0.05 # small partial reward for successful test to prevent blind guessing
            except Exception as e:
                feedback = f"Syntax or execution error: {str(e)}"
                reward = -0.05
                
        elif action.action_type == "submit":
            # Grade final submission
            done = True
            grader_fn = getattr(Graders, f"grade_{self.current_task_key}")
            score, feedback = grader_fn(self.conn, action.query)
            reward = score

        return SqlEnvObservation(
            task_description=self.current_task_info["description"],
            schema_info=self.current_task_info["schema_info"],
            initial_query=self.current_task_info["initial_query"],
            feedback=feedback,
            done=done,
            reward=reward,
            metadata={"step": self._state.step_count}
        )

    @property
    def state(self) -> State:
        return self._state
