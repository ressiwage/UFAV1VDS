import io
import os
import subprocess
import tempfile

from fastapi import HTTPException
from PIL import Image

from core.config import DAV1D_PATH

import asyncio
import subprocess


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

    async def decode_first_frame(self, file_bytes: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.obu")
            frame_y4m = os.path.join(tmpdir, "frame.y4m")

            with open(input_path, "wb") as f:
                f.write(file_bytes)

            await self._run(DAV1D_PATH, "-i", input_path, "-o", "/dev/null")
            await self._run(
                DAV1D_PATH, "-i", input_path, "-o", frame_y4m,
                "--threads", "1", "--limit", "1",
            )
            return self._y4m_to_jpeg(frame_y4m)

    def _validate(self, input_path: str) -> None:
        result = subprocess.run(
            [DAV1D_PATH, "-i", input_path, "-o", "/dev/null"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d decode failed: {result.stderr.decode()}",
            )

    def _decode_first_frame(self, input_path: str, output_path: str) -> None:
        result = subprocess.run(
            [DAV1D_PATH, "-i", input_path, "-o", output_path, "--threads", "1", "--limit", "1"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=f"dav1d first-frame decode failed: {result.stderr.decode()}",
            )

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