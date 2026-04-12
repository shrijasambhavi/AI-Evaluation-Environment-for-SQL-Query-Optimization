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

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.conn = None
        self.current_task_key = None
        self.current_task_info = None

    # ✅ RESET (correct)
    def reset(self, *args, **kwargs):
        self._state = State(episode_id=str(uuid4()), step_count=0)

        task = "easy"

        try:
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
        except Exception:
            task = "easy"

        if not isinstance(task, str) or task not in TASKS:
            task = "easy"

        self.current_task_key = task
        self.current_task_info = TASKS[task]

        # reset DB safely
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

        self.conn = self.current_task_info["setup_fn"]()

        observation = SqlEnvObservation(
            task_description=str(self.current_task_info.get("description", "")),
            schema_info=str(self.current_task_info.get("schema_info", "")),
            initial_query=str(self.current_task_info.get("initial_query", "")),
            feedback="Ready. Use 'test' to explore or 'submit' to finalize."
        )

        return observation

    # ✅ STEP (FULLY FIXED)
    def step(self, action: SqlEnvAction):
        self._state.step_count += 1

        # safety: ensure reset was called
        if not self.conn:
            return (
                SqlEnvObservation(
                    task_description="",
                    schema_info="",
                    initial_query=None,
                    feedback="Environment not initialized. Call /reset first."
                ),
                0.0,
                True,
                {}
            )

        reward = 0.0
        done = False
        feedback = ""

        try:
            if action.action_type == "test":
                try:
                    cursor = self.conn.cursor()

                    if not action.query or not isinstance(action.query, str):
                        raise ValueError("Invalid query")

                    cursor.execute(action.query)
                    rows = cursor.fetchmany(10)

                    feedback = f"Execution successful. First 10 rows: {rows}"
                    reward = 0.05

                except Exception as e:
                    feedback = f"Query failed: {str(e)}"
                    reward = -0.05

            elif action.action_type == "submit":
                done = True
                try:
                    grader_fn = getattr(Graders, f"grade_{self.current_task_key}")
                    score, feedback = grader_fn(self.conn, action.query)
                    reward = float(score)
                except Exception as e:
                    feedback = f"Grading error: {str(e)}"
                    reward = -0.1

            else:
                feedback = "Invalid action_type. Use 'test' or 'submit'."
                reward = -0.1

        except Exception as e:
            feedback = f"Unexpected error: {str(e)}"
            reward = -0.1
            done = False

        observation = SqlEnvObservation(
            task_description=str(self.current_task_info.get("description", "")),
            schema_info=str(self.current_task_info.get("schema_info", "")),
            initial_query=str(self.current_task_info.get("initial_query", "")),
            feedback=str(feedback)
        )

        return observation, float(reward), bool(done), {}

    @property
    def state(self) -> State:
        return self._state
