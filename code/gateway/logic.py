from config import CPU_THRESHOLD, RAM_THRESHOLD, DISK_THRESHOLD
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, Form, File, Request, Response, Query, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import  AsyncSession
from _shared._common.models.models import Archives
from sqlalchemy import select
import asyncio, json, time, httpx, os, secrets
import redis.asyncio as aioredis
from redis import Redis
from contextlib import asynccontextmanager
COMMON_SERV = os.environ['COMMON_API'] #auth, archives


def server_rank_key(server):
    cpu = server['cpu']
    ram = server['ram']
    disk = server['disk']
    sid = server['id']
    
    cpu_score = cpu if cpu < CPU_THRESHOLD else 1
    ram_score = -ram if ram > RAM_THRESHOLD else 1
    disk_score = -disk if disk > DISK_THRESHOLD else 1
    
    return (cpu_score, ram_score, disk_score, sid)
 

async def validate_bearer_via_common(authorization: str) -> dict:
    """
    Проверяем access_token через /user на auth-сервисе.
    Возвращает {"id": ..., "username": ...} или кидает 401.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{COMMON_SERV}/user",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    return resp.json()


async def issue_upload_otp(redis_client:Redis, user_id: int, necessary_ram: int, archive_id:int, OTP_TTL: int) -> str:
    """
    Генерирует одноразовый токен, кладёт в Redis с TTL.
    Структура ключа: otp:upload:<token>
    Значение: JSON {user_id, necessary_ram}
    """
    token = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user_id, "necessary_ram": necessary_ram, "archive_id":archive_id})
    await redis_client.setex(f"otp:upload:{token}", OTP_TTL, payload)
    return token


async def consume_upload_otp(redis_client, token: str) -> dict:
    """
    Атомарно читает и удаляет токен (GETDEL).
    Возвращает payload или кидает 401.
    """
    raw = await redis_client.getdel(f"otp:upload:{token}")
    if raw is None:
        raise HTTPException(status_code=401, detail="Invalid or expired upload token")
    return json.loads(raw)

async def get_archive_id(db: AsyncSession, user_id):
    if (aid:=(await db.execute(select(Archives).where(Archives.user_id==str(user_id)))).scalar_one_or_none()) is not None:
        return aid.id
    na = Archives(
        name = 'default',
        user_id=str(user_id)
    )
    db.add(na)
    await db.commit()
    await db.refresh(na)
    return na.id
