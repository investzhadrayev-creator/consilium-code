#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Клиенты OpenAI/Gemini для ролей аудитора и рецензента.
Протокол раунда 7: пин модели через repo Variables (OPENAI_MODEL/GEMINI_MODEL),
температура 0, повторы с backoff, при недоступности — исключение Unavailable
(вызывающий пишет REVIEW_UNAVAILABLE, никакого фиктивного согласия)."""
import io, json, os, re, time, hashlib, urllib.request, urllib.error

class Unavailable(Exception):
    pass

def _post(url, headers, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def _retry(fn, tries=3):
    last = None
    for i in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            last = f"HTTP {e.code}: {body}"
            if e.code in (400, 401, 403, 404):  # не лечится повтором
                raise Unavailable(last)
        except Exception as e:  # сеть/таймаут
            last = repr(e)
        time.sleep(5 * (2 ** i))
    raise Unavailable(last or "unknown")

def call_openai(prompt, system=None, max_tokens=6000):
    key = os.environ.get("OPENAI_API_KEY") or ""
    model = os.environ.get("OPENAI_MODEL") or ""
    if not key or not model:
        raise Unavailable("OPENAI_API_KEY/OPENAI_MODEL not set (run list_models workflow, set repo variable)")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    def once():
        body = {"model": model, "messages": msgs,
                "max_completion_tokens": max_tokens, "temperature": 0}
        try:
            return _post("https://api.openai.com/v1/chat/completions",
                         {"Authorization": f"Bearer {key}"}, body)
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")
            # reasoning-модели не принимают temperature / старые — max_completion_tokens
            if e.code == 400:
                body2 = {"model": model, "messages": msgs}
                if "temperature" in txt:
                    body2["max_completion_tokens"] = max_tokens
                else:
                    body2["temperature"] = 0
                    body2["max_tokens"] = max_tokens
                return _post("https://api.openai.com/v1/chat/completions",
                             {"Authorization": f"Bearer {key}"}, body2)
            raise
    j = _retry(once)
    txt = j["choices"][0]["message"]["content"]
    return {"text": txt, "model": j.get("model", model),
            "usage": j.get("usage", {}), "provider": "openai"}

def call_gemini(prompt, system=None, max_tokens=6000, model=None):
    key = os.environ.get("GEMINI_API_KEY") or ""
    model = model or os.environ.get("GEMINI_MODEL") or ""
    if not key or not model:
        raise Unavailable("GEMINI_API_KEY/GEMINI_MODEL not set (run list_models workflow, set repo variable)")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    temp = "0"

    def once():
        nonlocal temp
        try:
            return _post(url, {}, body)
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")
            # модель не принимает temperature -> один повтор без неё, факт фиксируется в meta_block
            if e.code == 400 and "temperature" in txt.lower() and "temperature" in body["generationConfig"]:
                del body["generationConfig"]["temperature"]
                temp = "not_applied"
                return _post(url, {}, body)
            raise urllib.error.HTTPError(e.url, e.code, e.msg, e.hdrs, io.BytesIO(txt.encode()))
    j = _retry(once)
    try:
        txt = j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise Unavailable(f"gemini: unexpected response shape: {str(j)[:300]}")
    return {"text": txt, "model": model, "temp": temp,
            "usage": j.get("usageMetadata", {}), "provider": "gemini"}

def call(provider, prompt, system=None, max_tokens=6000):
    f = call_openai if provider == "openai" else call_gemini
    return f(prompt, system=system, max_tokens=max_tokens)

def meta_block(resp, input_text):
    h = hashlib.sha256(input_text.encode()).hexdigest()[:16]
    return (f"<!-- provider={resp['provider']} model={resp['model']} "
            f"input_sha256_16={h} usage={json.dumps(resp['usage'])} "
            f"temp={resp.get('temp', '0')} ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} -->")

AUDITOR_PERSONA = ("Ты — Senior Equity Research Analyst с 20-летним опытом в value-хедж-фонде "
                   "(школа Грэма-Додда) и внешний аудитор проекта Consilium. Стиль: скептический, "
                   "доказательный, краткий. Несогласие ценнее вежливости. Числа — только из "
                   "переданных артефактов, никогда из памяти.")

def send_mail(subject, body_text):
    """Письмо оператору через Gmail SMTP. Секреты: GMAIL_ADDRESS, GMAIL_APP_PASSWORD."""
    import smtplib
    from email.mime.text import MIMEText
    addr = os.environ.get("GMAIL_ADDRESS") or ""
    pwd = os.environ.get("GMAIL_APP_PASSWORD") or ""
    to = os.environ.get("OPERATOR_EMAIL") or addr
    if not addr or not pwd:
        print("WARN: mail secrets not set; skip email:", subject)
        return False
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = addr
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(addr, pwd)
        s.sendmail(addr, [to], msg.as_string())
    return True

def _scrub(text, token):
    """Токен никогда не попадает в лог: ни сам, ни в составе URL бота."""
    text = str(text)
    if token:
        text = text.replace(token, "***")
    return re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***", text)

# Уровни важности Telegram (issue #92). Оператор одобряет с телефона: важное не должно тонуть
# среди ежедневных строк. ACTION/ALARM — жирный заголовок + звук; INFO — без звука.
ACTION = "ACTION"   # нужно решение оператора (PR на одобрение, отказ моста в merge)
ALARM = "ALARM"     # реальный сбой / подтверждённое нарушение правил
INFO = "INFO"       # ежедневная строка, чистый аудит, прочие сведения
LEVEL_HEADERS = {ACTION: "🔴 НУЖНО ВАШЕ РЕШЕНИЕ", ALARM: "🟠 ТРЕВОГА"}
TG_LIMIT = 4000
TRUNC_MARK = "\n…(усечено)"

def _fit_html(msg, head):
    """Экранированный текст, влезающий в лимит Telegram. Режем СЫРОЙ текст до экранирования:
    обрезка уже экранированной строки может разорвать сущность (&amp;) и Telegram отклонит всё."""
    import html
    budget = TG_LIMIT - len(head) - 1
    esc = html.escape(msg, quote=False)
    if len(esc) <= budget:
        return esc
    n = len(msg)
    while n > 0:
        esc = html.escape(msg[:n], quote=False) + TRUNC_MARK
        if len(esc) <= budget:
            return esc
        n = n - max(1, (len(esc) - budget) // 6)
    return TRUNC_MARK.strip()

def notify(text, level=INFO):
    """Telegram-уведомление оператору. Секреты: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
    level: ACTION | ALARM (HTML, жирный заголовок, со звуком) | INFO (без звука, по умолчанию).
    Неизвестный уровень — ValueError (не молчаливая подстановка INFO: missing != default).
    Нет секретов -> WARN и False (не падает). Ошибка отправки -> WARN без токена и False.
    True только если Telegram ответил ok."""
    if level not in (ACTION, ALARM, INFO):
        raise ValueError(f"notify: неизвестный уровень {level!r}; допустимо ACTION|ALARM|INFO")
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    chat = os.environ.get("TELEGRAM_CHAT_ID") or ""
    if not token or not chat:
        print("WARN: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set; notify skipped")
        return False
    msg = text if text.startswith("[Консилиум] ") else "[Консилиум] " + text
    if level == INFO:
        payload = {"chat_id": chat, "text": msg[:TG_LIMIT], "disable_notification": True}
    else:
        head = f"<b>{LEVEL_HEADERS[level]}</b>"
        payload = {"chat_id": chat, "text": head + "\n" + _fit_html(msg, head),
                   "parse_mode": "HTML", "disable_notification": False}
    try:
        j = _post(f"https://api.telegram.org/bot{token}/sendMessage", {}, payload, timeout=30)
        if not j.get("ok"):
            print("WARN: telegram not ok:", _scrub(str(j)[:200], token))
            return False
        return True
    except Exception as e:
        print("WARN: telegram notify failed:", _scrub(repr(e), token))
        return False
