# Copyright (c) Meta Platforms, Inc.
# Modified for OpenEnv Hackathon - Fully Validator Safe Version

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
    Fully compatible with OpenEnv validator.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0
        self.conn = None
        self.current_task_key = None
        self.current_task_info = None

    # ✅ FINAL RESET (handles ALL validator formats)
    def reset(self, *args, **kwargs) -> SqlEnvObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count += 1

        task = "easy"

        try:
            # Case 1: kwargs
            if "task" in kwargs:
                task = kwargs["task"]
            elif "task_id" in kwargs:
                task = kwargs["task_id"]

            # Case 2: args
            elif len(args) > 0:
                arg = args[0]

                if isinstance(arg, dict):
                    task = arg.get("task") or arg.get("task_id") or "easy"
                elif isinstance(arg, str):
                    task = arg

        except Exception:
            task = "easy"

        # Validate task safely
        if not isinstance(task, str) or task not in TASKS:
            task = "easy"

        self.current_task_key = task
        self.current_task_info = TASKS[task]

        # Safe DB handling
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

        try:
            self.conn = self.current_task_info["setup_fn"]()
        except Exception:
            # fallback to avoid crash
            self.conn = self.current_task_info["setup_fn"]()

        return SqlEnvObservation(
            task_description=str(self.current_task_info.get("description", "")),
            schema_info=str(self.current_task_info.get("schema_info", "")),
            initial_query=str(self.current_task_info.get("initial_query", "")),
            feedback="Ready. Submit action_type 'test' to explore or 'submit' to finalize.",
            done=False,
            reward=0.0
        )

    # ✅ STEP (safe + robust)
    def step(self, action: SqlEnvAction) -> SqlEnvObservation:  # type: ignore[override]
        self._state.step_count += 1

        if not self.conn:
            self.reset()

        reward = 0.0
        done = False
        feedback = ""

        try:
            if action.action_type == "test":
                try:
                    cursor = self.conn.cursor()
                    cursor.execute(action.query)
                    rows = cursor.fetchmany(10)
                    feedback = f"Execution successful. First 10 rows: {rows}"
                    reward = 0.05
                except Exception as e:
                    feedback = f"Syntax or execution error: {str(e)}"
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

        return SqlEnvObservation(
            task_description=str(self.current_task_info.get("description", "")),
            schema_info=str(self.current_task_info.get("schema_info", "")),
            initial_query=str(self.current_task_info.get("initial_query", "")),
            feedback=str(feedback),
            done=bool(done),
            reward=float(reward),
            metadata={"step": self._state.step_count}
        )

    @property
    def state(self) -> State:
        return self._state
