#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Калибровка аудитора (решение оператора 2026-10-19: Gemini 3.1 -> 4 Argon только после калибровки).
Исполняется, только если есть заявка mailbox/CALIBRATION_REQUEST_*.md БЕЗ ответа.
Заявка — front matter:
    ---
    date: 2026-10-18            # дата пакета (как у daily_audit)
    candidate_model: <id модели-кандидата Gemini>
    ---
Один и тот же пакет (daily_audit.build_packet за date, проход 1) уходит модели из GEMINI_MODEL
и кандидату; оба ответа + meta_block -> journal/calibration/<date>_<model>.md через autocommit.
Ответ существует = файл есть: готовые файлы не переписываются (append-only), идемпотентно.
Недоступная модель / битая заявка — именованный отказ, exit 1 + Telegram; файл-заглушка НЕ пишется
(иначе заявка навсегда считалась бы отвеченной). Переменные репозитория не меняются."""
import datetime as dt, glob, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_clients as L
import daily_audit as D

REQ_GLOB = "mailbox/CALIBRATION_REQUEST_*.md"
OUT_DIR = "journal/calibration"

class BadRequest(Exception):
    pass

def parse_request(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        raise BadRequest(f"{path}: нет front matter (---)")
    kv = {}
    for ln in m.group(1).splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            kv[k.strip()] = v.split("#", 1)[0].strip()
    try:
        day = dt.date.fromisoformat(kv.get("date", ""))
    except ValueError:
        raise BadRequest(f"{path}: date отсутствует или не ISO ({kv.get('date')!r})")
    cand = kv.get("candidate_model", "")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", cand):
        raise BadRequest(f"{path}: candidate_model отсутствует или недопустим ({cand!r})")
    return day, cand

def out_path(day, model):
    return f"{OUT_DIR}/{day}_{re.sub(r'[^A-Za-z0-9._-]+', '-', model)}.md"

def pending(root="."):
    """-> [(request_path, day, candidate, baseline_model, missing_models)] только без полного ответа."""
    base_model = os.environ.get("GEMINI_MODEL") or ""
    res = []
    for req in sorted(glob.glob(os.path.join(root, REQ_GLOB))):
        day, cand = parse_request(req)
        if not base_model:
            raise BadRequest("GEMINI_MODEL не задана — базовая модель неизвестна, калибровать не с чем")
        missing = [m for m in (base_model, cand) if not os.path.exists(os.path.join(root, out_path(day, m)))]
        if missing:
            res.append((req, day, cand, base_model, missing))
    return res

def run_one(req, day, cand, base_model, missing):
    g = D.gather(end=dt.datetime.combine(day, dt.time(16, 0), tzinfo=dt.timezone.utc))
    packet = D.build_packet(day, g)
    prompt = packet + D.PASS1_TASK
    written = []
    os.makedirs(OUT_DIR, exist_ok=True)
    for model in missing:
        r = L.call_gemini(prompt, system=L.AUDITOR_PERSONA, model=model)  # Unavailable -> наверх
        role = "кандидат" if model == cand and model != base_model else "базовая (GEMINI_MODEL)"
        path = out_path(day, model)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# CALIBRATION {day} — {role}: {model}\n\nзаявка: {req}\n\n"
                    f"{L.meta_block(r, prompt)}\n\n## Ответ (проход 1)\n\n{r['text']}\n")
        written.append(path)
    return written

def main():
    try:
        todo = pending()
    except BadRequest as e:
        print("CALIBRATION REFUSED:", e)
        L.notify(f"Калибровка: заявка отклонена — {e}")
        sys.exit(1)
    if not todo:
        print("calibrate: заявок без ответа нет — нечего исполнять")
        return
    import autocommit
    failed = []
    for item in todo:
        try:
            paths = run_one(*item)
        except L.Unavailable as e:
            print(f"CALIBRATION UNAVAILABLE {item[0]}: {e}")
            failed.append(f"{item[0]}: {e}")
            continue
        if not autocommit.publish(paths, f"calibration {item[1]} {item[2]}", author="consilium-calibrate"):
            failed.append(f"{item[0]}: публикация не прошла проверку")
        else:
            print("calibration published:", paths)
    if failed:
        L.notify("Калибровка не завершена: " + "; ".join(f[:150] for f in failed))
        sys.exit(1)

if __name__ == "__main__":
    main()
