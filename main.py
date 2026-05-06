from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_pool, run_migrations
from routers import auth_router, datesheets, marks, results, users, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    run_migrations()
    yield


app = FastAPI(
    title="UAMP — Exam & Result Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "https://exam-result-gamma.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(datesheets.router, prefix="/api/v1/exam/datesheets", tags=["Datesheets"])
app.include_router(marks.router, prefix="/api/v1/exam/marks", tags=["Marks"])
app.include_router(results.router, prefix="/api/v1/exam/results", tags=["Results"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/")
def root():
    return {"status": "ok", "system": "UAMP RMS API v1.0"}
