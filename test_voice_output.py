import unittest

from voice_output import prepare_speech_text


class PrepareSpeechTextTests(unittest.TestCase):
    def test_removes_markdown_without_destroying_link_labels(self):
        text = "## Result\nSee [the docs](https://example.com) and `settings`."
        self.assertEqual(
            prepare_speech_text(text),
            "Result See the docs and settings.",
        )

    def test_omits_fenced_code(self):
        text = "Answer.\n```python\nprint('secret')\n```\nDone."
        self.assertEqual(prepare_speech_text(text), "Answer. Done.")

    def test_caps_long_responses(self):
        prepared = prepare_speech_text("one two three four five", max_chars=12)
        self.assertTrue(prepared.endswith("response truncated"))
        self.assertLessEqual(len(prepared), 40)


if __name__ == "__main__":
    unittest.main()
