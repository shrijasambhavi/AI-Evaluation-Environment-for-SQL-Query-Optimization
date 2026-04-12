from openenv.core.env_server.http_server import create_app

# Import models + environment (supports both local & packaged execution)
try:
    from ..models import SqlEnvAction, SqlEnvObservation
    from .sql_env_environment import SqlEnvironment
except (ModuleNotFoundError, ImportError):
    from models import SqlEnvAction, SqlEnvObservation
    from server.sql_env_environment import SqlEnvironment

# Create OpenEnv app (this auto-registers /reset, /step, /state)
app = create_app(
    SqlEnvironment,
    SqlEnvAction,
    SqlEnvObservation,
    env_name="sql_env",
    max_concurrent_envs=1,
)

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

def main(host: str = "0.0.0.0", port: int = 7860):
    import uvicorn
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    main(port=args.port)
