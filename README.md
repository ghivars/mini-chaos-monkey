# Mini Chaos Monkey

A tiny, dependency-free (Python stdlib only) re-implementation of the idea behind Netflix's
**Chaos Monkey**: randomly kill production instances on purpose, so you find out what breaks
*before* a real outage does.

> Inspired by: Netflix Tech Blog — "The Netflix Simian Army" (2011)
> https://netflixtechblog.com/the-netflix-simian-army-16e57fbab116
> Original tool: https://github.com/Netflix/chaosmonkey

## What it does

```
load generator ──► gateway :8100 ──► backend :8101
   (8 threads)       (naive or        backend :8102
                      resilient)      backend :8103
                                         ▲
                     chaos monkey ───────┘ kills a random backend every 1–2 s
                     supervisor   ───────► restarts it 1.5 s later
```

The experiment runs three scenarios and compares them:

1. **baseline**: no chaos
2. **naive + chaos**: blind round-robin, no retries
3. **resilient + chaos**: active health checks, mark-down on failure, retry on another instance, short timeouts

## Results (10 s per scenario, seed 42, 7 kills)

| Scenario | Requests | Failed | Success | p50 (ms) | p99 (ms) |
|---|---:|---:|---:|---:|---:|
| baseline | 5660 | 0 | 100.00% | 11.7 | 36.0 |
| naive + chaos | 1323 | 130 | 90.17% | 11.9 | 521.7 |
| resilient + chaos | 4173 | 3 | 99.93% | 12.0 | 200.3 |

## What broke first (findings)

1. **Naive round-robin keeps sending traffic to dead instances.** About 1 in 10 requests failed.
2. **Throughput collapsed, not just availability.** Each request to a dead instance had to
   wait for a timeout, which tied up client threads, so the naive run served about 4× fewer requests.
   Failures cost you latency budget everywhere, not only on the failed calls.
3. **Retries + health checks fix most of it, but not all.** 3 requests still failed. My guess
   is that every retry landed on instances that were down or still booting at the same moment.
   Next steps: retry with backoff/jitter, and a readiness check separate from liveness.
4. **p99 is the honest metric.** p50 barely moved across scenarios, while p99 rose 6–14×.

## Run it

```bash
python experiment.py --duration 15 --seed 42
```

Requires Python 3.9+. No packages to install.

## Files

| File | Purpose |
|---|---|
| `backend.py` | the service being attacked (`/health`, `/work`) |
| `gateway.py` | load balancer, `naive` or `resilient` mode |
| `chaos_monkey.py` | process fleet, the monkey, the supervisor |
| `loadtest.py` | concurrent load generator + p50/p99 |
| `experiment.py` | runs all scenarios and prints the table |

## Ideas to extend

- Run it against Docker Compose containers (`docker kill`) instead of local processes
- Latency Monkey: inject slow responses instead of crashes (Netflix did this too)
- Circuit breaker in the gateway, then measure the difference
- Plot the success rate over time against the kill events
