import json
from fastapi import HTTPException
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from _shared._common.models.models import Videos

class StatusRepository:
    def __init__(self, redis, db):
        self.redis:Redis = redis
        self.db:AsyncSession = db

    async def create_video(self, name, archive_id) -> int:
        nv = Videos(
            name=name,
            is_processed=False,
            archive_id=archive_id
        )
        self.db.add(nv)
        await self.db.commit()
        await self.db.refresh(nv)
        return nv.id
    
    async def get_video_status(self, video_id):
        return self.redis.get(f"video:status:{video_id}")
    
    async def set_video_status(self, video_id, status:str):
        '''status is {uploaded, queued, processing, done, failed, retrying}'''
        self.redis.set(f"video:status:{video_id}", status)

        this_video = (await self.db.execute(select(Videos).where(Videos.id==video_id))).scalar_one_or_none()
        if this_video is None:
            raise Exception('no such video')
        if status=='done':
            await self.db.execute(update(Videos).where(Videos.id==video_id).values(is_processed=True))