from typing import Dict, Any
from pathlib import Path

import pydash

from voice2json.utils import ppath

# -----------------------------------------------------------------------------


class Transcriber:
    def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
        pass


def get_transcriber(
    profile_dir: Path, profile: Dict[str, Any], debug=False
) -> Transcriber:
    from voice2json.speech.pocketsphinx import get_decoder, transcribe
    from voice2json.utils import maybe_convert_wav

    # Load settings
    acoustic_model = ppath(
        profile, profile_dir, "speech-to-text.acoustic-model", "acoustic_model"
    )
    dictionary = ppath(
        profile, profile_dir, "speech-to-text.dictionary", "dictionary.txt"
    )
    language_model = ppath(
        profile, profile_dir, "speech-to-text.language-model", "language_model.txt"
    )
    mllr_matrix = ppath(profile, profile_dir, "speech-to-text.mllr-matrix")

    # Load deocder
    decoder = get_decoder(
        acoustic_model, dictionary, language_model, mllr_matrix, debug=debug
    )

    class PocketsphinxTranscriber(Transcriber):
        def __init__(self, decoder):
            self.decoder = decoder

        def transcribe_wav(self, wav_data: bytes) -> Dict[str, Any]:
            audio_data = maybe_convert_wav(wav_data)
            return transcribe(self.decoder, audio_data)

    return PocketsphinxTranscriber(decoder)


# -----------------------------------------------------------------------------


class Recognizer:
    def recognize(self, text: str) -> Dict[str, Any]:
        pass


def get_recognizer(profile_dir: Path, profile: Dict[str, Any]) -> Recognizer:
    import pywrapfst as fst
    import networkx as nx
    from voice2json.intent.fsticuffs import (
        recognize,
        recognize_fuzzy,
        empty_intent,
        fst_to_graph,
    )

    # Load settings
    intent_fst_path = ppath(
        profile, profile_dir, "intent-recognition.intent-fst", "intent.fst"
    )
    stop_words_path = ppath(profile, profile_dir, "intent-recognition.stop-words")
    lower_case = pydash.get(profile, "intent-recognition.lower-case", False)
    fuzzy = pydash.get(profile, "intent-recognition.fuzzy", True)
    skip_unknown = pydash.get(profile, "intent-recognition.skip_unknown", True)

    # Load intent finite state transducer
    intent_fst = fst.Fst.read(str(intent_fst_path))

    # Load stop words (common words that can be safely ignored)
    stop_words: Set[str] = set()
    if stop_words_path is not None:
        stop_words.extend(w.strip() for w in stop_words_path.read_text().splitlines())

    # Ignore words outside of input symbol table
    known_tokens: Set[str] = set()
    if skip_unknown:
        in_symbols = intent_fst.input_symbols()
        for i in range(in_symbols.num_symbols()):
            key = in_symbols.get_nth_key(i)
            token = in_symbols.find(i).decode()

            # Exclude meta tokens and <eps>
            if not (token.startswith("__") or token.startswith("<")):
                known_tokens.add(token)

    if fuzzy:
        # Convert to graph for fuzzy searching
        intent_graph = fst_to_graph(intent_fst)

        class FuzzyRecognizer(Recognizer):
            def __init__(self, intent_graph, known_tokens, lower_case, stop_words):
                self.intent_graph = intent_graph
                self.known_tokens = known_tokens
                self.lower_case = lower_case
                self.stop_words = stop_words

            def recognize(self, text: str) -> Dict[str, Any]:
                if self.lower_case:
                    text = text.lower()

                return recognize_fuzzy(
                    self.intent_graph,
                    text,
                    known_tokens=self.known_tokens,
                    stop_words=self.stop_words,
                )

        return FuzzyRecognizer(intent_graph, known_tokens, lower_case, stop_words)
    else:

        class StrictRecognizer(Recognizer):
            def __init__(self, intent_fst, known_tokens, lower_case):
                self.intent_fst = intent_fst
                self.known_tokens = known_tokens
                self.lower_case = lower_case

            def recognize(self, text: str) -> Dict[str, Any]:
                if self.lower_case:
                    text = text.lower()

                return recognize(self.intent_fst, text, self.known_tokens)

        return StrictRecognizer(intent_fst, known_tokens, lower_case)


# -----------------------------------------------------------------------------
