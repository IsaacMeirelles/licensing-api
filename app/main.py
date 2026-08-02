from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import activations, admins, auth, licenses
from app.core.config import get_settings
from app.core.ratelimit import limiter

settings = get_settings()


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "muitas requisicoes, tente novamente mais tarde"},
        headers={"Retry-After": "60"},
    )


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de licenciamento: chaves assinadas Ed25519 + ativacao online.",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(admins.router, prefix="/api/v1/admin", tags=["admins (admin)"])
app.include_router(licenses.router, prefix="/api/v1/admin", tags=["licenses (admin)"])
app.include_router(activations.router, prefix="/api/v1", tags=["ativacao"])


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
