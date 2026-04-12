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

    # =========================
    # RESET (SAFE)
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
    # STEP (FULLY SAFE)
    # =========================
    def step(self, action: SqlEnvAction):
        try:
            self._state.step_count += 1

            # Ensure reset happened
            if not self.conn or not self.current_task_info:
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

            # -------- TEST --------
            if action.action_type == "test":
                try:
                    cursor = self.conn.cursor()

                    if not action.query or not isinstance(action.query, str):
                        raise ValueError("Invalid query")

                    cursor.execute(action.query)
                    rows = cursor.fetchmany(10)

                    feedback = f"Execution successful. Rows: {rows}"
                    reward = 0.05

                except Exception as e:
                    feedback = f"Query failed: {str(e)}"
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
                        feedback = "Grader not found"
                        reward = -0.1

                except Exception as e:
                    feedback = f"Grading error: {str(e)}"
                    reward = -0.1

            # -------- INVALID --------
            else:
                feedback = "Invalid action_type"
                reward = -0.1

            observation = SqlEnvObservation(
                task_description=str(self.current_task_info.get("description", "")),
                schema_info=str(self.current_task_info.get("schema_info", "")),
                initial_query=str(self.current_task_info.get("initial_query", "")),
                feedback=str(feedback)
            )

            return observation, float(reward), bool(done), {}

        except Exception as e:
            # 🚨 THIS GUARANTEES NO 500 EVER
            return (
                SqlEnvObservation(
                    task_description="",
                    schema_info="",
                    initial_query=None,
                    feedback=f"Fatal error: {str(e)}"
                ),
                0.0,
                True,
                {}
            )

    @property
    def state(self) -> State:
        return self._state
