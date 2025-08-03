from fastapi import FastAPI
from routes.loads import router as loads_router
from routes.verify import router as verify_router
from routes.negotiate import router as negotiate_router

app = FastAPI(title="Inbound Carrier Sales API")

app.include_router(loads_router)
app.include_router(verify_router)
app.include_router(negotiate_router)

# health-check
@app.get("/ping")
def pong():
    return {"ping": "pong"}

# Main
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)

