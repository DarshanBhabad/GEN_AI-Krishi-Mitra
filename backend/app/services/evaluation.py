import json
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.retrieval import retrieve
from app.services.safety import decide
from app.services.understanding import classify_question


DATASET = Path(__file__).resolve().parents[3] / "data" / "evaluation" / "cases.json"


def run_evaluation(db: Session) -> dict:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    database_probe = db.execute(select(1)).scalar_one() == 1
    started = time.perf_counter()
    recall_hits = 0
    answerable = 0
    refusal_correct = 0
    refusal_cases = 0
    for case in cases:
        question = case["question"]
        context = classify_question(question, case.get("location"))
        results = retrieve(db, question, limit=5)
        expected = case["expected"]
        if expected == "answerable":
            answerable += 1
            if any(
                item["title"] == case.get("relevant_document_title")
                for item in results
            ):
                recall_hits += 1
        else:
            refusal_cases += 1
            decision = decide(context, results)
            if not decision.allowed:
                refusal_correct += 1
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "cases": len(cases),
        "retrieval_recall_at_5": round(recall_hits / answerable, 3) if answerable else None,
        "correct_refusal_rate": round(refusal_correct / refusal_cases, 3) if refusal_cases else None,
        "answerable_cases": answerable,
        "refusal_cases": refusal_cases,
        "latency_ms": elapsed_ms,
        "answer_faithfulness": None,
        "speech_recognition_accuracy": None,
        "api_reliability": {"database_probe": "passed" if database_probe else "failed"},
        "unmeasured_metrics_note": (
            "Faithfulness needs human answer labels and speech accuracy needs reference audio/transcripts. "
            "The API reliability smoke result is a database probe, not an uptime or load test."
        ),
        "note": "Local rule-and-retrieval evaluation only; not a farmer study or an LLM faithfulness score.",
    }
