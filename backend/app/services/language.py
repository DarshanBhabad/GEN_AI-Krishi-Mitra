import re


MARATHI_MARKERS = ("आहे", "नाही", "काय", "माझ्या", "करावे", "साठी", "मध्ये", "पिकाला")


def detect_language(text: str, preferred: str = "hi") -> str:
    devanagari = len(re.findall(r"[\u0900-\u097f]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if devanagari == 0:
        return preferred
    if devanagari < latin:
        return preferred
    if any(marker in text for marker in MARATHI_MARKERS):
        return "mr"
    return preferred if preferred in {"hi", "mr"} else "hi"


def language_label(code: str) -> str:
    return "Hindi" if code == "hi" else "Marathi"
