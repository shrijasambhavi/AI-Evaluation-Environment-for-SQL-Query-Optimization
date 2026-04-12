from uuid import uuid4
from typing import Any

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SqlEnvAction, SqlEnvObservation
except Exception:
    from models import SqlEnvAction, SqlEnvObservation


class SqlEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)

    # -------- RESET --------
    def reset(self, *args, **kwargs):
        self._state = State(episode_id=str(uuid4()), step_count=0)

        return SqlEnvObservation(
            task_description="SQL test env",
            schema_info="dummy",
            initial_query="SELECT 1",
            feedback="ready"
        )

    # -------- STEP --------
    def step(self, action: Any):
        try:
            self._state.step_count += 1

            # Accept BOTH formats
            if isinstance(action, dict):
                if "action" in action:
                    action = action["action"]
                action = SqlEnvAction(**action)

            # Always return safe output
            if action.action_type == "test":
                return (
                    SqlEnvObservation(
                        task_description="SQL test env",
                        schema_info="dummy",
                        initial_query="SELECT 1",
                        feedback="test ok"
                    ),
                    0.05,
                    False,
                    {}
                )

            if action.action_type == "submit":
                return (
                    SqlEnvObservation(
                        task_description="SQL test env",
                        schema_info="dummy",
                        initial_query="SELECT 1",
                        feedback="submit ok"
                    ),
                    1.0,
                    True,
                    {}
                )

            return (
                SqlEnvObservation(
                    task_description="SQL test env",
                    schema_info="dummy",
                    initial_query="SELECT 1",
                    feedback="invalid action"
                ),
                -0.1,
                True,
                {}
            )

        except Exception as e:
            return (
                SqlEnvObservation(
                    task_description="",
                    schema_info="",
                    initial_query=None,
                    feedback=f"error: {str(e)}"
                ),
                0.0,
                True,
                {}
            )

    @property
    def state(self):
        return self._state
