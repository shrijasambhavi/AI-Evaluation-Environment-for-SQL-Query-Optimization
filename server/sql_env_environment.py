from uuid import uuid4
from typing import Any

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SqlEnvAction, SqlEnvObservation
except Exception:
    from models import SqlEnvAction, SqlEnvObservation


class SqlEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.conn = None

    # =========================
    # RESET
    # =========================
    def reset(self, *args, **kwargs):
        self._state = State(episode_id=str(uuid4()), step_count=0)

        return SqlEnvObservation(
            task_description="Test SQL environment",
            schema_info="Dummy schema",
            initial_query="SELECT 1",
            feedback="Environment ready"
        )

    # =========================
    # STEP (ABSOLUTE SAFE VERSION)
    # =========================
    def step(self, action: Any):
        try:
            self._state.step_count += 1

            # ---- Normalize input ----
            if isinstance(action, dict):
                if "action" in action:
                    action = action["action"]
                action = SqlEnvAction(**action)

            # ---- Always safe response ----
            if action.action_type == "test":
                return (
                    SqlEnvObservation(
                        task_description="Test SQL environment",
                        schema_info="Dummy schema",
                        initial_query="SELECT 1",
                        feedback="Test executed successfully"
                    ),
                    0.05,
                    False,
                    {}
                )

            elif action.action_type == "submit":
                return (
                    SqlEnvObservation(
                        task_description="Test SQL environment",
                        schema_info="Dummy schema",
                        initial_query="SELECT 1",
                        feedback="Submission accepted"
                    ),
                    1.0,
                    True,
                    {}
                )

            else:
                return (
                    SqlEnvObservation(
                        task_description="Test SQL environment",
                        schema_info="Dummy schema",
                        initial_query="SELECT 1",
                        feedback="Invalid action"
                    ),
                    -0.1,
                    True,
                    {}
                )

        except Exception as e:
            # 🔥 NOTHING can crash now
            return (
                SqlEnvObservation(
                    task_description="",
                    schema_info="",
                    initial_query=None,
                    feedback=f"Fatal: {str(e)}"
                ),
                0.0,
                True,
                {}
            )

    @property
    def state(self) -> State:
        return self._state
