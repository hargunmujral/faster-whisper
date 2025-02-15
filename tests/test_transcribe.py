import os

from faster_whisper import BatchedInferencePipeline, WhisperModel, decode_audio


def test_supported_languages():
    model = WhisperModel("tiny.en")
    assert model.supported_languages == ["en"]


def test_transcribe(jfk_path):
    model = WhisperModel("tiny")
    segments, info = model.transcribe(jfk_path, word_timestamps=True)
    assert info.all_language_probs is not None

    assert info.language == "en"
    assert info.language_probability > 0.9
    assert info.duration == 11

    # Get top language info from all results, which should match the
    # already existing metadata
    top_lang, top_lang_score = info.all_language_probs[0]
    assert info.language == top_lang
    assert abs(info.language_probability - top_lang_score) < 1e-16

    segments = list(segments)

    assert len(segments) == 1

    segment = segments[0]

    assert segment.text == (
        " And so my fellow Americans ask not what your country can do for you, "
        "ask what you can do for your country."
    )

    assert segment.text == "".join(word.word for word in segment.words)
    assert segment.start == segment.words[0].start
    assert segment.end == segment.words[-1].end
    batched_model = BatchedInferencePipeline(model=model, use_vad_model=False)
    result = batched_model.transcribe(jfk_path, word_timestamps=True)
    segments = []
    for segment, info in result:
        assert info.language == "en"
        assert info.language_probability > 0.7
        segments.append(
            {"start": segment.start, "end": segment.end, "text": segment.text}
        )

    assert len(segments) == 1
    assert segment.text == (
        " And so my fellow Americans ask not what your country can do for you, "
        "ask what you can do for your country."
    )


def test_batched_transcribe(physcisworks_path):
    model = WhisperModel("tiny")
    batched_model = BatchedInferencePipeline(model=model)
    result = batched_model.transcribe(physcisworks_path, batch_size=16)
    segments = []
    for segment, info in result:
        assert info.language == "en"
        assert info.language_probability > 0.7
        segments.append(
            {"start": segment.start, "end": segment.end, "text": segment.text}
        )
    # number of near 30 sec segments
    assert len(segments) == 8

    result = batched_model.transcribe(
        physcisworks_path, batch_size=16, word_timestamps=True
    )
    segments = []
    for segment, info in result:
        assert segment.words is not None
        segments.append(
            {"start": segment.start, "end": segment.end, "text": segment.text}
        )
    # more number of segments owing to vad based alignment instead of 30 sec segments
    assert len(segments) > 8


def test_prefix_with_timestamps(jfk_path):
    model = WhisperModel("tiny")
    segments, _ = model.transcribe(jfk_path, prefix="And so my fellow Americans")
    segments = list(segments)

    assert len(segments) == 1

    segment = segments[0]

    assert segment.text == (
        " And so my fellow Americans ask not what your country can do for you, "
        "ask what you can do for your country."
    )

    assert segment.start == 0
    assert 10 < segment.end < 11


def test_vad(jfk_path):
    model = WhisperModel("tiny")
    segments, info = model.transcribe(
        jfk_path,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
    )
    segments = list(segments)

    assert len(segments) == 1
    segment = segments[0]

    assert segment.text == (
        " And so my fellow Americans ask not what your country can do for you, "
        "ask what you can do for your country."
    )

    assert 0 < segment.start < 1
    assert 10 < segment.end < 11

    assert info.vad_options.min_silence_duration_ms == 500
    assert info.vad_options.speech_pad_ms == 200


def test_stereo_diarization(data_dir):
    model = WhisperModel("tiny")

    audio_path = os.path.join(data_dir, "stereo_diarization.wav")
    left, right = decode_audio(audio_path, split_stereo=True)

    segments, _ = model.transcribe(left)
    transcription = "".join(segment.text for segment in segments).strip()
    assert transcription == (
        "He began a confused complaint against the wizard, "
        "who had vanished behind the curtain on the left."
    )

    segments, _ = model.transcribe(right)
    transcription = "".join(segment.text for segment in segments).strip()
    assert transcription == "The horizon seems extremely distant."


def test_multisegment_lang_id(physcisworks_path):
    model = WhisperModel("tiny")
    language_info = model.detect_language_multi_segment(physcisworks_path)
    assert language_info["language_code"] == "en"
    assert language_info["language_confidence"] > 0.8
