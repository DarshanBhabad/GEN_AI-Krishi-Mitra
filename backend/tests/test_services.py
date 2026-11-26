from app.services.documents import chunk_text
from app.services.safety import decide
from app.services.understanding import classify_question


def test_long_document_chunks_stay_under_limit_with_overlap():
    text = "Paragraph one. " * 120
    chunks = chunk_text(text, max_chars=500)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_unapproved_retrieval_result_cannot_pass_safety_gate():
    context = classify_question("What is the crop advice for soybean?")
    retrieved = [{"approved": False, "coverage": 1.0}]

    assert not decide(context, retrieved).allowed


def test_other_intent_is_outside_supported_agricultural_scope():
    context = classify_question("Tell me a joke.")

    decision = decide(context, [])

    assert not decision.allowed
    assert decision.reason == "outside_supported_scope"
