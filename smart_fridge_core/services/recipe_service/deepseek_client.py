import json
import re
from typing import Any, Dict

import httpx

from core.config import settings


class DeepSeekClient:
    """
    Оставляем старое имя класса, чтобы не менять остальные импорты.
    Но фактически это клиент OpenRouter.
    """

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        self.model = settings.OPENROUTER_MODEL
        self.timeout = settings.OPENROUTER_TIMEOUT_SECONDS
        self.site_url = settings.OPENROUTER_SITE_URL
        self.app_name = settings.OPENROUTER_APP_NAME

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _extract_json(self, raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError(f"OpenRouter model did not return valid JSON. Raw: {raw_text[:1500]}")

    def create_recipe_plan(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "temperature": 0.4,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)

            if response.status_code >= 400:
                raise RuntimeError(
                    f"OpenRouter API error {response.status_code}: {response.text}"
                )

            data = response.json()

        try:
            content = data["choices"][0]["message"].get("content", "")
        except Exception:
            raise RuntimeError(f"Unexpected OpenRouter response: {data}")

        parsed = self._extract_json(content)
        parsed["_meta"] = {
            "provider": "openrouter",
            "model": data.get("model", self.model),
        }
        return parsed
