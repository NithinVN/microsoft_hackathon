import os
import time
from collections import deque
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="DemoShop", version="1.2.0")

PRODUCTS: List[Dict[str, Any]] = [
    {"id": 1, "name": "Aurora Lamp", "price": 39.99, "category": "lighting"},
    {"id": 2, "name": "Nimbus Speaker", "price": 79.99, "category": "audio"},
    {"id": 3, "name": "Atlas Backpack", "price": 59.99, "category": "travel"},
]

request_history: deque[int] = deque(maxlen=200)
error_history: deque[int] = deque(maxlen=200)
request_counter = 0
error_counter = 0


def read_bool(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def read_float(name: str, default: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@app.middleware("http")
async def capture_metrics(request: Request, call_next):
    global request_counter, error_counter
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    request_history.append(elapsed_ms)
    request_counter += 1
    if response.status_code >= 400:
        error_counter += 1
        error_history.append(elapsed_ms)
    return response


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse("""
    <html><head><title>DemoShop</title><style>
      body { font-family: Arial, sans-serif; background: #f3f4f6; margin: 0; padding: 32px; }
      .card { background: white; border-radius: 12px; max-width: 980px; margin: 0 auto; padding: 24px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
      .product { display: inline-block; margin: 16px; padding: 16px; border: 1px solid #ddd; border-radius: 12px; width: 220px; }
      h1 { margin-bottom: 8px; }
    </style></head><body>
      <div class="card">
        <h1>DemoShop</h1>
        <p>Small storefront for IncidentMind integration testing.</p>
        <div>
          <div class="product"><h3>Aurora Lamp</h3><p>$39.99</p><a href="/products/1">View</a></div>
          <div class="product"><h3>Nimbus Speaker</h3><p>$79.99</p><a href="/products/2">View</a></div>
          <div class="product"><h3>Atlas Backpack</h3><p>$59.99</p><a href="/products/3">View</a></div>
        </div>
      </div>
    </body></html>
    """)


@app.get("/products")
async def list_products():
    if read_bool("SLOW_API"):
        time.sleep(3)
    return {"products": PRODUCTS}


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    product = next((item for item in PRODUCTS if item["id"] == product_id), None)
    if product is None:
        return JSONResponse(status_code=404, content={"error": "Product not found"})
    return product


@app.get("/dependency/status")
async def dependency_status():
    if read_bool("DEPENDENCY_UNAVAILABLE"):
        return JSONResponse(status_code=503, content={"status": "unavailable", "service": "payments-api"})
    return {"status": "available", "service": "payments-api"}


@app.post("/checkout")
async def checkout():
    if read_bool("DEPENDENCY_UNAVAILABLE"):
        return JSONResponse(status_code=503, content={"error": "Payment dependency unavailable", "status": "dependency_unavailable"})

    fail_rate = read_float("CHECKOUT_FAILURE_RATE", 0.0)
    if fail_rate > 0:
        import random
        if random.random() < fail_rate:
            return JSONResponse(status_code=500, content={"error": "Checkout failed", "status": "internal_error"})

    return {
        "status": "success",
        "order_id": "ORDER-1001",
        "total": 119.97,
        "items": [1, 2],
    }


@app.get("/health")
async def health():
    service_status = "healthy"
    if read_bool("DEPENDENCY_UNAVAILABLE") or read_bool("HIGH_DB_POOL"):
        service_status = "degraded"
    return {
        "status": service_status,
        "service": "demo-shop",
        "version": "1.2.0",
        "dependencies": "unavailable" if read_bool("DEPENDENCY_UNAVAILABLE") else "available",
        "database": "degraded" if read_bool("HIGH_DB_POOL") else "healthy",
    }


@app.get("/metrics")
async def metrics():
    request_total = request_counter or 1
    error_total = error_counter
    observed_error_rate = error_total / request_total
    configured_checkout_failure_rate = read_float("CHECKOUT_FAILURE_RATE", 0.0)
    avg_latency = sum(request_history) / len(request_history) if request_history else 0
    db_pool_usage = 98 if read_bool("HIGH_DB_POOL") else 52
    dependency_status = "unavailable" if read_bool("DEPENDENCY_UNAVAILABLE") else "available"
    active_failures = []
    if read_bool("SLOW_API"):
        active_failures.append("slow_api")
    if read_bool("DEPENDENCY_UNAVAILABLE"):
        active_failures.append("dependency_unavailable")
    if configured_checkout_failure_rate > 0:
        active_failures.append("checkout_failures")
    if read_bool("HIGH_DB_POOL"):
        active_failures.append("high_db_pool")

    return {
        "service": "demo-shop",
        "request_count": request_total,
        "error_count": error_total,
        "error_rate": round(observed_error_rate, 4),
        "checkout_failure_probability": round(configured_checkout_failure_rate, 4),
        "observed_checkout_error_rate": round(observed_error_rate, 4),
        "average_response_time_ms": int(avg_latency),
        "database_pool_usage_percent": db_pool_usage,
        "dependency_status": dependency_status,
        "active_failure_modes": active_failures,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=False)
