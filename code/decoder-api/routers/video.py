import json
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from db.dependencies import get_redis
from repositories.otp_repository import OtpRepository
from services.video_service import VideoService
from _shared._common.db.nats import js_connect

router = APIRouter(tags=["video"])


def get_otp_repo(redis=Depends(get_redis)) -> OtpRepository:
    return OtpRepository(redis)


def get_video_service() -> VideoService:
    return VideoService()


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    token: str = Query(..., description="Одноразовый токен из /upload/token"),
    otp_repo: OtpRepository = Depends(get_otp_repo),
    video_service: VideoService = Depends(get_video_service),
):
    payload = await otp_repo.consume_upload_token(token)

    file_bytes = await file.read()
    frame_bytes = video_service.decode_first_frame(file_bytes)

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