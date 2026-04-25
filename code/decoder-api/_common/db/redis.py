import os
import redis.asyncio as aioredis


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


redis_client: aioredis.Redis | None = None