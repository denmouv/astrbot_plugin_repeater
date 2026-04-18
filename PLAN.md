# 语音复读插件计划

## 目标
- 在插件开启时监听消息。
- 当接收到语音消息（Record）时：
  1) 取到语音文件并进行 STT 转写；
  2) 使用该语音作为音色样本进行 TTS 克隆；
  3) 将生成的克隆语音回复给用户。

## 设计要点
- 使用 AstrBot `Record` 消息段读取语音文件。
- 通过 `Context.get_using_stt_provider()` 或配置指定 STT Provider 获取转写文本。
- 通过配置指定 TTS Provider 的 OpenAI 兼容接口，使用 multipart 上传 `audio_sample` 实现克隆。
- 发送 `Record` 语音消息（wav）。
- 使用插件配置 `_conf_schema.json` 支持启用开关与 Provider 选择。

## 实施步骤
1. 更新插件元数据（名称、描述、支持平台）。
2. 添加 `_conf_schema.json`，支持开关与 Provider 选择。
3. 重写 `main.py`：监听语音消息、调用 STT、调用 TTS 克隆、发送语音。
4. 简要更新 README 说明使用方式与配置。

## 验收标准
- 插件开启后，收到语音即回复克隆语音。
- 未配置 STT/TTS 时不会崩溃并给出日志提示。
- 仅在 OneBot (aiocqhttp) 平台触发。
