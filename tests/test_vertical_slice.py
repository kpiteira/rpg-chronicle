import json

from rpg_chronicle.pipeline import run_fixture_pipeline
from rpg_chronicle.providers import FixtureTranscriptProvider


def test_fixture_vertical_slice_is_review_ready_and_evidence_backed(tmp_path):
    fixture = (
        __import__("pathlib").Path(__file__).parents[1]
        / "benchmarks"
        / "fixtures"
        / "r0_synthetic_session.json"
    )

    session = run_fixture_pipeline(fixture, tmp_path, FixtureTranscriptProvider())

    assert session.status == "review_ready"
    assert len(session.turns) == 4
    assert len(session.scenes) == 2
    assert session.review_questions[0].evidence.turn_ids == ["turn-003", "turn-004"]

    package_path = tmp_path / session.session_id / "review-package.json"
    package = json.loads(package_path.read_text())
    assert package["summary"].startswith("The party met courier Mira Vey")
    assert package["needs_attention"][0]["actions"] == [
        "accept",
        "correct",
        "defer",
        "irrelevant",
    ]


def test_fixture_vertical_slice_resumes_without_retranscribing(tmp_path):
    class OneShotProvider(FixtureTranscriptProvider):
        calls = 0

        def transcribe(self, source):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("completed transcription stage was repeated")
            return super().transcribe(source)

    fixture = (
        __import__("pathlib").Path(__file__).parents[1]
        / "benchmarks"
        / "fixtures"
        / "r0_synthetic_session.json"
    )
    provider = OneShotProvider()

    run_fixture_pipeline(fixture, tmp_path, provider)
    resumed = run_fixture_pipeline(fixture, tmp_path, provider)

    assert resumed.status == "review_ready"
    assert provider.calls == 1
