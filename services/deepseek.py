"""Запрос к нейросети DeepSeek (HTTPS API). Общий для пароля и адреса."""

import json
import urllib.request

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
TIMEOUT = 20


def ask(api_key, prompt, temperature, max_tokens):
    """Отправляет запрос и возвращает текст ответа без лишних пробелов и кавычек по краям.

    Ошибки сети и отказ сервиса приходят как OSError, неожиданный ответ - как ValueError/KeyError.
    """
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        answer = json.load(response)
    return answer["choices"][0]["message"]["content"].strip().strip("`'\" \n")
