"""Roles y prefijos de conversaciones ampliadas, preservando offsets originales."""

import unittest

from backend.domain.transcript import caller_segments, dialogue_turns


class TranscriptTests(unittest.TestCase):
    def test_appending_labelled_turns_keeps_unlabelled_initial_report(self):
        initial = "  Hay fuego en Av. Corrientes 1540. 🏠 "
        text = initial + "\nOperador: ¿Hay gas?\nLlamante: No."
        segments = caller_segments(text)
        self.assertEqual(segments[0].text, initial + "\n")
        self.assertEqual(segments[0].start, 0)
        for segment in segments:
            self.assertEqual(text[segment.start:segment.start + len(segment.text)], segment.text)
        self.assertEqual(segments[1].text.strip(), "No.")

    def test_ciudadano_is_a_caller_without_rewriting_the_transcript(self):
        text = "Operador: ¿Dónde?\nCiudadano: En Corrientes 1540."
        turns = dialogue_turns(text)
        self.assertEqual([turn.role for turn in turns], ["operador", "llamante"])
        self.assertEqual(caller_segments(text)[0].text.strip(), "En Corrientes 1540.")
        self.assertEqual(text[turns[1].start:], turns[1].text)
