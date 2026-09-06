import unittest
from unittest.mock import patch
from doc_reader.local_voices import catalog, voices_for, validate_voice, POCKET
from doc_reader.tts_service import EngineRegistry


class LocalVoiceTests(unittest.TestCase):
    def test_catalog_contains_every_published_voice_without_loading_models(self):
        data = catalog({"kokoro", "pocket", "kitten"})
        self.assertEqual([len(m["voices"]) for m in data["models"]], [54, 26, 8])
        for model in data["models"]:
            ids = [v["id"] for v in model["voices"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertIn(model["defaultVoice"], ids)
            self.assertTrue(all(v["previewText"] for v in model["voices"]))

    def test_voice_ids_are_model_specific_and_cannot_load_arbitrary_files(self):
        for voice in ("Bella", "https://example.com/voice.wav", "/private/file.wav"):
            with self.assertRaises(ValueError): validate_voice("pocket", voice)
        self.assertEqual(validate_voice("kitten", None), "Bella")

    def test_local_dispatch_passes_exact_selected_voice_and_speed(self):
        registry = EngineRegistry(enabled_engines={"pocket", "kitten"}, device="cpu")
        with patch.object(registry, "_synthesize_local", return_value="audio") as generate:
            self.assertEqual(registry.synthesize(engine="kitten", text="Hello.", voice="Jasper", speed=1.25), "audio")
            generate.assert_called_once_with("kitten", "Hello.", "Jasper", speed=1.25)
        with self.assertRaises(ValueError): registry.synthesize(engine="kokoro", text="Hello.")

    def test_installed_pocket_package_has_no_omitted_predefined_voices(self):
        try:
            from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES
        except ImportError:
            self.skipTest("Pocket package is not installed in this test environment")
        self.assertEqual(set(POCKET), set(_ORIGINS_OF_PREDEFINED_VOICES))


if __name__ == "__main__": unittest.main()
