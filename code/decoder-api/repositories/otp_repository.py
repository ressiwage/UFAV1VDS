import json
from fastapi import HTTPException


class OtpRepository:
    def __init__(self, redis):
        self.redis = redis

    async def consume_upload_token(self, token: str) -> dict:
        raw = await self.redis.getdel(f"otp:upload:{token}")
        if raw is None:
            raise HTTPException(status_code=401, detail="Invalid or expired upload token")
        return json.loads(raw)