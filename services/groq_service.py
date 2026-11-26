import logging

from groq import APIError, Groq

from config.settings import settings

logger = logging.getLogger(__name__)


class GroqServiceError(RuntimeError):
    pass


class GroqService:
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        api_key = settings.groq_api_key.get_secret_value()
        if not api_key:
            logger.error("Groq API key is not configured")
            raise GroqServiceError("GROQ_API_KEY must be configured.")

        client = Groq(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except APIError as exc:
            logger.exception("Groq chat completion failed")
            raise GroqServiceError("The language model request failed.") from exc

        if not response.choices:
            logger.error("Groq returned no completion choices")
            raise GroqServiceError("The language model returned no choices.")
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            logger.error("Groq returned an empty completion")
            raise GroqServiceError("The language model returned an empty answer.")
        return answer.strip()
