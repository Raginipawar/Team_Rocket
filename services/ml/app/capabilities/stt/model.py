"""Real STT: faster-whisper large-v3 + AI4Bharat IndicConformer (technical.md §9.1).
Pipeline (not yet wired): ffmpeg decode -> 16kHz mono -> loudness normalise ->
Silero VAD trim -> Whisper language ID -> route hi/mr to IndicConformer+Whisper
(keep higher confidence), else Whisper."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_stt(audio_bytes: bytes, lang_hint: str | None) -> dict:
    raise ModelNotLoaded(
        "STT models not loaded -- download faster-whisper large-v3 and "
        "AI4Bharat IndicConformer weights, or set ML_MOCK_CAPABILITIES=stt"
    )
