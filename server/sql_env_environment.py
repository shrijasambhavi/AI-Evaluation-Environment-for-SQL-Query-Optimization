from uuid import uuid4
from typing import Any, Dict

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SqlEnvAction, SqlEnvObservation
    from .tasks import TASKS, Graders
except (ModuleNotFoundError, ImportError):
    from models import SqlEnvAction, SqlEnvObservation
    from server.tasks import TASKS, Graders


class SqlEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.conn = None
        self.current_task_key = None
        self.current_task_info = None

    # =========================
    # RESET
    # =========================
    def reset(self, *args, **kwargs):
        try:
            self._state = State(episode_id=str(uuid4()), step_count=0)

            task = "easy"

            if "task" in kwargs:
                task = kwargs["task"]
            elif "task_id" in kwargs:
                task = kwargs["task_id"]
            elif len(args) > 0:
                arg = args[0]
                if isinstance(arg, dict):
                    task = arg.get("task") or arg.get("task_id") or "easy"
                elif isinstance(arg, str):
                    task = arg

            if task not in TASKS:
                task = "easy"

            self.current_task_key = task
            self.current_task_info = TASKS[task]

            try:
                if self.conn:
                    self.conn.close()
            except Exception:
                pass

            self.conn = self.current_task_info["setup_fn"]()

            return SqlEnvObservation(
                task_description=str(self.current_task_info.get("description", "")),
                schema_info=str(self.current_task_info.get("schema_info", "")),
                initial_query=str(self.current_task_info.get("initial_query", "")),
                feedback="Ready. Use 'test' or 'submit'."
            )

        except Exception as e:
            return SqlEnvObservation(
                task_description="",
                schema_info="",
                initial_query=None,
                feedback=f"Reset error: {str(e)}"
            )

    # =========================
    # STEP (ACCEPTS BOTH FORMATS + NEVER CRASHES)
    # =========================
    def step(self, action: Any):
        try:
            self._state.step_count += 1

            # -------- NORMALIZE INPUT --------
            if isinstance(action, dict):
                # case 1: {"action": {...}}
                if "action" in action:
                    action = action["action"]

                action = SqlEnvAction(**action)

            # -------- SAFETY CHECK --------
            if not self.conn or not self.current_task_info:
                return (
                    SqlEnvObservation(
                        task_description="",
                        schema_info="",
                        initial_query=None,
                        feedback="Call /reset first"
                    ),
                    0.0,
                    True,
                    {}
                )

            reward = 0.0
            done = False
            feedback = ""

            # -------- TEST --------
            if action.action_type == "test":
                try:
                    cursor = self.conn.cursor()
                    cursor.execute(action.query or "SELECT 1")
                    rows = cursor.fetchmany(5)

                    feedback = f"OK: {rows}"
                    reward = 0.05

                except Exception as e:
                    feedback = f"Query error: {str(e)}"
                    reward = -0.05

            # -------- SUBMIT --------
            elif action.action_type == "submit":
                done = True
                try:
                    grader_fn = getattr(
                        Graders,
                        f"grade_{self.current_task_key}",
                        None
                    )

                    if grader_fn:
                        score, feedback = grader_fn(self.conn, action.query)
                        reward = float(score)
                    else:
                        feedback = "No grader"
                        reward = -0.1

                except Exception as e:
                    feedback = f"Grader error: {str(e)}"
                    reward = -0.1

            else:
                feedback = "Invalid action"
                reward = -0.1

            observation = SqlEnvObservation(
                task_description=str(self.current_task_info.get("description", "")),
                schema_info=str(self.current_task_info.get("schema_info", "")),
                initial_query=str(self.current_task_info.get("initial_query", "")),
                feedback=str(feedback)
            )

            return observation, reward, done, {}

        except Exception as e:
            # 🔥 ABSOLUTE SAFETY NET
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
