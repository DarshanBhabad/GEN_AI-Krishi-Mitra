from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionContext:
    intent: str
    crop: str | None
    season: str | None
    location: str | None
    commodity: str | None
    market: str | None
    needs_follow_up: str | None
    unsafe_chemical: bool


INTENT_TERMS = {
    "weather": ("weather", "forecast", "rain", "मौसम", "बारिश", "हवामान", "पाऊस"),
    "mandi": ("mandi", "price", "prices", "भाव", "किंमत", "बाजारभाव", "मंडी", "दर"),
    "scheme": ("scheme", "yojana", "योजना", "अनुदान", "शासकीय", "सरकारी"),
    "pest_disease": ("pest", "disease", "कीट", "रोग", "कीड", "बुरशी", "फंगल"),
    "crop_advice": ("crop", "फसल", "पीक", "सोयाबीन", "कापूस", "कपास", "wheat", "गहू"),
}
CHEMICAL_TERMS = (
    "pesticide", "insecticide", "fungicide", "herbicide", "कीटनाशक",
    "फवारणी", "फवारणीचे औषध", "दवा", "डोस", "dose", "dosage", "मात्रा",
    "chemical spray", "रासायनिक",
)
CROPS = {
    "soybean": ("soybean", "सोयाबीन"),
    "cotton": ("cotton", "कपास", "कापूस"),
    "wheat": ("wheat", "गेहूं", "गहू"),
    "rice": ("rice", "धान", "तांदूळ", "भात"),
    "onion": ("onion", "प्याज", "कांदा"),
    "tomato": ("tomato", "टमाटर", "टोमॅटो"),
}
SEASONS = {
    "kharif": ("kharif", "खरीफ", "खरीप", "monsoon"),
    "rabi": ("rabi", "रबी", "रब्बी"),
    "zaid": ("zaid", "ज़ायद", "जायद"),
}


def classify_question(text: str, selected_location: str | None = None) -> QuestionContext:
    normalized = text.casefold()
    intent = "other"
    for candidate in ("weather", "mandi", "scheme", "pest_disease", "crop_advice"):
        if any(term in normalized for term in INTENT_TERMS[candidate]):
            intent = candidate
            break
    crop = next(
        (
            crop_name
            for crop_name, terms in CROPS.items()
            if any(term in normalized for term in terms)
        ),
        None,
    )
    season = next(
        (
            season_name
            for season_name, terms in SEASONS.items()
            if any(term in normalized for term in terms)
        ),
        None,
    )
    location = selected_location.strip() if selected_location and selected_location.strip() else None
    unsafe = any(term in normalized for term in CHEMICAL_TERMS)

    follow_up = None
    if intent == "weather" and not location:
        follow_up = "location"
    elif intent == "mandi" and not crop:
        follow_up = "commodity"
    elif intent in {"crop_advice", "pest_disease"} and not crop:
        follow_up = "crop"

    return QuestionContext(
        intent=intent,
        crop=crop,
        season=season,
        location=location,
        commodity=crop,
        market=location,
        needs_follow_up=follow_up,
        unsafe_chemical=unsafe,
    )
