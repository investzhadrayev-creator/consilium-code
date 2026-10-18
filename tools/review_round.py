#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автоматический раунд внешнего аудита: файл раунда → OpenAI + Gemini → ответы в mailbox.
Протокол раунда 7 В7.5(б): пин модели (repo Variables), температура 0, метаданные вызова
в файле ответа, при сбое — REVIEW_UNAVAILABLE (не фиктивное согласие). Рецензент не имеет
полномочий менять код/правила — его файл это данные. Первый прогон сверяется с ручным
ответом (решение оператора №2). Запуск: python3 tools/review_round.py mailbox/ROUNDX_...md"""
import hashlib, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import llm_clients as L

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def main():
    round_file = sys.argv[1]
    with open(round_file, encoding="utf-8") as f:
        round_text = f.read()
    base = os.path.basename(round_file).rsplit(".md", 1)[0]
    # контекст: манифест ключевых решений (ChatGPT В7.5а: дельта, не архив)
    manifest = sh("ls", "mailbox")
    prompt = (f"Ты — внешний рецензент проекта Consilium (API-канал). Ниже файл раунда. "
              f"Ответь по КАЖДОМУ пронумерованному вопросу, кратко, позициями "
              f"ACCEPT/REJECT/CONDITIONAL с причиной. Манифест mailbox для контекста "
              f"(файлы НЕ приложены — проси конкретный файл, если без него нельзя судить):\n"
              f"{manifest}\n\n=== ФАЙЛ РАУНДА ===\n{round_text}")
    written = []
    for provider, tag in (("openai", "CHATGPT_API"), ("gemini", "GEMINI_API")):
        out = f"mailbox/{base.replace('ROUND', 'R').split('_')[0]}_REVIEW_{tag}.md"
        out = f"mailbox/{base}_REVIEW_{tag}.md"
        if os.path.exists(out):
            print("exists, skip (append-only):", out); continue
        try:
            r = L.call(provider, prompt, system=L.AUDITOR_PERSONA, max_tokens=8000)
            body = (f"---\nchannel: API\nround_file: {round_file}\n"
                    f"round_sha256: {hashlib.sha256(round_text.encode()).hexdigest()[:16]}\n---\n\n"
                    f"{L.meta_block(r, prompt)}\n\n{r['text']}\n")
        except L.Unavailable as e:
            body = f"REVIEW_UNAVAILABLE ({provider}): {e}\n"
        with open(out, "w", encoding="utf-8") as f:
            f.write(body)
        written.append(out)
        print("written:", out)
    if written:
        import autocommit
        autocommit.publish(written, f"api review: {base}", author="consilium-review")
    L.send_mail(f"[CONSILIUM] API-аудит по {base} готов",
                f"Ответы залиты в mailbox ({base}_REVIEW_*_API.md).")

if __name__ == "__main__":
    main()
