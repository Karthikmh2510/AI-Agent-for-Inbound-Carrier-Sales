import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from routes.loads import router as loads_router
from routes.verify import router as verify_router
from routes.negotiate import router as negotiate_router

load_dotenv()

# Ensure the environment variable for the API key is set
API_HEADER = "x-api-key"
API_KEY    = os.getenv("HAPPYROBOT_REST_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "Environment variable HAPPYROBOT_REST_API_KEY is not set. "
        "Add it with `flyctl secrets set HAPPYROBOT_REST_API_KEY=abcd1234`."
    )

app = FastAPI(title="Inbound Carrier Sales API")

# ── middleware: header-based auth ─────────────────────────────────────────────
@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    # allow health-checks and docs without auth
    if request.url.path in {"/ping", "/docs", "/openapi.json"}:
        return await call_next(request)

    if request.headers.get(API_HEADER) != API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized – missing or invalid x-api-key"},
        )
    return await call_next(request)

# ── routers ───────────────────────────────────────────────────────────────────
app.include_router(loads_router)
app.include_router(verify_router)
app.include_router(negotiate_router)

# ── health-check ─────────────────────────────────────────────────────────────
@app.get("/ping")
def pong():
    return {"ping": "pong"}


# ── local debug entrypoint ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)

