import io
import os
import subprocess
import tempfile

from fastapi import HTTPException, UploadFile
from PIL import Image

from core.config import DAV1D_PATH, MAX_CONCURRENT

import asyncio

semaphore = asyncio.Semaphore(MAX_CONCURRENT)

CHUNK_SIZE = 1024 * 1024  # 1 MB


class VideoService:

    async def _run(self, *args: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d failed: {stderr.decode()}",
            )

    async def decode_first_frame(self, file_bytes: bytes, in_memory: bool = True) -> bytes:
        tmpdir_kwargs: dict = {'dir': '/dev/shm'} if in_memory else dict()
        with tempfile.TemporaryDirectory(**tmpdir_kwargs) as tmpdir:
            input_path = os.path.join(tmpdir, "input.obu")
            frame_y4m = os.path.join(tmpdir, "frame.y4m")

            with open(input_path, "wb") as f:
                f.write(file_bytes)

            await self._run(DAV1D_PATH, "-i", input_path, "--threads", "1", "-o", "/dev/null")
            await self._run(
                DAV1D_PATH, "-i", input_path, "-o", frame_y4m,
                "--threads", "1", "--limit", "1",
            )
            return self._y4m_to_jpeg(frame_y4m)

    async def decode_first_frame_streaming(self, file: UploadFile, in_memory: bool = False) -> bytes:
        """
        Стримим файл чанками на диск, не загружая его целиком в память.
        in_memory=False → tmpdir на обычном диске (не /dev/shm).
        """
        tmpdir_kwargs: dict = {'dir': '/dev/shm'} if in_memory else dict()
        with tempfile.TemporaryDirectory(**tmpdir_kwargs) as tmpdir:
            input_path = os.path.join(tmpdir, "input.obu")
            frame_y4m = os.path.join(tmpdir, "frame.y4m")

            # Пишем файл на диск чанками — RAM не растёт
            with open(input_path, "wb") as f:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)

            print(f'file streamed to disk: {input_path}')

            await self._run(DAV1D_PATH, "-i", input_path, "--threads", "1", "-o", "/dev/null")
            await self._run(
                DAV1D_PATH, "-i", input_path, "-o", frame_y4m,
                "--threads", "1", "--limit", "1",
            )
            # _y4m_to_jpeg читает с диска — не держит весь файл в памяти
            return self._y4m_to_jpeg(frame_y4m)

    def _y4m_to_jpeg(self, y4m_path: str, quality: int = 85) -> bytes:
        with open(y4m_path, "rb") as f:
            raw = f.read()

        header_end = raw.index(b"\n")
        header = raw[:header_end].decode()
        params = {
            token[0]: token[1:]
            for token in header.split()
            if len(token) > 1 and token[0] in "WHC"
        }
        width = int(params["W"])
        height = int(params["H"])
        color_space = params.get("C", "420")

        frame_start = raw.index(b"FRAME", header_end) + len(b"FRAME")
        frame_start = raw.index(b"\n", frame_start) + 1

        img = self._decode_planes(raw, frame_start, width, height, color_space)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    def _decode_planes(self, raw: bytes, offset: int, width: int, height: int, color_space: str) -> Image.Image:
        if color_space.startswith("420"):
            y_size = width * height
            uv_size = (width // 2) * (height // 2)
            y  = raw[offset : offset + y_size]
            cb = raw[offset + y_size : offset + y_size + uv_size]
            cr = raw[offset + y_size + uv_size : offset + y_size + uv_size * 2]
            y_plane  = Image.frombytes("L", (width, height), y)
            cb_plane = Image.frombytes("L", (width // 2, height // 2), cb).resize((width, height), Image.BILINEAR)
            cr_plane = Image.frombytes("L", (width // 2, height // 2), cr).resize((width, height), Image.BILINEAR)
            return Image.merge("YCbCr", (y_plane, cb_plane, cr_plane)).convert("RGB")

        if color_space.startswith("444"):
            plane_size = width * height
            y  = raw[offset : offset + plane_size]
            cb = raw[offset + plane_size : offset + plane_size * 2]
            cr = raw[offset + plane_size * 2 : offset + plane_size * 3]
            y_plane  = Image.frombytes("L", (width, height), y)
            cb_plane = Image.frombytes("L", (width, height), cb)
            cr_plane = Image.frombytes("L", (width, height), cr)
            return Image.merge("YCbCr", (y_plane, cb_plane, cr_plane)).convert("RGB")

        if color_space.startswith("mono"):
            y = raw[offset : offset + width * height]
            return Image.frombytes("L", (width, height), y).convert("RGB")

        raise ValueError(f"Неподдерживаемый цветовой формат Y4M: {color_space}")