# Task Artifact: LLM Graceful Degradation Iteration

**Time**: 2026-05-23 17:02 (Asia/Shanghai)  
**Task**: 活纸每日迭代 - LLM 失败优雅降级  
**Agent**: cron-iteration agent (qclaw pool-deepseek-v4-pro)

## Objective
Fix LLM call failures in `/api/npc/talk` and `/api/npc/talk_stream` from raising HTTP 502 to gracefully degrading with a humanized NPC response.

## Key Decisions

1. **Fallback function location**: `talk_service.py` — keeps the logic in the same module as other talk-related functions, and generates a valid `NpcResponseSchema` so `apply_npc_reply()` can process it without changes.

2. **7-scenario fallback pool**: Chose varied, plausible Chinese scenarios (走神/被打断/倦极/风/喧哗/低头/灯火) — not all "走神" to maintain variety.

3. **State consistency preserved**: `apply_npc_reply()` is called in fallback path too, ensuring history write, clock advance, and auto-save are not skipped.

4. **No reflection on fallback**: Added `is_fallback` flag to suppress `bg_reflect` when LLM fails (nothing substantive to reflect on).

5. **Incremental field `llm_fallback: true`**: Front-end compatible, no breaking changes.

6. **Streaming endpoint parity**: Both `/api/npc/talk` and `/api/npc/talk_stream` fixed — streaming is used by the frontend.

## Changes Made

| File | Action |
|------|--------|
| `backend/services/talk_service.py` | Added `build_graceful_fallback()` with 7-scenario pool |
| `backend/api/routes.py` | Replaced 502 exception with graceful fallback in both talk endpoints |
| `docs/iterations/2026-05-23_1702.md` | Iteration record written |
| `docs/iterations/task-artifact-20260523-1702-graceful-degradation.md` | This artifact |

## Tests

- Python module import: PASS
- `/api/health` endpoint: PASS
- `/api/hello` endpoint: PASS
- Server starts without import errors: PASS
- Graceful fallback generates valid NpcResponseSchema: PASS

## Git Commit

- Hash: `3ee5aaa`
- Branch: `qclaw`
- Status: committed locally, push failed due to network (GitHub unreachable)
- Push to retry when network is available

## Not Done (Network Issue)

- `git push origin qclaw` — failed with "Connection reset" / "Could not connect to github.com port 443"
