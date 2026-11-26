from dataclasses import dataclass

from app.services.understanding import QuestionContext


KVK_REFERRAL = {
    "hi": "कृपया अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) या किसान कॉल सेंटर से सलाह लें।",
    "mr": "कृपया जवळच्या कृषी विज्ञान केंद्र (KVK) किंवा किसान कॉल सेंटरशी संपर्क साधा.",
}


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def decide(
    context: QuestionContext,
    retrieved: list[dict],
    min_coverage: float = 0.22,
) -> GateDecision:
    if context.unsafe_chemical:
        return GateDecision(False, "chemical_advice_requires_expert")
    if context.needs_follow_up:
        return GateDecision(False, "missing_required_detail")
    if context.intent in {"weather", "mandi"}:
        return GateDecision(False, "live_data_not_available")
    if context.intent not in {"crop_advice", "pest_disease", "scheme"}:
        return GateDecision(False, "outside_supported_scope")
    relevant = [
        item for item in retrieved
        if item.get("approved") and item.get("coverage", 0.0) >= min_coverage
    ]
    if not relevant:
        return GateDecision(False, "insufficient_approved_evidence")
    return GateDecision(True, "approved_evidence_found")


def refusal_text(reason: str, language: str) -> str:
    if reason == "missing_required_detail":
        return "कृपया आवश्यक जानकारी दें, फिर मैं खोजने की कोशिश करूँगा।" if language == "hi" else "कृपया आवश्यक माहिती द्या; मग मी शोधण्याचा प्रयत्न करेन."
    if reason == "chemical_advice_requires_expert":
        lead = "कीटनाशक या रासायनिक दवा की मात्रा बताना सुरक्षित नहीं है।" if language == "hi" else "कीटकनाशक किंवा रासायनिक औषधाचा डोस सांगणे सुरक्षित नाही."
        return f"{lead} {KVK_REFERRAL[language]}"
    if reason == "live_data_not_available":
        return "इस प्रश्न के लिए ताज़ा लाइव जानकारी चाहिए, जो अभी उपलब्ध नहीं है। कृपया आधिकारिक मंडी या मौसम सेवा देखें।" if language == "hi" else "या प्रश्नासाठी ताजी माहिती आवश्यक आहे, जी सध्या उपलब्ध नाही. कृपया अधिकृत बाजार किंवा हवामान सेवा तपासा."
    return (
        "मेरे पास इस प्रश्न का भरोसेमंद, स्वीकृत स्रोत उपलब्ध नहीं है। "
        + KVK_REFERRAL[language]
        if language == "hi"
        else "या प्रश्नासाठी माझ्याकडे विश्वासार्ह, मंजूर स्रोत उपलब्ध नाही. "
        + KVK_REFERRAL[language]
    )
