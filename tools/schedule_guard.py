#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Надёжность расписаний (issue #70): идемпотентность резервных слотов + сторож пропусков.

GitHub исполняет schedule «по мере возможности» и пропускает запуски под нагрузкой, поэтому у
каждого расписания несколько слотов. Каждый слот перед работой спрашивает ЭТОТ модуль, опубликован
ли результат периода на origin/main; если да — выход 0 со строкой «уже опубликовано», без PR,
без красного, без Telegram.

Сторож (watch) читает расписание из самих .github/workflows/*.yml (что ожидалось за 24 ч — из
реальных cron, а не из памяти), сверяет с `gh run list` и с main (опубликован ли результат
последнего закрытого периода). Статусы именованные: PUBLISHED / MISSING / NOT_REQUIRED / UNKNOWN.
UNKNOWN (источник недоступен) — не «зелёно» и не «пропуск»: называется причина.

CLI:
  python3 tools/schedule_guard.py check <workflow>   # exit 0 всегда; пишет флаги в $GITHUB_ENV
  python3 tools/schedule_guard.py watch [--only <workflow>] [--notify]   # exit 1 при MISSING/UNKNOWN
"""
import csv, datetime as dt, io, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_clients as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_DIR = os.path.join(ROOT, ".github", "workflows")
MAIN = "origin/main"
GRACE = dt.timedelta(minutes=60)            # прогон последнего слота успевает опубликоваться
NOTIFY_WINDOW = dt.timedelta(hours=26)      # о пропуске периода сообщаем один раз, не неделю подряд
RUN_LIMIT = 200
PUBLISHED, MISSING, NOT_REQUIRED, UNKNOWN = "PUBLISHED", "MISSING", "NOT_REQUIRED", "UNKNOWN"
BRIDGE_MAX_AGE = dt.timedelta(hours=6)      # старше — мост считается незапущенным (issue #94)
BRIDGE_URL = "https://github.com/investzhadrayev-creator/consilium-code/actions/workflows/mail_bridge.yml"
FLOOR1_RE = re.compile(r"^FLOOR1_(\d{4}-\d{2}-\d{2})\.md$")

SPECS = {
    # period: None -> у workflow нет «результата периода» (дедуп внутри скрипта / по заявке)
    "mail-bridge": {"file": "mail_bridge.yml", "period": None},
    "calibrate-auditor": {"file": "calibrate-auditor.yml", "period": None},
    "daily-report": {"file": "daily_report.yml", "period": "day", "activity": True,
                     "paths": lambda p: [f"journal/digests/DAILY_{p}.md"]},
    "daily-audit": {"file": "daily_audit.yml", "period": "day", "activity": True,
                    "paths": lambda p: [f"journal/audits/DAILY_AUDIT_{p}.md"]},
    "panel-weekly": {"file": "panel_weekly.yml", "period": "week", "panel": True},
    # письмо не оставляет файла в репозитории: результат периода = успешный прогон
    "weekly-digest": {"file": "weekly_digest.yml", "period": "week", "by_runs": True},
    "monthly-architect-audit": {"file": "monthly_audit.yml", "period": "month",
                                "paths": lambda p: [f"journal/audits/MONTHLY_ARCHITECT_AUDIT_{p:%Y-%m}.md"]},
}


class ScheduleError(Exception):
    pass


def sh(*cmd):
    """-> (returncode, stdout, stderr); без исключений, отказ виден вызывающему."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:                    # нет git/gh в PATH — тоже именованный отказ
        return 127, "", f"{cmd[0]}: {e}"
    return r.returncode, r.stdout, r.stderr


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


# ---------------------------------------------------------------- cron ------------------------
def _field(spec, lo, hi):
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = int(part)
            b = hi if step != 1 else a
        if a < lo or b > hi or a > b or step < 1:
            raise ValueError(f"поле cron вне диапазона: {spec!r}")
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr):
    f = expr.split()
    if len(f) != 5:
        raise ScheduleError(f"cron {expr!r}: нужно 5 полей")
    try:
        dow = {d % 7 for d in _field(f[4], 0, 7)}
        return {"min": _field(f[0], 0, 59), "hour": _field(f[1], 0, 23),
                "dom": _field(f[2], 1, 31), "mon": _field(f[3], 1, 12), "dow": dow,
                "dom_star": f[2] == "*", "dow_star": f[4] == "*"}
    except ValueError as e:
        raise ScheduleError(f"cron {expr!r}: {e}")


def _day_matches(c, d):
    dom_ok = d.day in c["dom"]
    dow_ok = (d.weekday() + 1) % 7 in c["dow"]
    if d.month not in c["mon"]:
        return False
    if not c["dom_star"] and not c["dow_star"]:      # POSIX: оба заданы -> ИЛИ
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def expand_cron(expr, start, end):
    """Все срабатывания cron (UTC) в [start, end)."""
    c = parse_cron(expr)
    out = []
    d = start.date()
    while d <= end.date():
        if _day_matches(c, d):
            for h in sorted(c["hour"]):
                for m in sorted(c["min"]):
                    t = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc)
                    if start <= t < end:
                        out.append(t)
        d += dt.timedelta(days=1)
    return out


def workflow_crons(name):
    path = os.path.join(WF_DIR, SPECS[name]["file"])
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise ScheduleError(f"{name}: не прочитан {path}: {e}")
    crons = re.findall(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", text, re.M)
    if not crons:
        raise ScheduleError(f"{name}: в {SPECS[name]['file']} нет ни одного cron")
    return crons


def slots(name, start, end):
    out = []
    for expr in workflow_crons(name):
        out += expand_cron(expr, start, end)
    return sorted(set(out))


# ---------------------------------------------------------------- periods ---------------------
def period_start(kind, d):
    if kind == "day":
        return d
    if kind == "week":                       # ISO-неделя пн..вс: суббота и воскресенье — одна неделя
        return d - dt.timedelta(days=d.weekday())
    return d.replace(day=1)


def period_end(kind, p):
    if kind == "day":
        return p + dt.timedelta(days=1)
    if kind == "week":
        return p + dt.timedelta(days=7)
    return (p.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def previous_period(kind, p):
    return period_start(kind, p - dt.timedelta(days=1))


def _dt(d):
    return dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)


def period_slots(name, p):
    kind = SPECS[name]["period"]
    return slots(name, _dt(p), _dt(period_end(kind, p)))


def latest_closed_period(name, now):
    """Последний период, чей последний слот (+ запас на прогон) уже в прошлом."""
    kind = SPECS[name]["period"]
    p = period_start(kind, now.date())
    for _ in range(4):
        s = period_slots(name, p)
        if s and s[-1] + GRACE <= now:
            return p, s[-1] + GRACE
        p = previous_period(kind, p)
    raise ScheduleError(f"{name}: нет закрытого периода за последние 4 (cron не даёт слотов?)")


# ---------------------------------------------------------------- facts from main -------------
def ensure_main():
    """-> None если origin/main свежий, иначе причина отказа (тогда всё UNKNOWN, не MISSING)."""
    rc, _, err = sh("git", "fetch", "--quiet", "origin", "main")
    return None if rc == 0 else f"UNAVAILABLE (git fetch origin main): rc={rc} {err.strip()[:200]}"


def on_main(path):
    """True/False; None — не удалось определить (ошибка git не равна «файла нет»)."""
    rc, out, _ = sh("git", "ls-tree", "--name-only", MAIN, "--", path)
    if rc != 0:
        return None
    return bool(out.strip())


def list_on_main(dirpath):
    rc, out, _ = sh("git", "ls-tree", "--name-only", MAIN, dirpath.rstrip("/") + "/")
    if rc != 0:
        return None
    return [os.path.basename(x) for x in out.splitlines() if x.strip()]


def activity_in_window(first_slot):
    """Были ли коммиты на main за 26 ч до слота: нет -> «пустой день», отчёта/аудита по дизайну нет."""
    since = (first_slot - dt.timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")
    until = first_slot.strftime("%Y-%m-%dT%H:%M:%SZ")
    rc, out, err = sh("git", "log", MAIN, f"--since={since}", f"--until={until}", "--format=%h", "-1")
    if rc != 0:
        return None
    return bool(out.strip())


def _day(s):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def panel_parts(p):
    """-> {'row': (state, detail), 'card': (state, detail)} для недели с понедельником p."""
    end = period_end("week", p)
    rc, out, err = sh("git", "show", f"{MAIN}:journal/PANEL_LOG.csv")
    if rc != 0:
        row = (UNKNOWN, f"UNAVAILABLE (git show {MAIN}:journal/PANEL_LOG.csv): rc={rc} {err.strip()[:200]}")
    else:
        weeks = [_day(r.get("week_end")) for r in csv.DictReader(io.StringIO(out))]
        hit = [w for w in weeks if w and p <= w < end]
        row = ((PUBLISHED, f"строка week_end={hit[0]} в journal/PANEL_LOG.csv на main") if hit else
               (MISSING, f"нет строки week_end в [{p}, {end}) в journal/PANEL_LOG.csv на main"))
    tool = on_main("tools/floor1_card.py")
    if tool is None:
        card = (UNKNOWN, "UNAVAILABLE (git ls-tree tools/floor1_card.py)")
    elif not tool:
        card = (NOT_REQUIRED, "tools/floor1_card.py ещё нет на main (задача К1) — карточка не требуется")
    else:
        names = list_on_main("Reports/floor1")
        if names is None:
            card = (UNKNOWN, "UNAVAILABLE (git ls-tree Reports/floor1)")
        else:
            hit = [n for n in names if FLOOR1_RE.match(n) and p <= _day(FLOOR1_RE.match(n).group(1)) < end]
            card = ((PUBLISHED, f"Reports/floor1/{hit[0]} на main") if hit else
                    (MISSING, f"нет Reports/floor1/FLOOR1_<дата>.md с датой в [{p}, {end}) на main"))
    return {"row": row, "card": card}


def gh_runs(file, since_date):
    """-> (runs|None, error|None). Фильтр по дате грубый (сутки), точный — на клиенте."""
    rc, out, err = sh("gh", "run", "list", "--workflow", file, "--created", f">={since_date}",
                      "--limit", str(RUN_LIMIT), "--json", "event,status,conclusion,createdAt")
    if rc != 0:
        return None, f"UNAVAILABLE (gh run list {file}): rc={rc} {err.strip()[:200]}"
    try:
        runs = json.loads(out)
        for r in runs:
            r["_t"] = dt.datetime.strptime(r["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except (ValueError, KeyError, TypeError) as e:
        return None, f"UNAVAILABLE (gh run list {file}: разбор ответа): {e!r}"
    return runs, None


def bridge_check(runs, since_date, now):
    """Возраст последнего УСПЕШНОГО прогона mail-bridge (любой event: schedule / workflow_run / dispatch).
    -> (state, detail, alert|None). Старше BRIDGE_MAX_AGE или успешных нет -> MISSING + alert.
    Нет успешного прогона в окне -> возраст неизвестен, называется нижняя граница («более N ч»)."""
    ok = [r["_t"] for r in runs if r["conclusion"] == "success"]
    if ok:
        age = max(now - max(ok), dt.timedelta(0))
        hours, bound = int(age.total_seconds() // 3600), ""
        detail = f"последний успешный прогон {max(ok):%Y-%m-%d %H:%M}Z, возраст {hours} ч"
    else:
        age = now - _dt(dt.date.fromisoformat(since_date))
        hours, bound = int(age.total_seconds() // 3600), "более "
        detail = f"успешных прогонов в окне с {since_date} нет (возраст не определить, нижняя граница {hours} ч)"
    if age <= BRIDGE_MAX_AGE:
        return PUBLISHED, detail, None
    return MISSING, detail, (f"Мост не запускался {bound}{hours} ч — Actions → mail-bridge → Run workflow "
                             f"{BRIDGE_URL}")


def result_state(name, p, check_activity=False):
    """Опубликован ли результат периода p workflow `name` на main. -> (state, detail)."""
    spec = SPECS[name]
    if spec.get("panel"):
        parts = panel_parts(p)
        for key in ("row", "card"):
            if parts[key][0] in (MISSING, UNKNOWN):
                return parts[key]
        return PUBLISHED, parts["row"][1] + ("; " + parts["card"][1] if parts["card"][0] == PUBLISHED else "")
    if spec.get("by_runs"):
        runs, err = gh_runs(spec["file"], p.isoformat())
        if runs is None:
            return UNKNOWN, err
        ok = [r for r in runs if r["conclusion"] == "success" and r["_t"] >= _dt(p)]
        return ((PUBLISHED, f"успешный прогон {ok[0]['createdAt']} ({ok[0]['event']})") if ok else
                (MISSING, f"нет успешного прогона {spec['file']} с {p}"))
    states = [on_main(x) for x in spec["paths"](p)]
    paths = ", ".join(spec["paths"](p))
    if any(s is None for s in states):
        return UNKNOWN, f"UNAVAILABLE (git ls-tree {MAIN} {paths})"
    if all(states):
        return PUBLISHED, f"{paths} на main"
    if check_activity and spec.get("activity"):
        first = period_slots(name, p)[0]
        act = activity_in_window(first)
        if act is None:
            return UNKNOWN, "UNAVAILABLE (git log: коммиты за 26 ч до слота)"
        if not act:
            return NOT_REQUIRED, f"пустой день: коммитов за 26 ч до {first:%Y-%m-%d %H:%M}Z нет — {paths} не формируется"
    return MISSING, f"нет {paths} на main"


# ---------------------------------------------------------------- idempotency -----------------
def already_published(name, now=None):
    """Результат ТЕКУЩЕГО периода уже на main? -> dict(published: bool, state, detail, row, card).
    UNKNOWN не равен «опубликовано»: слот работает (валидатор отсекает дубль недели)."""
    now = now or utcnow()
    spec = SPECS[name]
    if spec["period"] is None:
        return {"published": False, "state": NOT_REQUIRED, "detail": "у workflow нет результата периода",
                "row": False, "card": False}
    err = ensure_main()
    p = period_start(spec["period"], now.date())
    if err and not spec.get("by_runs"):
        return {"published": False, "state": UNKNOWN, "detail": err, "row": False, "card": False}
    if spec.get("panel"):
        parts = panel_parts(p)
        row = parts["row"][0] == PUBLISHED
        card = parts["card"][0] in (PUBLISHED, NOT_REQUIRED)
        det = "; ".join(f"{k}: {v[0]} ({v[1]})" for k, v in parts.items())
        st = PUBLISHED if row and card else (UNKNOWN if UNKNOWN in (parts["row"][0], parts["card"][0]) else MISSING)
        return {"published": row and card, "state": st, "detail": det, "row": row, "card": card,
                "card_published": parts["card"][0] == PUBLISHED}
    st, det = result_state(name, p)
    return {"published": st == PUBLISHED, "state": st, "detail": det, "row": st == PUBLISHED,
            "card": st == PUBLISHED}


def skip_if_published(name, now=None):
    """Для main() скриптов: True -> результат уже опубликован, вызывающий выходит с кодом 0."""
    r = already_published(name, now)
    if r["published"]:
        print(f"{name}: уже опубликовано — {r['detail']}")
        return True
    if r["state"] == UNKNOWN:
        print(f"WARN {name}: публикацию периода проверить не удалось, слот работает: {r['detail']}")
    return False


def panel_row_published(now=None):
    return already_published("panel-weekly", now)["row"]


# ---------------------------------------------------------------- watchdog --------------------
def watch(now=None, only=None):
    """-> list[dict] по workflow: name, expected, actual, truncated, period, state, detail, alert."""
    now = now or utcnow()
    names = [only] if only else list(SPECS)
    err = ensure_main()
    rows = []
    for name in names:
        spec = SPECS[name]
        row = {"name": name, "expected": None, "actual": None, "period": "—", "state": UNKNOWN,
               "detail": "", "alert": None, "truncated": False}
        rows.append(row)
        try:
            exp = slots(name, now - dt.timedelta(hours=24), now)
            row["expected"] = len(exp)
            runs, rerr = gh_runs(spec["file"], (now - dt.timedelta(hours=24)).date().isoformat())
            if runs is None:
                row["detail"] = rerr
            else:
                row["actual"] = len([r for r in runs if r["event"] == "schedule"
                                     and r["_t"] >= now - dt.timedelta(hours=24)])
                row["truncated"] = len(runs) >= RUN_LIMIT
            if spec["period"] is None:
                if row["actual"] is not None:
                    row["state"] = NOT_REQUIRED
                    row["detail"] = "результата периода нет (дедуп внутри скрипта)"
                    if name == "mail-bridge":      # возраст последнего успешного прогона, не число слотов
                        row["state"], row["detail"], row["alert"] = bridge_check(
                            runs, (now - dt.timedelta(hours=24)).date().isoformat(), now)
                continue
            p, deadline = latest_closed_period(name, now)
            row["period"] = str(p)
            if err and not spec.get("by_runs"):
                row["state"], row["detail"] = UNKNOWN, err
                continue
            row["state"], row["detail"] = result_state(name, p, check_activity=True)
            if row["state"] == MISSING and now - deadline <= NOTIFY_WINDOW:
                row["alert"] = f"результат периода {p} не опубликован ни одним слотом"
        except ScheduleError as e:
            row["state"], row["detail"] = UNKNOWN, f"UNAVAILABLE (расписание): {e}"
    return rows


def render(rows, now):
    out = ["## Пропущенные запуски", "",
           f"Окно 24 ч до {now:%Y-%m-%d %H:%M}Z; ожидаемые слоты читаются из .github/workflows/*.yml; "
           f"«было» = прогоны event=schedule по `gh run list` (лимит {RUN_LIMIT}).", "",
           "| workflow | ожидалось за 24 ч | было | период | статус | подробности |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        exp = "?" if r["expected"] is None else r["expected"]
        act = "?" if r["actual"] is None else (f"≥{r['actual']}" if r["truncated"] else r["actual"])
        mark = " ⚠" if r["alert"] else ""
        out.append(f"| {r['name']} | {exp} | {act} | {r['period']} | {r['state']}{mark} | {r['detail']} |")
    return "\n".join(out) + "\n"


def alert_text(r):
    if r["name"] == "mail-bridge":
        return r["alert"]
    return (f"Пропущен запуск: {r['name']} — {r['alert']}. Оператору: Actions → {r['name']} → "
            f"Run workflow (workflow_dispatch).")


def watch_section(now=None, only=None, notify=True):
    """-> (markdown, число проблем). Telegram — по каждому пропуску; UNKNOWN — одним сообщением."""
    now = now or utcnow()
    rows = watch(now, only)
    if notify:
        for r in rows:
            if r["alert"]:
                L.notify(alert_text(r))
        unk = [r for r in rows if r["state"] == UNKNOWN]
        if unk:
            L.notify("Сторож расписаний не смог проверить: "
                     + "; ".join(f"{r['name']} ({r['detail'][:80]})" for r in unk))
    bad = [r for r in rows if r["alert"] or r["state"] in (MISSING, UNKNOWN)]
    return render(rows, now), len(bad)


# ---------------------------------------------------------------- CLI -------------------------
def _set_env(**kv):
    path = os.environ.get("GITHUB_ENV")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def main(argv):
    if len(argv) >= 3 and argv[1] == "check" and argv[2] in SPECS:
        r = already_published(argv[2])
        print(f"{argv[2]}: {r['state']} — {r['detail']}")
        if r["published"]:
            print("уже опубликовано")
            _set_env(ALREADY_PUBLISHED="1")
        if r["row"]:
            _set_env(PANEL_ROW_PUBLISHED="1")
        if r.get("card_published"):
            _set_env(FLOOR1_PUBLISHED="1")
        return 0
    if len(argv) >= 2 and argv[1] == "watch":
        only = argv[argv.index("--only") + 1] if "--only" in argv else None
        if only is not None and only not in SPECS:
            print(f"usage: неизвестный workflow {only!r}; известные: {', '.join(SPECS)}")
            return 2
        now = utcnow()
        md, n = watch_section(now, only, notify="--notify" in argv)
        print(md)
        return 1 if n else 0
    print("usage: schedule_guard.py check <workflow> | watch [--only <workflow>] [--notify]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
