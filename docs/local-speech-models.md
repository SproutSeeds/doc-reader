# Local speech models for ClawDad

The shared speech service supports Kokoro 82M, Pocket TTS 3.1 and Kitten TTS Mini
0.8. ClawDad reads `/v1/voices` to show every bundled voice: 54, 26 and 8
respectively. The catalog includes language and publisher-provided voice gender;
unspecified gender remains unspecified. It does not invent emotional styles.
Kokoro and Kitten expose speed. Pocket uses its natural speaking pace.

Install in the existing local speech environment:

```sh
uv pip install --python /path/to/tts-local/.venv/bin/python -r requirements-local-speech.txt
/path/to/tts-local/.venv/bin/python -m unidic download
python -m doc_reader.tts_service --host 127.0.0.1 --port 8772 --engines kokoro,pocket,kitten,whisper --device cpu
```

Use the environment's Python for the service command. Preserve the host's current
Whisper configuration and service environment. Japanese Kokoro requires the UniDic
dictionary; the other language resources and model weights download on first use
and remain in the local model cache. Pocket's non-English voices select their
matching language model automatically. Inference runs on the paired Mac. ClawDad
uses its existing authenticated connection to deliver audio to the phone.

The Mac installation uses `~/.doc-reader-managed/doc_reader/` and LaunchAgent
`~/Library/LaunchAgents/com.docreader.tts-local.plist`. Deploy both
`tts_service.py` and `local_voices.py`, then update the existing `--engines`
argument and reload the LaunchAgent. Back up the existing source and plist before
replacing them. Leave unrelated Doc Reader application files in place.

Verify `/healthz`, `/v1/voices`, and actual WAV generation for each engine. The
September 6 integration generated valid audio for all 88 voices, including five
Japanese voices after installing UniDic. Tests cover voice validation, model
routing, and agreement with Pocket's installed voice catalog. Audible quality and
phone playback latency require listening on the intended device.

Source catalogs: [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md),
[Pocket TTS](https://github.com/kyutai-labs/pocket-tts),
[Kitten TTS](https://github.com/KittenML/KittenTTS).
