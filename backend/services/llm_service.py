import json

from config import GOOGLE_API_KEY


class LLMService:
    def __init__(self, model_name: str = "gemini-3.1-flash-lite"):
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY bulunamadi.")

        from google import genai

        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_name = model_name

    def generate_json(self, prompt: str, response_schema: dict) -> dict:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.1,
            ),
        )

        text = response.text

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM JSON parse edilemedi. Ham cevap:\n{text}") from exc
