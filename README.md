# astrbot-plugin-repeater

语音复读并克隆音色的 AstrBot 插件。

## 功能

- 监听 OneBot v11（aiocqhttp）语音消息。
- 使用 STT 转写语音文本。
- 使用 TTS 的音色克隆接口生成回复语音并发送。

## 配置

在 WebUI 中打开插件配置：

- `enable`：启用开关。
- `stt_provider_id`：选择 STT Provider（建议选择已配置的 OpenAI Whisper 兼容 Provider）。
- `tts_provider_id`：选择 TTS Provider（OpenAI 兼容接口，支持 `audio_sample` 克隆）。
- `text_template`：回复文本模板，使用 `{text}` 占位。
- `clone_response_format`：回复音频格式（推荐 `wav`）。
- `clone_language`：语言设置（默认 `Auto`）。
- `clone_instructions`：TTS 指令（可选）。
- `fallback_to_plain_tts`：克隆失败时是否降级为普通 TTS。

## 说明

插件依赖 AstrBot 已配置的 STT/TTS Provider，并通过 OpenAI 兼容接口调用音色克隆。请确保 TTS 服务支持 `audio_sample` 传参。
