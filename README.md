---
title: AI-Evaluation-Environment-for-SQL-Query-Optimization
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# AI-Evaluation-Environment-for-SQL-Query-Optimization

## Description and Motivation
The **SQL Query Reviewer & Optimizer** is a real-world task environment for OpenEnv. This environment is designed for AI agents that act as Database Engineers. Typically, agent environments test simple logical parsing, but this environment evaluates deep database understanding. It simulates tasks humans actually do: debugging syntactically broken SQL, rewriting legacy queries for efficient execution (e.g. enforcing direct JOINs over table scans), and producing completely new queries that fit within strict computational or token budgets.

## Action Space
The agent responds with a JSON object (`SqlEnvAction`) featuring:
- `action_type`: `str` - Must be either `"test"` (to run a query) or `"submit"` (to finalize and grade).
- `query`: `str` - The SQL query to either try executing or submit as the final answer.

## Observation Space
The environment returns (`SqlEnvObservation`):
- `task_description`: `str` - Objective of the current task.
- `schema_info`: `str` - SQL statements showing table schemas.
- `initial_query`: `Optional[str]` - A starting query to debug or optimize.
- `feedback`: `str` - The response from the SQLite DB. Can be the first 10 rows of an execution, or a syntax error trace.

## Tasks and Difficulty
1. **Easy:** Syntax Fix. The agent is provided a query missing a `JOIN` condition and using an incorrect alias. It must fix the syntax to retrieve matching user order info.
2. **Medium:** Slow Query Optimization. The agent must rewrite an `IN (SELECT...)` subquery to an explicit `JOIN`, ensuring that `EXPLAIN QUERY PLAN` confirms the usage of index-based operations over a simple `SCAN TABLE`.
3. **Hard:** Constrained Generation. The agent generates a 3-table analytical query (groupby/aggregation) from scratch. The environment heavily penalizes queries that exceed the token budget (max 200 characters).

## Setup and Usage
### Using Docker (Hugging Face Spaces compatible)
```bash
docker build -t sql_env -f Dockerfile .
docker run -p 8000:8000 sql_env
