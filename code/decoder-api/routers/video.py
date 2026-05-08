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
    file_bytes = await file.read()
    print('file read')
    frame_bytes = await video_service.decode_first_frame(file_bytes, in_memory=in_memory)
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


async def _stream_decode(request: Request) :
    proc = await asyncio.create_subprocess_exec(
        DAV1D_PATH,
        "-i", "/dev/stdin",
        "-o", "/dev/stdout",
        "--threads", "1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def feed_stdin():
        try:
            async for chunk in request.stream():
                print('wc', chunk[:4])
                proc.stdin.write(chunk)
                await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # dav1d завершился раньше — нормально
        finally:
            proc.stdin.close()

    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=8)

    async def read_stdout():
        while chunk := await proc.stdout.read(65536):
            print('wc', chunk[:4])
            await queue.put(chunk)
        await queue.put(None)  # sentinel

    feed_task   = asyncio.create_task(feed_stdin())
    reader_task = asyncio.create_task(read_stdout())

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk

    await asyncio.gather(feed_task, reader_task)
    await proc.wait()