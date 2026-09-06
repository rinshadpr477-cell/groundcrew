"""Simple concurrent load test against the read-heavy /triage/queue endpoint.
Reports throughput and latency percentiles. Requires the API server to already be running.

Usage: python load_test.py [concurrency] [total_requests]
Example: python load_test.py 20 200   -> 20 concurrent workers, 200 total requests
"""

import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

API_URL = "http://127.0.0.1:8000/triage/queue"


def _one_request() -> tuple[float, int]:
    start = time.perf_counter()
    try:
        response = httpx.get(API_URL, timeout=10)
        status = response.status_code
    except httpx.HTTPError:
        status = -1
    elapsed = time.perf_counter() - start
    return elapsed, status


def run_load_test(concurrency: int, total_requests: int) -> None:
    print(f"Load testing {API_URL} — {total_requests} requests, {concurrency} concurrent workers\n")
    latencies: list[float] = []
    errors = 0

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_one_request) for _ in range(total_requests)]
        for future in as_completed(futures):
            elapsed, status = future.result()
            latencies.append(elapsed)
            if status != 200:
                errors += 1
    total_seconds = time.perf_counter() - start

    latencies_ms = sorted(l * 1000 for l in latencies)
    p50 = latencies_ms[int(len(latencies_ms) * 0.50)]
    p95 = latencies_ms[min(int(len(latencies_ms) * 0.95), len(latencies_ms) - 1)]
    p99 = latencies_ms[min(int(len(latencies_ms) * 0.99), len(latencies_ms) - 1)]

    print(f"Total time:      {total_seconds:.2f}s")
    print(f"Throughput:      {total_requests / total_seconds:.1f} req/s")
    print(f"Errors:          {errors}/{total_requests}")
    print(f"Latency p50:     {p50:.1f}ms")
    print(f"Latency p95:     {p95:.1f}ms")
    print(f"Latency p99:     {p99:.1f}ms")
    print(f"Latency mean:    {statistics.mean(latencies_ms):.1f}ms")
    print(f"Latency max:     {max(latencies_ms):.1f}ms")


if __name__ == "__main__":
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    total_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    run_load_test(concurrency, total_requests)