import sys
import types
import unittest
from unittest import mock


class TestSarvamTranslate(unittest.TestCase):
    def test_translate_uses_sdk_when_available(self):
        fake_client = mock.Mock()
        fake_client.text.translate.return_value = {"translated_text": "હાય", "request_id": "r1"}

        class FakeSarvamAI:
            def __init__(self, api_subscription_key: str):
                self.api_subscription_key = api_subscription_key
                self.text = fake_client.text

        m = types.ModuleType("sarvamai")
        m.SarvamAI = FakeSarvamAI

        with mock.patch.dict(sys.modules, {"sarvamai": m}):
            from backend.utils import sarvam_client
            out = sarvam_client.translate_text_sarvam(
                text="Hi",
                source_language_code="auto",
                target_language_code="gu-IN",
                speaker_gender="Male",
                api_key="k",
            )

        self.assertTrue(out["success"])
        self.assertEqual(out["translated_text"], "હાય")
        fake_client.text.translate.assert_called_once()

    def test_translate_falls_back_to_http_when_sdk_missing(self):
        from backend.utils import sarvam_client

        class FakeResp:
            def __init__(self, payload):
                self._payload = payload
                self.text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        with mock.patch("backend.utils.sarvam_client._try_import_sdk", return_value=None):
            with mock.patch("backend.utils.sarvam_client.requests.post") as post:
                post.return_value = FakeResp({"translated_text": "નમસ્તે", "request_id": "r2"})
                out = sarvam_client.translate_text_sarvam(
                    text="Hello",
                    source_language_code="en-IN",
                    target_language_code="gu-IN",
                    api_key="k",
                )

        self.assertTrue(out["success"])
        self.assertEqual(out["translated_text"], "નમસ્તે")


if __name__ == "__main__":
    unittest.main()
