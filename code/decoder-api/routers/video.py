import json, asyncio
from fastapi import APIRouter, Depends, File, Query, UploadFile, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from typing import Tuple
from db.dependencies import get_redis, get_db_
from repositories.otp_repository import OtpRepository
from repositories.status_repository import StatusRepository
from services.video_service import VideoService, semaphore
from _shared._common.db.nats import js_connect
from core.config import DAV1D_PATH

router = APIRouter(tags=["video"])


def get_otp_repo(redis=Depends(get_redis)) -> OtpRepository:
    return OtpRepository(redis)


def get_video_service() -> VideoService:
    return VideoService()

def get_status_repo(redis=Depends(get_redis), db=Depends(get_db_)) -> StatusRepository:
    return StatusRepository(redis, db)

async def _process_upload(
    file: UploadFile,
    token: str,
    otp_repo: OtpRepository,
    video_service: VideoService,
    status_repo: StatusRepository,
    in_memory: bool = True,
) -> Response:
    print('upload started')
    payload = await otp_repo.consume_upload_token(token)
    await status_repo.create_video('unknown', payload['archive_id'])
    print('token consumed')

    if in_memory:
        file_bytes = await file.read()
        print('file read (in-memory)')
        frame_bytes = await video_service.decode_first_frame(file_bytes, in_memory=True)
    else:
        frame_bytes = await video_service.decode_first_frame_streaming(file, in_memory=False)

    print('decoded')
    js, _ = await js_connect()
    try:
        await js.add_stream(name="NOTIFS", subjects=["notifications"])
    except Exception:
        pass
    await js.publish(
        "notifications",
        payload=json.dumps({"user_id": payload["user_id"], "payload": "123 test"}).encode(),
    )

    return Response(content=frame_bytes, media_type="image/jpeg")


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    token: str = Query(...),
    otp_repo: OtpRepository = Depends(get_otp_repo),
    video_service: VideoService = Depends(get_video_service),
    status_repo: StatusRepository = Depends(get_status_repo)
):
    return await _process_upload(file, token, otp_repo, video_service, status_repo, in_memory=True)


@router.post("/upload_disk")
async def upload_video_disk(
    file: UploadFile = File(...),
    token: str = Query(...),
    otp_repo: OtpRepository = Depends(get_otp_repo),
    video_service: VideoService = Depends(get_video_service),
    status_repo: StatusRepository = Depends(get_status_repo)
):
    return await _process_upload(file, token, otp_repo, video_service, status_repo, in_memory=False)

