"""Server-only Gemini Interactions transport. Never surface provider error bodies."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.application.chat_prompt import SYSTEM_PROMPT

MODEL = 'gemini-4-hydrogen'
ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/interactions'


class GeminiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class GeminiClient:
    def generate(self, payload: dict) -> str:
        key = os.environ.get('GEMINI_API_KEY', '').strip()
        if not key:
            raise GeminiError(503, 'El asistente no tiene credenciales configuradas.')
        body = {
            'model': MODEL, 'system_instruction': SYSTEM_PROMPT,
            # History is quoted background, not a signed continuation. Each call
            # receives a fresh selection and cannot retain a previous canton's data.
            'input': json.dumps(payload, ensure_ascii=False, allow_nan=False),
            'generation_config': {'thinking_level': 'low', 'max_output_tokens': 2400},
            'store': False,
        }
        request = Request(ENDPOINT, data=json.dumps(body).encode(), method='POST', headers={
            'x-goog-api-key': key, 'Content-Type': 'application/json',
            'Api-Revision': '2026-05-20',
        })
        try:
            with urlopen(request, timeout=60) as response:
                result = json.loads(response.read(2_000_000))
        except HTTPError as error:
            status = 429 if error.code == 429 else 502
            raise GeminiError(status, 'Gemini no pudo atender la consulta. Intenta nuevamente.') from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise GeminiError(502, 'No se pudo obtener una respuesta de Gemini.') from None
        if not isinstance(result, dict) or result.get('status') != 'completed':
            raise GeminiError(502, 'Gemini no completó la respuesta.')
        answer = '\n'.join(
            block['text'] for step in result.get('steps', [])
            if step.get('type') == 'model_output'
            for block in step.get('content', [])
            if block.get('type') == 'text' and isinstance(block.get('text'), str)
        ).strip()
        if not answer:
            raise GeminiError(502, 'Gemini no devolvió una respuesta de texto.')
        # Defense in depth: never return the configured credential, even if echoed.
        return answer.replace(key, '[credencial omitida]')
