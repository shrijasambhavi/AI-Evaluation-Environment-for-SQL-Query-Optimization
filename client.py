from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from models import SqlEnvAction, SqlEnvObservation


class SqlEnv(EnvClient[SqlEnvAction, SqlEnvObservation, State]):

    def _step_payload(self, action: SqlEnvAction) -> Dict:
        return {
            "action_type": action.action_type,
            "query": action.query,
        }

    def _parse_result(self, payload: Dict) -> StepResult[SqlEnvObservation]:
        obs_data = payload.get("observation", {})
        observation = SqlEnvObservation(
            task_description=obs_data.get("task_description", ""),
            schema_info=obs_data.get("schema_info", ""),
            initial_query=obs_data.get("initial_query"),
            feedback=obs_data.get("feedback", ""),
            done=payload.get("done", False),
            reward=payload.get("reward", 0.0),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
