from collections.abc import Sequence

from openai import OpenAI

from app.core.config import settings


class AIUnavailableError(RuntimeError):
    pass


class AIService:
    def __init__(self) -> None:
        self.client = (
            OpenAI(api_key=settings.api_key, base_url=settings.normalized_base_url)
            if settings.api_key and settings.normalized_base_url
            else None
        )

    @property
    def chat_ready(self) -> bool:
        return self.client is not None and bool(settings.model_id)

    @property
    def embeddings_ready(self) -> bool:
        return self.client is not None and bool(settings.embedding_model_id)

    def answer(self, question: str, language: str, evidence: Sequence[str]) -> str:
        client = self.client
        model_id = settings.model_id
        if client is None or not model_id:
            raise AIUnavailableError("No chat model is configured.")
        if not evidence:
            raise ValueError("Grounded generation requires evidence.")
        language_name = "Hindi" if language == "hi" else "Marathi"
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Answer briefly in {language_name}. Use only the supplied "
                        "evidence. Do not add general knowledge or make unsupported "
                        "recommendations. If evidence does not answer the question, "
                        "say so and recommend contacting a local KVK or Kisan Call "
                        "Centre. Do not provide pesticide names, dosages, or chemical "
                        "application instructions."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\nApproved evidence:\n"
                        + "\n\n---\n\n".join(evidence)
                    ),
                },
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise AIUnavailableError("The configured model returned an empty answer.")
        return content.strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self.client
        model_id = settings.embedding_model_id
        if client is None or not model_id:
            raise AIUnavailableError("No embedding model is configured.")
        response = client.embeddings.create(model=model_id, input=texts)
        return [item.embedding for item in response.data]


ai_service = AIService()
