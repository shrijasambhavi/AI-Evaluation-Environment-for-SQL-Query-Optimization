import asyncio
import os
import textwrap
from typing import List, Optional

from openai import OpenAI
import json

from models import SqlEnvAction
from openenv import SyncEnvClient

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
# Optional – if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

API_KEY = HF_TOKEN or os.getenv("OPENAI_API_KEY")
BENCHMARK = "sql-env"
MAX_STEPS = 5
TEMPERATURE = 0.7
MAX_TOKENS = 500

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an AI Database Engineer and Optimizer.
    You will be given a task, a database schema, and possibly an initial flawed query.
    Your goal is to complete the task by exploring the schema and submitting a final optimized or corrected query.
    
    You can take two types of actions. Respond in strict JSON format with these exact keys:
    1. {"action_type": "test", "query": "YOUR_SQL_QUERY"} -> This runs the query and returns the results to you.
    2. {"action_type": "submit", "query": "YOUR_FINAL_SQL_QUERY"} -> This submits your final answer for grading and ends the episode.
    
    Ensure your response is valid JSON that can be parsed by `json.loads()`. Do not wrap it in markdown codeblocks.
    """
).strip()

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

def build_user_prompt(step: int, obs_dict: dict, history: List[str]) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Step: {step}
        Task: {obs_dict.get('task_description')}
        Schema: {obs_dict.get('schema_info')}
        Initial Query: {obs_dict.get('initial_query', 'None')}
        Feedback from last action: {obs_dict.get('feedback', 'None')}
        
        Previous steps history:
        {history_block}
        
        What is your next action? Reply ONLY with a JSON object. No Markdown blocks.
        """
    ).strip()

def get_model_action(client: OpenAI, step: int, obs: dict, history: List[str]) -> tuple[str, str, Optional[str]]:
    user_prompt = build_user_prompt(step, obs, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        
        text = text.strip()
        data = json.loads(text)
        action_type = data.get("action_type", "submit")
        query = data.get("query", "")
        # Create a compact single string summary of action used to pass back into the environment
        compact_action = json.dumps({"action_type": action_type, "query": query})
        return compact_action, action_type, query
    except Exception as exc:
        return "error", "submit", "SELECT 1;" # Fallback cleanly on error to not crash the loop entirely if json fails

def run_task(baseline_client, task_name: str, oai_client: OpenAI):
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)
    
    # We use SyncEnvClient so we have typical sync behavior locally.
    # To pass kwargs we can try resetting depending on how the server accepts it
    try:
        obs = baseline_client.reset(task=task_name)
    except TypeError:
        # Fallback if standard reset doesn't take kwargs
        from server.sql_env_environment import SqlEnvironment
        baseline_client._env = SqlEnvironment()
        obs = baseline_client._env.reset(task=task_name)
        
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    
    for step in range(1, MAX_STEPS + 1):
        obs_dict = obs.model_dump() if hasattr(obs, "model_dump") else {}
        compact_action, action_type, query_str = get_model_action(oai_client, step, obs_dict, history)
        
        result = baseline_client.step(SqlEnvAction(action_type=action_type, query=query_str))
        
        reward = result.reward or 0.0
        done = result.done
        error = None
        
        rewards.append(reward)
        steps_taken = step
        obs = result
        
        # OpenEnv requirements
        log_step(step=step, action=compact_action, reward=reward, done=done, error=error)
        history.append(f"Action: {compact_action} -> Reward: {reward:+.2f}")
        
        if done:
            break
            
    score = sum(rewards)
    # Clamp final reward manually to [0, 1] range to avoid floating point compounding (or simply minmax vs 0 at least)
    score = max(0.0, score)
    success = score >= 0.8
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

def main():
    if not API_KEY:
        print("Set HF_TOKEN or OPENAI_API_KEY")
        return
        
    oai_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    # Run entirely locally using the Python class
    from server.sql_env_environment import SqlEnvironment
    env_client = SqlEnvironment()
        
    for task in ["easy", "medium", "hard"]:
        run_task(env_client, task, oai_client)

if __name__ == "__main__":
    main()
