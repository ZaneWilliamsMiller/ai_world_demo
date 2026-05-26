import sys
sys.path.insert(0, r'C:\Users\AAWZV\.qclaw\workspace-ua58rsb93veqtxl7\living-paper')
from backend.config import settings

print(f'llm_base_url: {settings.llm_base_url}')
print(f'llm_model: {settings.llm_model}')
print(f'llm_timeout_s: {settings.llm_timeout_s}')
print(f'llm_pool_max_connections: {settings.llm_pool_max_connections}')
print(f'llm_pool_max_keepalive: {settings.llm_pool_max_keepalive}')
print(f'llm_max_concurrency: {settings.llm_max_concurrency}')

url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
print(f'Constructed URL: {url}')
print(f'Has /v1: {"/v1/" in url}')

# Test both URLs
import httpx, asyncio

async def test():
    async with httpx.AsyncClient(timeout=10) as c:
        # URL without /v1
        try:
            r = await c.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={'Authorization': f'Bearer {settings.llm_api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': settings.llm_model,
                    'messages': [{'role': 'user', 'content': 'say yes'}],
                    'max_tokens': 5
                }
            )
            print(f'Without /v1: {r.status_code} {r.text[:100]}')
        except Exception as e:
            print(f'Without /v1 FAILED: {e}')

        # URL with /v1
        try:
            r = await c.post(
                f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions",
                headers={'Authorization': f'Bearer {settings.llm_api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': settings.llm_model,
                    'messages': [{'role': 'user', 'content': 'say yes'}],
                    'max_tokens': 5
                }
            )
            print(f'With /v1: {r.status_code} {r.text[:100]}')
        except Exception as e:
            print(f'With /v1 FAILED: {e}')

asyncio.run(test())