"""Versioned, local-only voice catalog used by ClawDad and the speech sidecar.

Sources: hexgrad/Kokoro-82M voices; pocket-tts 3.1.0 predefined voices;
KittenML/kitten-tts-mini-0.8 config.json. Never accept arbitrary voice URLs.
"""
from __future__ import annotations

import importlib.util

KOKORO = """af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky
am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa
bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis
ef_dora em_alex em_santa ff_siwis hf_alpha hf_beta hm_omega hm_psi if_sara im_nicola
jf_alpha jf_gongitsune jf_nezumi jf_tebukuro jm_kumo pf_dora pm_alex pm_santa
zf_xiaobei zf_xiaoni zf_xiaoxiao zf_xiaoyi zm_yunjian zm_yunxi zm_yunxia zm_yunyang""".split()
LANGUAGES = {
    "a": "English (US)", "b": "English (UK)", "e": "Spanish", "f": "French",
    "h": "Hindi", "i": "Italian", "j": "Japanese", "p": "Portuguese (Brazil)", "z": "Mandarin",
}
POCKET = "alba anna azelma bill_boerst caro_davy charles cosette eponine eve fantine george jane javert jean marius mary michael paul peter_yearsley stuart_bell vera giovanni lola juergen rafael estelle".split()
POCKET_LANGUAGES = {
    "giovanni": ("italian", "Italian"), "lola": ("spanish_24l", "Spanish"),
    "juergen": ("german_24l", "German"), "rafael": ("portuguese", "Portuguese"),
    "estelle": ("french_24l", "French"),
}
KITTEN = {"Bella": "female", "Jasper": "male", "Luna": "female", "Bruno": "male",
          "Rosie": "female", "Hugo": "male", "Kiki": "female", "Leo": "male"}
MODELS = {
    "kokoro": {"name": "Kokoro", "modelId": "kokoro-82m-v1", "defaultVoice": "af_heart", "package": "kokoro", "sizeLabel": "82M parameters", "supportsSpeed": True},
    "pocket": {"name": "Pocket TTS", "modelId": "pocket-tts-3.1", "defaultVoice": "alba", "package": "pocket_tts", "sizeLabel": "100M parameters; language models download separately", "supportsSpeed": False},
    "kitten": {"name": "Kitten TTS", "modelId": "kitten-tts-mini-0.8", "defaultVoice": "Bella", "package": "kittentts", "sizeLabel": "80 MB model", "supportsSpeed": True},
}

PREVIEWS = {
    "English": "You can keep listening while you move between projects. Choose a voice that feels comfortable for longer responses.",
    "Spanish": "Puedes seguir escuchando mientras cambias de proyecto. Elige una voz cómoda para respuestas largas.",
    "French": "Vous pouvez continuer à écouter en changeant de projet. Choisissez une voix agréable pour les longues réponses.",
    "Hindi": "आप प्रोजेक्ट बदलते समय भी सुनना जारी रख सकते हैं। लंबे उत्तरों के लिए एक आरामदायक आवाज़ चुनें।",
    "Italian": "Puoi continuare ad ascoltare mentre cambi progetto. Scegli una voce piacevole per le risposte lunghe.",
    "Japanese": "プロジェクトを切り替えても音声を聞き続けられます。長い回答でも聞きやすい声を選んでください。",
    "Portuguese": "Pode continuar a ouvir enquanto muda de projeto. Escolha uma voz confortável para respostas longas.",
    "Mandarin": "切换项目时，您可以继续收听。请选择一种适合长时间聆听的声音。",
    "German": "Du kannst weiter zuhören, während du zwischen Projekten wechselst. Wähle eine angenehme Stimme für längere Antworten.",
}


def voices_for(engine: str) -> list[dict]:
    if engine == "kokoro":
        return [{"id": name, "name": name[3:].replace("_", " ").title(),
                 "language": LANGUAGES[name[0]], "gender": "female" if name[1] == "f" else "male"}
                for name in KOKORO]
    if engine == "pocket":
        return [{"id": name, "name": name.replace("_", " ").title(),
                 "language": POCKET_LANGUAGES.get(name, ("english", "English"))[1],
                 "gender": "unspecified"} for name in POCKET]
    if engine == "kitten":
        return [{"id": name, "name": name, "language": "English (US)", "gender": gender}
                for name, gender in KITTEN.items()]
    return []


def validate_voice(engine: str, voice: str | None) -> str:
    if engine not in MODELS:
        raise ValueError(f"Unsupported local voice model: {engine}")
    voice = voice or MODELS[engine]["defaultVoice"]
    if voice not in {entry["id"] for entry in voices_for(engine)}:
        raise ValueError(f"Voice {voice!r} is not available for {MODELS[engine]['name']}.")
    return voice


def catalog(enabled_engines: set[str]) -> dict:
    models = []
    for engine, details in MODELS.items():
        installed = importlib.util.find_spec(details["package"]) is not None
        models.append({"id": engine, **{k: v for k, v in details.items() if k != "package"},
                       "installed": installed, "enabled": engine in enabled_engines,
                       "voices": [{**voice, "previewText": PREVIEWS[voice["language"].split(" (")[0]]} for voice in voices_for(engine)]})
    return {"schema": "clawdad.local-voices/1", "models": models,
            "previewText": "You can keep listening while you move between projects. Choose a voice that feels comfortable for longer responses."}
