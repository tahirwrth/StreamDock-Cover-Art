import asyncio
import base64
import threading
from typing import Optional, Dict, Any

from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions

from src.core.action import Action
from src.core.logger import Logger
import os


async def get_media_info() -> Optional[Dict[str, Any]]:
    try:
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        if not current_session:
            return None

        info = await current_session.try_get_media_properties_async()
        info_dict = {attr: getattr(info, attr) for attr in dir(info) if not attr.startswith("_")}
        info_dict["genres"] = list(info_dict.get("genres", []))

        if info.thumbnail is not None:
            thumbnail_stream = await info.thumbnail.open_read_async()
            buffer = Buffer(thumbnail_stream.size)
            await thumbnail_stream.read_async(buffer, buffer.capacity, InputStreamOptions.NONE)
            thumbnail_data = bytes(buffer)
            info_dict["thumbnail"] = base64.b64encode(thumbnail_data).decode("utf-8")
        else:
            info_dict["thumbnail"] = None

        playback_info = current_session.get_playback_info()
        info_dict["playback_status"] = playback_info.playback_status.name

        timeline_props = current_session.get_timeline_properties()
        info_dict["current_position"] = int(timeline_props.position.total_seconds())
        info_dict["duration"] = int(timeline_props.end_time.total_seconds())

        return info_dict

    except Exception as e:
        Logger.error(f"[MediaCover] Error fetching media data: {e}")
        return None


class MediaCover(Action):
    POLL_INTERVAL_SECONDS = 0.5

    def __init__(self, action: str, context: str, settings: Dict, plugin):
        super().__init__(action, context, settings, plugin)
        self._loop = None
        self._thread = None
        self._running = True
        self._last_thumbnail_b64: Optional[str] = None

        fallback_path = os.path.join(os.getcwd(), "static", "img", "no-media.png")
        self._fallback_b64 = None
        if os.path.exists(fallback_path):
            with open(fallback_path, "rb") as f:
                self._fallback_b64 = base64.b64encode(f.read()).decode("utf-8")

        Logger.info(f"[MediaCover] Initialized for context {context}")
        self._start_background_loop()

    def _start_background_loop(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, args=(self._loop,), daemon=True)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._poll_media_loop(), self._loop)
        Logger.info("[MediaCover] Background media polling loop started")

    @staticmethod
    def _run_loop(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _poll_media_loop(self):
        while self._running:
            try:
                info = await get_media_info()
                if info and info.get("thumbnail"):
                    thumbnail_b64 = info["thumbnail"]
                    if thumbnail_b64 != self._last_thumbnail_b64:
                        self._last_thumbnail_b64 = thumbnail_b64
                        self._update_key_image(thumbnail_b64, info)
                else:
                    if self._fallback_b64 and self._last_thumbnail_b64 != "fallback":
                        self._last_thumbnail_b64 = "fallback"
                        self._set_fallback_image()
            except Exception as e:
                Logger.error(f"[MediaCover] Error in polling loop: {e}")

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    def _set_fallback_image(self):
        if not self._fallback_b64:
            return
        data_url = f"data:image/png;base64,{self._fallback_b64}"
        self.set_image(data_url)
        Logger.info("[MediaCover] Set fallback image")

    def _update_key_image(self, thumbnail_b64: str, info: Dict[str, Any]):
        try:
            img_bytes = base64.b64decode(thumbnail_b64)
            img = Image.open(BytesIO(img_bytes)).convert("RGB")

            max_size = 200
            img.thumbnail((max_size, max_size), Image.LANCZOS)

            canvas = Image.new("RGB", (max_size, max_size), (0, 0, 0))

            x = (max_size - img.width) // 2
            y = (max_size - img.height) // 2

            rounded = Image.new("RGB", img.size)
            mask = Image.new("L", img.size, 0)
            mdraw = ImageDraw.Draw(mask)
            radius = int(min(img.size) * 0.18)
            mdraw.rounded_rectangle((0, 0, img.width, img.height), radius, fill=255)
            rounded.paste(img, (0, 0), mask)

            canvas.paste(rounded, (x, y), mask)

            buffer = BytesIO()
            canvas.save(buffer, format="PNG")
            processed_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            data_url = f"data:image/png;base64,{processed_b64}"
            self.set_image(data_url)

            title = info.get("title") or ""
            artist = info.get("artist") or ""
            Logger.info(f"[MediaCover] Updated cover art: {title} - {artist}")

        except Exception as e:
            Logger.error(f"[MediaCover] Failed to update key image: {e}")

    def on_will_disappear(self):
        Logger.info(f"[MediaCover] Will disappear for context {self.context}")
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def on_key_down(self, payload: dict):
        Logger.info(f"[MediaCover] Key down: {payload}")