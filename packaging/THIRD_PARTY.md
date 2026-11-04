Doc Reader is MIT licensed. Copyright and attribution are in LICENSE.txt.

The desktop distribution includes CPython from Astral python-build-standalone,
with its licenses retained in runtime. Python package licenses and notices are
retained in each package's dist-info directory. runtime-packages.json records the
exact installed versions for each build.

Kokoro 82M weights (Apache-2.0): https://huggingface.co/hexgrad/Kokoro-82M
Whisper weights (MIT): https://github.com/openai/whisper
faster-whisper (MIT): https://github.com/SYSTRAN/faster-whisper
eSpeak NG (GPL-3.0): https://github.com/espeak-ng/espeak-ng
espeakng-loader sources/build instructions: https://github.com/thewh1teagle/espeakng-loader
FFmpeg bundled by imageio-ffmpeg (see bundled binary license):
https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0
Binary build sources and scripts: https://github.com/imageio/imageio-binaries

Additional GPL/LGPL license texts are in licenses/. The FFmpeg executable has
GPL-enabled codecs; its license differs from the Python wrapper's BSD license.
FFmpeg source: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz
eSpeak NG source: https://github.com/espeak-ng/espeak-ng/tree/4870adfa25b1a32b4361592f1be8a40337c58d6c
Intel Mac packaging links CTranslate2 to the OpenMP runtime already loaded by
PyTorch. The build adjustment is recorded in packaging/build_desktop.py.

Models download from Hugging Face when first used. An internet connection is
needed for that download; local reading and transcription then run on the device.
The Windows interface builds on Aaron Tate's original Windows integration.
