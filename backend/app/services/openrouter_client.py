"""Bounded OpenRouter transport. Provider error bodies are never exposed."""
import json
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from fastapi import HTTPException
from config import config

MAX_RESPONSE_BYTES = 256_000
MAX_CATALOG_BYTES = 8_000_000


def report_error(status, kind, message):
    return HTTPException(status, detail={"type": kind, "message": message})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenRouterClient:
    def __init__(self, settings=config, opener=None, sleep=time.sleep):
        self.settings = settings
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    def configured(self):
        s = self.settings
        return bool(s.AI_REPORTS_ENABLED and s.OPENROUTER_API_KEY and s.OPENROUTER_MODEL)

    def require_configuration(self):
        if not self.configured():
            raise report_error(503, "AIUnavailable", "AI reports are disabled or server configuration is incomplete.")
        try:
            url = urlsplit(self.settings.OPENROUTER_BASE_URL)
            port = url.port
        except ValueError:
            raise report_error(503, "AIConfigurationError", "Use the HTTPS OpenRouter API base URL.") from None
        if (url.scheme != "https" or url.hostname != "openrouter.ai" or url.username or url.password
                or url.query or url.fragment or port not in (None, 443) or url.path.rstrip('/') != '/api/v1'):
            raise report_error(503, "AIConfigurationError", "Use the HTTPS OpenRouter API base URL.")
        if not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,150}', self.settings.OPENROUTER_MODEL):
            raise report_error(503, "AIConfigurationError", "OPENROUTER_MODEL must be a model catalog identifier, not a display name.")

    def _json_request(self, request, limit):
        for attempt in range(3):
            try:
                with self.opener.open(request, timeout=25) as response:
                    body = response.read(limit + 1)
                if len(body) > limit:
                    raise report_error(502, "AIResponseTooLarge", "Provider response exceeded the permitted size.")
                return json.loads(body)
            except HTTPError as exc:
                status = exc.code
                exc.close()
                if status in (408, 429, 500, 502, 503, 504) and attempt < 2:
                    self.sleep(0.25 * 2 ** attempt)
                    continue
                raise report_error(503 if status == 429 else 502, "AIProviderError", "OpenRouter could not complete this request.") from None
            except (TimeoutError, socket.timeout):
                if attempt < 2:
                    self.sleep(0.25 * 2 ** attempt)
                    continue
                raise report_error(504, "AIProviderTimeout", "OpenRouter request timed out.") from None
            except URLError:
                if attempt < 2:
                    self.sleep(0.25 * 2 ** attempt)
                    continue
                raise report_error(502, "AIProviderError", "OpenRouter could not be reached.") from None
            except (ValueError, UnicodeError):
                raise report_error(502, "AIInvalidOutput", "OpenRouter returned an invalid response.") from None

    def generate(self, snapshot, system_prompt, schema):
        self.require_configuration()
        base = self.settings.OPENROUTER_BASE_URL.rstrip('/')
        catalog = self._json_request(Request(base + '/models'), MAX_CATALOG_BYTES)
        models = catalog.get('data', []) if isinstance(catalog, dict) else []
        if not isinstance(models, list):
            raise report_error(502, "AIInvalidOutput", "OpenRouter returned an invalid model catalog.")
        model = next((m for m in models if isinstance(m, dict) and m.get('id') == self.settings.OPENROUTER_MODEL), None)
        if model is None:
            raise report_error(503, "AIConfigurationError", "Configured model is unavailable in the OpenRouter catalog.")
        payload = {"model": self.settings.OPENROUTER_MODEL, "max_tokens": 10000,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": json.dumps(snapshot, ensure_ascii=True)}]}
        if 'structured_outputs' in (model.get('supported_parameters') or []):
            payload['response_format'] = {"type": "json_schema", "json_schema": {
                "name": "freshwater_scientific_report", "strict": True, "schema": schema}}
            payload['provider'] = {"require_parameters": True}
        else:
            payload['messages'][0]['content'] += '\nReturn only strict JSON following this schema: ' + json.dumps(schema)
        request = Request(base + '/chat/completions', data=json.dumps(payload).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + self.settings.OPENROUTER_API_KEY,
                                   'Content-Type': 'application/json'})
        result = self._json_request(request, MAX_RESPONSE_BYTES)
        try:
            choice = result['choices'][0]
            content = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(content, str):
                raise ValueError
            if self.settings.OPENROUTER_API_KEY in content:
                raise ValueError
            return content
        except (KeyError, IndexError, TypeError, ValueError):
            raise report_error(502, "AIInvalidOutput", "OpenRouter returned incomplete or invalid report content.") from None
