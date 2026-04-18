from __future__ import annotations

import uuid
from pathlib import Path

import httpx

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Record
from astrbot.api.star import Context, Star, register
from astrbot.core.provider.provider import STTProvider, TTSProvider
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path


@register("astrbot_plugin_repeater", "Denmouv", "语音复读并克隆音色", "0.1.0")
class VoiceRepeater(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _is_enabled(self) -> bool:
        return bool(self.config.get("enable", True))

    def _get_config_str(self, key: str, default: str = "") -> str:
        value = self.config.get(key, default)
        if value is None:
            return default
        return str(value).strip()

    def _resolve_stt_provider(self, event: AstrMessageEvent) -> STTProvider | None:
        provider_id = self._get_config_str("stt_provider_id")
        if provider_id:
            provider = self.context.get_provider_by_id(provider_id)
            if isinstance(provider, STTProvider):
                return provider
            logger.warning("Configured STT provider is not available: %s", provider_id)
        return self.context.get_using_stt_provider(event.unified_msg_origin)

    def _resolve_tts_provider(self, event: AstrMessageEvent) -> TTSProvider | None:
        provider_id = self._get_config_str("tts_provider_id")
        if provider_id:
            provider = self.context.get_provider_by_id(provider_id)
            if isinstance(provider, TTSProvider):
                return provider
            logger.warning("Configured TTS provider is not available: %s", provider_id)
        return self.context.get_using_tts_provider(event.unified_msg_origin)

    def _build_text(self, raw_text: str) -> str:
        template = self._get_config_str("text_template", "{text}") or "{text}"
        return template.replace("{text}", raw_text)

    async def _find_record(self, event: AstrMessageEvent) -> Record | None:
        for segment in event.get_messages():
            if isinstance(segment, Record):
                return segment
        return None

    async def _transcribe(self, stt_provider: STTProvider, audio_path: Path) -> str:
        text = await stt_provider.get_text(str(audio_path))
        return text.strip()

    async def _clone_tts_via_openai_api(
        self,
        tts_provider: TTSProvider,
        text: str,
        audio_path: Path,
    ) -> Path:
        provider_config = tts_provider.provider_config
        api_base = str(provider_config.get("api_base", "")).rstrip("/")
        if not api_base:
            raise ValueError("TTS provider api_base is empty")

        model = str(provider_config.get("model", ""))
        voice = str(provider_config.get("openai-tts-voice", "alloy"))
        response_format = self._get_config_str("clone_response_format", "wav") or "wav"
        language = self._get_config_str("clone_language", "Auto") or "Auto"
        instructions = self._get_config_str("clone_instructions", "")
        api_key = str(provider_config.get("api_key", ""))

        url = f"{api_base}/audio/speech"
        data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
            "language": language,
            "audio_sample_text": text,
        }
        if instructions:
            data["instructions"] = instructions

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        timeout = provider_config.get("timeout", 60)
        if isinstance(timeout, str):
            timeout = int(timeout)

        temp_dir = Path(get_astrbot_temp_path())
        temp_dir.mkdir(parents=True, exist_ok=True)
        out_path = temp_dir / f"voice_repeater_{uuid.uuid4().hex}.{response_format}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            with audio_path.open("rb") as audio_file:
                files = {
                    "audio_sample": (
                        audio_path.name,
                        audio_file,
                        "application/octet-stream",
                    )
                }
                resp = await client.post(url, data=data, files=files, headers=headers)
                resp.raise_for_status()
                out_path.write_bytes(resp.content)

        return out_path

    async def _tts_fallback(self, tts_provider: TTSProvider, text: str) -> Path:
        audio_path = await tts_provider.get_audio(text)
        return Path(audio_path)

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if not self._is_enabled():
            return
        if event.get_sender_id() == event.get_self_id():
            return

        record = await self._find_record(event)
        if not record:
            return

        stt_provider = self._resolve_stt_provider(event)
        if not stt_provider:
            logger.warning("No STT provider available, skip voice repeater.")
            return

        tts_provider = self._resolve_tts_provider(event)
        if not tts_provider:
            logger.warning("No TTS provider available, skip voice repeater.")
            return

        try:
            audio_path = Path(await record.convert_to_file_path())
            event.track_temporary_local_file(str(audio_path))
        except Exception as exc:
            logger.warning("Failed to resolve record audio path: %s", exc)
            return

        try:
            text = await self._transcribe(stt_provider, audio_path)
        except Exception as exc:
            logger.warning("STT failed: %s", exc)
            return

        if not text:
            logger.info("STT returned empty text, skip reply.")
            return

        reply_text = self._build_text(text)
        audio_reply_path: Path | None = None

        try:
            audio_reply_path = await self._clone_tts_via_openai_api(
                tts_provider=tts_provider,
                text=reply_text,
                audio_path=audio_path,
            )
        except Exception as exc:
            logger.warning("Voice clone failed: %s", exc)
            if not self.config.get("fallback_to_plain_tts", True):
                return
            try:
                audio_reply_path = await self._tts_fallback(tts_provider, reply_text)
            except Exception as fallback_exc:
                logger.warning("Fallback TTS failed: %s", fallback_exc)
                return

        if not audio_reply_path or not audio_reply_path.exists():
            logger.warning("Generated audio file missing.")
            return

        event.track_temporary_local_file(str(audio_reply_path))
        yield event.chain_result([Record.fromFileSystem(str(audio_reply_path))])
