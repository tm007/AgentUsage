#!/usr/bin/env python3
import csv
import html
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


APP_NAME = "AgentUsage"
APP_TITLE = "AgentUsage Dashboard"
APP_ICON = "agentusage-icon.svg"
APP_MANIFEST = "agentusage.webmanifest"
ROOT = Path(__file__).resolve().parent
HOME = Path.home()


def iso_from_ms(value):
    if value is None:
        return ""
    try:
        value = int(value)
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def day_from_iso(value):
    if not value:
        return ""
    return value[:10]


def project_label(path):
    if not path:
        return "(unknown)"
    path = str(path)
    home = str(HOME)
    if path.startswith(home):
        path = "~" + path[len(home):]
    parts = [p for p in path.split("/") if p and p != "~"]
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1] if parts else path


PUBLIC_SAFE = os.environ.get("AGENTUSAGE_PUBLIC_SAFE", "1").lower() not in {"0", "false", "no"}


def clean_project(path):
    if not path:
        return ""
    path = str(path)
    home = str(HOME)
    if path.startswith(home):
        path = "~" + path[len(home):]
    if PUBLIC_SAFE:
        return project_label(path)
    return path


def state_dir():
    override = os.environ.get("AI_USAGE_DASHBOARD_STATE_DIR")
    return Path(override).expanduser() if override else (HOME / ".ai-usage-dashboard")


def claude_cache_path():
    return state_dir() / "claude-token-cache.json"


def session_archive_path():
    return state_dir() / "session-archive.json"


def merge_session_record(target, source):
    if not source:
        return target
    for field in ["project_path", "project_label", "model", "day", "confidence"]:
        if not target.get(field) and source.get(field):
            target[field] = source.get(field)
    if source.get("start_time") and (not target.get("start_time") or source["start_time"] < target["start_time"]):
        target["start_time"] = source["start_time"]
    if source.get("end_time") and (not target.get("end_time") or source["end_time"] > target["end_time"]):
        target["end_time"] = source["end_time"]
    for field in [
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "total_tokens",
        "activity_proxy",
        "cost_proxy",
        "files_modified",
        "lines_added",
        "lines_removed",
        "read_ops",
        "write_ops",
        "duration_minutes",
        "message_count",
    ]:
        target[field] = max(float(target.get(field) or 0), float(source.get(field) or 0))
        if field != "cost_proxy" and field != "duration_minutes":
            target[field] = int(target[field])
    target["cost_proxy"] = float(target["cost_proxy"])
    target["duration_minutes"] = int(target["duration_minutes"])
    if source.get("exact_tokens"):
        target["exact_tokens"] = True
    if target.get("exact_tokens") and target.get("total_tokens", 0) <= 0:
        target["total_tokens"] = int(target.get("input_tokens", 0)) + int(target.get("output_tokens", 0)) + int(target.get("cache_creation_tokens", 0)) + int(target.get("cache_read_tokens", 0))
    if target.get("exact_tokens"):
        target["activity_proxy"] = max(int(target.get("activity_proxy") or 0), int(target.get("total_tokens") or 0))
        target["confidence"] = "high"
    if not target.get("data_notes") and source.get("data_notes"):
        target["data_notes"] = source["data_notes"]
    return target


def load_session_cache():
    path = claude_cache_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    items = raw.get("sessions") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return {}
    records = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = item.get("session_id") or item.get("id")
        if not sid:
            continue
        rec = empty_session(item.get("tool") or "Claude", sid)
        rec.update(item)
        rec["session_id"] = sid
        rec["tool"] = "Claude"
        records[sid] = rec
    return records


def save_session_cache(sessions):
    records = load_session_cache()
    for session in sessions:
        if not isinstance(session, dict):
            continue
        if session.get("tool") != "Claude":
            continue
        sid = session.get("session_id")
        if not sid:
            continue
        rec = records.setdefault(sid, empty_session("Claude", sid))
        merge_session_record(rec, session)
        rec["tool"] = "Claude"
    path = claude_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "sessions": sorted(records.values(), key=lambda r: r.get("session_id", ""))}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def load_session_archive():
    path = session_archive_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    items = raw.get("sessions") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return {}
    records = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = item.get("session_id") or item.get("id")
        if not sid:
            continue
        rec = empty_session(item.get("tool") or "", sid)
        rec.update(item)
        rec["session_id"] = sid
        records[sid] = rec
    return records


def merge_session_from_archive(target, source):
    if not source:
        return target
    merge_session_record(target, source)
    if not target.get("tool") and source.get("tool"):
        target["tool"] = source.get("tool")
    return target


def save_session_archive(sessions):
    records = load_session_archive()
    for session in sessions:
        if not isinstance(session, dict):
            continue
        sid = session.get("session_id")
        if not sid:
            continue
        rec = records.setdefault(sid, empty_session(session.get("tool") or "", sid))
        merge_session_from_archive(rec, session)
        rec["tool"] = session.get("tool") or rec.get("tool") or ""
    path = session_archive_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "sessions": sorted(records.values(), key=lambda r: (r.get("tool", ""), r.get("session_id", "")))}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def merge_session_archive(live_sessions):
    records = {}
    for session in live_sessions:
        if not isinstance(session, dict):
            continue
        sid = session.get("session_id")
        if not sid:
            continue
        records[sid] = dict(session)
    for sid, archived in load_session_archive().items():
        rec = records.setdefault(sid, empty_session(archived.get("tool") or "", sid))
        merge_session_from_archive(rec, archived)
        rec["tool"] = archived.get("tool") or rec.get("tool") or ""
    return list(records.values())


def merge_claude_statusline(sessions_by_id, status_file=None):
    path = Path(status_file) if status_file else (HOME / ".claude" / "statusline-msgcount.json")
    if not path.exists():
        return sessions_by_id
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return sessions_by_id
    sessions = raw.get("sessions") if isinstance(raw, dict) else {}
    if not isinstance(sessions, dict):
        return sessions_by_id
    for sid, info in sessions.items():
        if not sid or not isinstance(info, dict):
            continue
        rec = sessions_by_id.setdefault(sid, empty_session("Claude", sid))
        msg_num = int(info.get("msg_num") or 0)
        out_tokens = int(info.get("out_tokens") or 0)
        if msg_num and not rec["message_count"]:
            rec["message_count"] = msg_num
        if out_tokens and not rec["exact_tokens"]:
            rec["output_tokens"] = max(int(rec["output_tokens"] or 0), out_tokens)
            rec["activity_proxy"] = max(int(rec["activity_proxy"] or 0), out_tokens)
            if rec["total_tokens"] <= 0:
                rec["total_tokens"] = out_tokens
            rec["data_notes"] = rec["data_notes"] or "Claude statusline msgcount fallback; output tokens only."
            if rec["confidence"] == "low":
                rec["confidence"] = "medium"
    return sessions_by_id


def merge_cached_sessions(live_sessions):
    records = {}
    for session in live_sessions:
        if not isinstance(session, dict):
            continue
        sid = session.get("session_id")
        if not sid:
            continue
        records[sid] = dict(session)
    for sid, cached in load_session_cache().items():
        rec = records.setdefault(sid, empty_session("Claude", sid))
        merge_session_record(rec, cached)
        rec["tool"] = "Claude"
    return list(records.values())


def empty_session(tool, session_id):
    return {
        "tool": tool,
        "session_id": session_id or "",
        "project_path": "",
        "project_label": "(unknown)",
        "start_time": "",
        "end_time": "",
        "day": "",
        "model": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
        "exact_tokens": False,
        "activity_proxy": 0,
        "cost_proxy": 0.0,
        "files_modified": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "read_ops": 0,
        "write_ops": 0,
        "duration_minutes": 0,
        "message_count": 0,
        "confidence": "low",
        "data_notes": "",
    }


def parse_claude():
    sessions_by_id = {}
    raw_dir = HOME / ".claude" / "projects"
    if raw_dir.exists():
        seen_usage = set()
        for path in raw_dir.rglob("*.jsonl"):
            try:
                lines = path.open(errors="ignore")
            except Exception:
                continue
            with lines as f:
                for line in f:
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    sid = data.get("sessionId") or path.stem
                    agent_id = data.get("agentId") if data.get("isSidechain") else ""
                    rec_id = f"{sid}::{agent_id}" if agent_id else sid
                    rec = sessions_by_id.setdefault(rec_id, empty_session("Claude", rec_id))
                    cwd = data.get("cwd") or rec["project_path"]
                    if cwd and not rec["project_path"]:
                        rec["project_path"] = clean_project(cwd)
                        rec["project_label"] = project_label(cwd)
                    ts = data.get("timestamp") or ""
                    if ts and (not rec["start_time"] or ts < rec["start_time"]):
                        rec["start_time"] = ts
                        rec["day"] = day_from_iso(ts)
                    if ts and (not rec["end_time"] or ts > rec["end_time"]):
                        rec["end_time"] = ts
                    typ = data.get("type")
                    if typ in {"user", "assistant"}:
                        rec["message_count"] += 1
                    msg = data.get("message") if isinstance(data.get("message"), dict) else {}
                    if msg.get("model") and not rec["model"]:
                        rec["model"] = msg.get("model") or ""
                    content = msg.get("content") or []
                    if isinstance(content, list):
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_use":
                                continue
                            name = item.get("name") or ""
                            if name in {"Read", "Grep", "Glob", "LS", "WebSearch", "WebFetch"}:
                                rec["read_ops"] += 1
                            if name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
                                rec["write_ops"] += 1
                    usage = msg.get("usage") if isinstance(msg, dict) else None
                    if usage:
                        usage_key = (str(path), data.get("requestId") or msg.get("id") or data.get("uuid"))
                        if usage_key in seen_usage:
                            continue
                        seen_usage.add(usage_key)
                        rec["input_tokens"] += int(usage.get("input_tokens") or 0)
                        rec["output_tokens"] += int(usage.get("output_tokens") or 0)
                        rec["cache_creation_tokens"] += int(usage.get("cache_creation_input_tokens") or 0)
                        rec["cache_read_tokens"] += int(usage.get("cache_read_input_tokens") or 0)
                        rec["exact_tokens"] = True
                        rec["confidence"] = "high"
        for rec in sessions_by_id.values():
            rec["total_tokens"] = (
                rec["input_tokens"]
                + rec["output_tokens"]
                + rec["cache_creation_tokens"]
                + rec["cache_read_tokens"]
            )
            rec["activity_proxy"] = rec["total_tokens"]
            rec["data_notes"] = "Exact Claude raw usage from projects JSONL, deduped by request/message id; total includes cache creation/read tokens."

    meta_dir = HOME / ".claude" / "usage-data" / "session-meta"
    if meta_dir.exists():
        for path in meta_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            sid = data.get("session_id") or path.stem
            rec = sessions_by_id.setdefault(sid, empty_session("Claude", sid))
            if not rec["project_path"]:
                rec["project_path"] = clean_project(data.get("project_path", ""))
                rec["project_label"] = project_label(data.get("project_path", ""))
            if not rec["start_time"]:
                rec["start_time"] = data.get("start_time", "")
                rec["day"] = day_from_iso(rec["start_time"])
            if not rec["exact_tokens"]:
                rec["input_tokens"] = int(data.get("input_tokens") or 0)
                rec["output_tokens"] = int(data.get("output_tokens") or 0)
                rec["total_tokens"] = rec["input_tokens"] + rec["output_tokens"]
                rec["exact_tokens"] = rec["total_tokens"] > 0
                rec["activity_proxy"] = rec["total_tokens"]
            rec["duration_minutes"] = int(data.get("duration_minutes") or 0)
            rec["files_modified"] = int(data.get("files_modified") or 0)
            rec["lines_added"] = int(data.get("lines_added") or 0)
            rec["lines_removed"] = int(data.get("lines_removed") or 0)
            if not rec["message_count"]:
                rec["message_count"] = int(data.get("user_message_count") or 0) + int(data.get("assistant_message_count") or 0)
            tools = data.get("tool_counts") or {}
            if not rec["read_ops"]:
                rec["read_ops"] = int(tools.get("Read", 0) + tools.get("Grep", 0) + tools.get("Glob", 0))
            if not rec["write_ops"]:
                rec["write_ops"] = int(tools.get("Write", 0) + tools.get("Edit", 0) + tools.get("MultiEdit", 0))
            rec["confidence"] = "high"
            rec["data_notes"] = rec["data_notes"] or "Exact token fields from Claude session metadata."

    # Fallback: parse history.jsonl for sessions without project files
    history_file = HOME / ".claude" / "history.jsonl"
    if history_file.exists():
        history_sessions = {}
        with history_file.open(errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                sid = data.get("sessionId")
                if not sid:
                    continue
                if sid not in sessions_by_id:
                    history_sessions.setdefault(sid, []).append(data)
        for sid, msgs in history_sessions.items():
            rec = sessions_by_id.setdefault(sid, empty_session("Claude", sid))
            if rec.get("exact_tokens"):
                continue  # Already have real data for this session
            timestamps = [m["timestamp"] for m in msgs if m.get("timestamp")]
            projects = [m["project"] for m in msgs if m.get("project")]
            if timestamps:
                ts_min = min(timestamps)
                ts_max = max(timestamps)
                rec["start_time"] = iso_from_ms(ts_min)
                rec["end_time"] = iso_from_ms(ts_max)
                rec["day"] = day_from_iso(rec["start_time"])
            if projects and not rec["project_path"]:
                rec["project_path"] = clean_project(projects[0])
                rec["project_label"] = project_label(projects[0])
            rec["message_count"] = len(msgs)
            # Estimate activity from total text length (rough proxy)
            total_chars = sum(len(m.get("display", "")) for m in msgs)
            rec["activity_proxy"] = max(rec["activity_proxy"], total_chars)
            rec["confidence"] = "medium"
            rec["data_notes"] = rec["data_notes"] or "Session inferred from history.jsonl; exact tokens unavailable."

    sessions_by_id = merge_claude_statusline(sessions_by_id)
    sessions = merge_cached_sessions(list(sessions_by_id.values()))
    save_session_cache(sessions)
    return sessions


def parse_codex():
    sessions = {}
    state_db = HOME / ".codex" / "state_5.sqlite"
    if state_db.exists():
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                "select id, rollout_path, cwd, model, reasoning_effort, tokens_used, created_at_ms, updated_at_ms "
                "from threads"
            ):
                sid = row["id"]
                rec = sessions.setdefault(sid, empty_session("Codex", sid))
                project = row["cwd"] or ""
                rec["project_path"] = clean_project(project)
                rec["project_label"] = project_label(project)
                rec["start_time"] = iso_from_ms(row["created_at_ms"])
                rec["end_time"] = iso_from_ms(row["updated_at_ms"])
                rec["day"] = day_from_iso(rec["start_time"])
                rec["model"] = " ".join(x for x in [row["model"], row["reasoning_effort"]] if x)
                rec["total_tokens"] = int(row["tokens_used"] or 0)
                rollout_path = row["rollout_path"] or ""
                if rollout_path:
                    rollout = Path(rollout_path)
                    if not rollout.is_absolute():
                        rollout = HOME / ".codex" / rollout_path
                    if rollout.exists():
                        token_total = None
                        try:
                            with rollout.open(errors="ignore") as f:
                                for line in f:
                                    try:
                                        event = json.loads(line)
                                    except Exception:
                                        continue
                                    payload = event.get("payload") or {}
                                    if payload.get("type") != "token_count":
                                        continue
                                    info = payload.get("info") or {}
                                    usage = info.get("total_token_usage") or {}
                                    if usage:
                                        token_total = usage
                            if token_total:
                                rec["input_tokens"] = int(token_total.get("input_tokens") or 0)
                                rec["output_tokens"] = int(token_total.get("output_tokens") or 0)
                                rec["cache_read_tokens"] = int(token_total.get("cached_input_tokens") or 0)
                                rec["total_tokens"] = int(token_total.get("total_tokens") or rec["total_tokens"])
                        except Exception:
                            pass
                rec["exact_tokens"] = rec["total_tokens"] > 0
                rec["activity_proxy"] = rec["total_tokens"]
                rec["confidence"] = "high" if rec["exact_tokens"] else "medium"
                rec["data_notes"] = "Exact Codex token total from state_5.sqlite; input/output split from rollout token_count when present."
        finally:
            conn.close()

    history = HOME / ".codex" / "history.jsonl"
    if history.exists():
        with history.open(errors="ignore") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                sid = data.get("session_id")
                if not sid:
                    continue
                rec = sessions.setdefault(sid, empty_session("Codex", sid))
                ts = data.get("ts")
                iso = iso_from_ms(ts)
                if iso and (not rec["start_time"] or iso < rec["start_time"]):
                    rec["start_time"] = iso
                    rec["day"] = day_from_iso(iso)
                rec["message_count"] += 1
                if not rec["exact_tokens"]:
                    rec["activity_proxy"] += len(data.get("text") or "")

    index = HOME / ".codex" / "session_index.jsonl"
    names = {}
    if index.exists():
        with index.open(errors="ignore") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                if data.get("id"):
                    names[data["id"]] = data.get("thread_name") or ""

    db = HOME / ".codex" / "logs_2.sqlite"
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                "select thread_id, min(ts) min_ts, max(ts) max_ts, count(*) n, sum(estimated_bytes) bytes "
                "from logs where thread_id is not null group by thread_id"
            ):
                sid = row["thread_id"]
                rec = sessions.setdefault(sid, empty_session("Codex", sid))
                rec["start_time"] = rec["start_time"] or iso_from_ms(row["min_ts"])
                rec["end_time"] = iso_from_ms(row["max_ts"])
                rec["day"] = rec["day"] or day_from_iso(rec["start_time"])
                if not rec["exact_tokens"]:
                    rec["activity_proxy"] += int(row["n"] or 0)
                rec["cost_proxy"] += int(row["bytes"] or 0)
                rec["data_notes"] = "Codex logs expose thread/model/cwd activity; exact tokens are included only when telemetry fields are found."
            pattern = re.compile(r"cwd=([^}:]+)")
            model_re = re.compile(r"model=([A-Za-z0-9._/-]+)")
            for row in conn.execute(
                "select thread_id, target, feedback_log_body from logs "
                "where thread_id is not null and target like '%cwd=%'"
            ):
                sid = row["thread_id"]
                rec = sessions.setdefault(sid, empty_session("Codex", sid))
                text = (row["target"] or "") + " " + (row["feedback_log_body"] or "")
                if not rec["project_path"]:
                    m = pattern.search(text)
                    if m:
                        project = m.group(1).strip().strip('"')
                        rec["project_path"] = clean_project(project)
                        rec["project_label"] = project_label(project)
                if not rec["model"]:
                    m = model_re.search(text)
                    if m:
                        rec["model"] = m.group(1)
            for rec in sessions.values():
                if not rec["exact_tokens"]:
                    rec["input_tokens"] = 0
                    rec["output_tokens"] = 0
                    rec["total_tokens"] = 0
                    rec["exact_tokens"] = False
                    rec["confidence"] = "medium" if rec["project_path"] else "low"
                if not rec["project_path"] and rec["session_id"] in names:
                    rec["project_label"] = names[rec["session_id"]]
        finally:
            conn.close()
    for rec in sessions.values():
        rec["data_notes"] = rec["data_notes"] or "Codex history/session metadata; tokens unavailable, activity proxy used."
    return list(sessions.values())


def parse_cursor():
    sessions = []
    status_dir = HOME / ".cursor" / "statusline-state"
    cursor_token_sessions = set()
    if status_dir.exists():
        for path in status_dir.glob("session-*-last"):
            sid = path.name.removeprefix("session-").removesuffix("-last")
            try:
                parts = path.read_text().strip().split()
                input_tokens = int(float(parts[0])) if len(parts) >= 1 else 0
                output_tokens = int(float(parts[1])) if len(parts) >= 2 else 0
            except Exception:
                input_tokens = 0
                output_tokens = 0
            rec = empty_session("Cursor", sid)
            start_file = status_dir / f"session-{sid}-start"
            cost_file = status_dir / f"session-{sid}-cost"
            msg_file = status_dir / f"session-{sid}-msgcount"
            if start_file.exists():
                try:
                    rec["start_time"] = iso_from_ms(int(start_file.read_text().strip()))
                    rec["day"] = day_from_iso(rec["start_time"])
                except Exception:
                    pass
            if cost_file.exists():
                try:
                    rec["cost_proxy"] = float(cost_file.read_text().strip() or 0)
                except Exception:
                    pass
            if msg_file.exists():
                try:
                    rec["message_count"] = int(float(msg_file.read_text().strip() or 0))
                except Exception:
                    pass
            rec["input_tokens"] = input_tokens
            rec["output_tokens"] = output_tokens
            rec["total_tokens"] = input_tokens + output_tokens
            rec["exact_tokens"] = rec["total_tokens"] > 0
            rec["activity_proxy"] = rec["total_tokens"]
            rec["confidence"] = "high" if rec["exact_tokens"] else "medium"
            rec["data_notes"] = "Cursor statusline cumulative input/output token totals from session-*-last."
            sessions.append(rec)
            cursor_token_sessions.add(sid)

    db = HOME / ".cursor" / "ai-tracking" / "ai-code-tracking.db"
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                "select coalesce(conversationId, requestId, source || ':' || fileName) sid, "
                "min(createdAt) min_ts, max(createdAt) max_ts, count(*) n, "
                "sum(case when source in ('composer','tab') then 1 else 0 end) ai_n, "
                "group_concat(distinct model) models "
                "from ai_code_hashes group by sid"
            ):
                sid = row["sid"] or "cursor-ai-code"
                rec = empty_session("Cursor", sid)
                rec["start_time"] = iso_from_ms(row["min_ts"])
                rec["end_time"] = iso_from_ms(row["max_ts"])
                rec["day"] = day_from_iso(rec["start_time"])
                rec["model"] = (row["models"] or "").strip(",")
                rec["activity_proxy"] = int(row["n"] or 0)
                rec["write_ops"] = int(row["ai_n"] or 0)
                rec["confidence"] = "medium"
                rec["data_notes"] = "Cursor AI-code tracking rows; token counts are not available locally."
                sessions.append(rec)
        finally:
            conn.close()

    if status_dir.exists():
        for path in status_dir.glob("day-*.tsv"):
            rec = empty_session("Cursor", f"cursor-statusline-{path.stem.removeprefix('day-')}")
            rec["start_time"] = f"{path.stem.removeprefix('day-')}T00:00:00Z"
            rec["day"] = path.stem.removeprefix("day-")
            try:
                value = float(path.read_text().strip() or 0)
            except Exception:
                value = 0.0
            rec["cost_proxy"] = value
            rec["activity_proxy"] = value
            rec["confidence"] = "low"
            rec["data_notes"] = "Cursor statusline daily value; treated as cost/activity proxy."
            sessions.append(rec)

    projects = HOME / ".cursor" / "projects"
    if projects.exists():
        for project in projects.iterdir():
            if not project.is_dir():
                continue
            rec = empty_session("Cursor", f"cursor-project-{project.name}")
            label = project.name
            if label.startswith("Users-"):
                label = label.removeprefix("Users-")
                parts = label.split("-", 1)
                label = parts[1] if len(parts) == 2 else label
            label = label.replace("-", "/")
            rec["project_path"] = "~/" + label if not label.startswith("/") else label
            rec["project_label"] = project_label(label)
            rec["start_time"] = iso_from_ms(int(project.stat().st_mtime))
            rec["day"] = day_from_iso(rec["start_time"])
            rec["activity_proxy"] = sum(1 for _ in project.rglob("*") if _.is_file())
            rec["confidence"] = "low"
            rec["data_notes"] = "Cursor project workspace files; project attention proxy only."
            sessions.append(rec)
    return sessions


def parse_opencode():
    db = HOME / ".local" / "share" / "opencode" / "opencode.db"
    sessions = {}
    if not db.exists():
        install_dir = HOME / ".opencode"
        state_dir = HOME / ".local" / "state" / "opencode"
        rec = empty_session("OpenCode", "opencode-local")
        stamp_source = install_dir if install_dir.exists() else state_dir
        if stamp_source.exists():
            rec["start_time"] = iso_from_ms(int(stamp_source.stat().st_mtime))
            rec["day"] = day_from_iso(rec["start_time"])
        rec["confidence"] = "low"
        rec["data_notes"] = "No OpenCode SQLite usage database found under ~/.local/share/opencode."
        return [rec]

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(
            "select s.id, s.project_id, s.directory, s.path, s.time_created, s.time_updated, "
            "s.summary_additions, s.summary_deletions, s.summary_files, p.worktree, p.name "
            "from session s left join project p on p.id = s.project_id"
        ):
            sid = row["id"]
            rec = sessions.setdefault(sid, empty_session("OpenCode", sid))
            project = row["worktree"] or row["directory"] or row["path"] or ""
            rec["project_path"] = clean_project(project)
            rec["project_label"] = project_label(project)
            rec["start_time"] = iso_from_ms(row["time_created"])
            rec["end_time"] = iso_from_ms(row["time_updated"])
            rec["day"] = day_from_iso(rec["start_time"])
            rec["lines_added"] = int(row["summary_additions"] or 0)
            rec["lines_removed"] = int(row["summary_deletions"] or 0)
            rec["files_modified"] = int(row["summary_files"] or 0)
            rec["confidence"] = "medium"
            rec["data_notes"] = "OpenCode session/project metadata from ~/.local/share/opencode/opencode.db."

        for row in conn.execute("select id, session_id, time_created, time_updated, data from message"):
            sid = row["session_id"]
            rec = sessions.setdefault(sid, empty_session("OpenCode", sid))
            rec["message_count"] += 1
            if row["time_created"]:
                created = iso_from_ms(row["time_created"])
                if created and (not rec["start_time"] or created < rec["start_time"]):
                    rec["start_time"] = created
                    rec["day"] = day_from_iso(created)
            if row["time_updated"]:
                updated = iso_from_ms(row["time_updated"])
                if updated and (not rec["end_time"] or updated > rec["end_time"]):
                    rec["end_time"] = updated
            try:
                data = json.loads(row["data"] or "{}")
            except Exception:
                continue
            path_info = data.get("path") if isinstance(data.get("path"), dict) else {}
            project = path_info.get("root") or path_info.get("cwd") or ""
            if project and not rec["project_path"]:
                rec["project_path"] = clean_project(project)
                rec["project_label"] = project_label(project)
            model_info = data.get("model") if isinstance(data.get("model"), dict) else {}
            model = data.get("modelID") or model_info.get("modelID") or ""
            provider = data.get("providerID") or model_info.get("providerID") or ""
            agent = data.get("agent") or data.get("mode") or ""
            model_label = " ".join(x for x in [provider, model, agent] if x)
            if model_label and (not rec["model"] or model in model_label and model not in rec["model"]):
                rec["model"] = model_label
            rec["cost_proxy"] += float(data.get("cost") or 0)
            tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
            if tokens:
                cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
                input_tokens = int(tokens.get("input") or 0)
                output_tokens = int(tokens.get("output") or 0)
                cache_write = int(cache.get("write") or 0)
                cache_read = int(cache.get("read") or 0)
                total = int(tokens.get("total") or (input_tokens + output_tokens + cache_write + cache_read))
                rec["input_tokens"] += input_tokens
                rec["output_tokens"] += output_tokens
                rec["cache_creation_tokens"] += cache_write
                rec["cache_read_tokens"] += cache_read
                rec["total_tokens"] += total
                if total or input_tokens or output_tokens or cache_write or cache_read:
                    rec["exact_tokens"] = True
                    rec["confidence"] = "high"
                    rec["data_notes"] = "Exact OpenCode tokens/cost from message.data in ~/.local/share/opencode/opencode.db; total includes cache read/write tokens."

        for row in conn.execute("select session_id, data from part"):
            sid = row["session_id"]
            rec = sessions.setdefault(sid, empty_session("OpenCode", sid))
            try:
                data = json.loads(row["data"] or "{}")
            except Exception:
                continue
            typ = data.get("type") or ""
            tool = (data.get("tool") or "").lower()
            state = data.get("state") if isinstance(data.get("state"), dict) else {}
            input_data = state.get("input") if isinstance(state.get("input"), dict) else {}
            fileish = " ".join(str(x).lower() for x in [tool, input_data.get("filePath"), input_data.get("path"), input_data.get("command")])
            if typ == "tool":
                rec["activity_proxy"] += 1
                if tool in {"read", "grep", "glob", "list", "ls"} or "grep" in fileish or "find" in fileish:
                    rec["read_ops"] += 1
                if tool in {"write", "edit", "patch"} or any(x in fileish for x in ["apply_patch", "write", "edit"]):
                    rec["write_ops"] += 1
            elif typ in {"text", "reasoning"}:
                rec["activity_proxy"] += 1

        for rec in sessions.values():
            if not rec["project_label"] or rec["project_label"] == "(unknown)":
                rec["project_label"] = project_label(rec["project_path"])
            if rec["start_time"] and rec["end_time"]:
                try:
                    start = datetime.fromisoformat(rec["start_time"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(rec["end_time"].replace("Z", "+00:00"))
                    rec["duration_minutes"] = max(0, int((end - start).total_seconds() // 60))
                except Exception:
                    pass
            if rec["exact_tokens"]:
                rec["activity_proxy"] = max(rec["activity_proxy"], rec["total_tokens"])
            elif not rec["data_notes"]:
                rec["data_notes"] = "OpenCode activity record without token telemetry."
    finally:
        conn.close()
    return list(sessions.values())


def aggregate(sessions):
    tools = {}
    projects = {}
    days = defaultdict(lambda: defaultdict(float))
    models = Counter()
    for rec in sessions:
        tool = rec["tool"]
        t = tools.setdefault(tool, {
            "tool": tool, "sessions": 0, "projects": set(), "active_days": set(),
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "exact_token_sessions": 0,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "activity_proxy": 0, "cost_proxy": 0, "read_ops": 0, "write_ops": 0,
            "files_modified": 0, "lines_added": 0, "lines_removed": 0,
        })
        t["sessions"] += 1
        if rec["project_label"] != "(unknown)":
            t["projects"].add(rec["project_label"])
        if rec["day"]:
            t["active_days"].add(rec["day"])
            days[rec["day"]][tool] += rec["total_tokens"] if rec["exact_tokens"] else rec["activity_proxy"]
        for k in ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens", "total_tokens", "activity_proxy", "cost_proxy", "read_ops", "write_ops", "files_modified", "lines_added", "lines_removed"]:
            t[k] += rec[k]
        if rec["exact_tokens"]:
            t["exact_token_sessions"] += 1
        if rec["model"]:
            models[(tool, rec["model"])] += 1

        key = (rec["tool"], rec["project_label"])
        p = projects.setdefault(key, {
            "tool": rec["tool"], "project": rec["project_label"], "project_path": "" if PUBLIC_SAFE else rec["project_path"],
            "sessions": 0, "total_tokens": 0, "activity_proxy": 0, "duration_minutes": 0,
            "files_modified": 0, "lines_added": 0, "lines_removed": 0, "confidence": rec["confidence"],
        })
        p["sessions"] += 1
        for k in ["total_tokens", "activity_proxy", "duration_minutes", "files_modified", "lines_added", "lines_removed"]:
            p[k] += rec[k]
        if not PUBLIC_SAFE and len(p["project_path"]) < len(rec["project_path"]):
            p["project_path"] = rec["project_path"]

    tool_rows = []
    for t in tools.values():
        t["projects"] = len(t["projects"])
        t["active_days"] = len(t["active_days"])
        tool_rows.append(t)
    project_rows = sorted(projects.values(), key=lambda p: (p["total_tokens"], p["activity_proxy"], p["sessions"]), reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tools": sorted(tool_rows, key=lambda t: (t["total_tokens"], t["activity_proxy"]), reverse=True),
        "projects": project_rows,
        "days": [{"day": d, **dict(vals)} for d, vals in sorted(days.items())],
        "models": [{"tool": k[0], "model": k[1], "sessions": v} for k, v in models.most_common()],
    }


def write_csv(sessions):
    path = ROOT / "usage-sessions.csv"
    fields = list(empty_session("", "").keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in sessions:
            writer.writerow({k: rec.get(k, "") for k in fields})
    return path


def render_dashboard(summary, sessions):
    payload = json.dumps({"summary": summary, "sessions": sessions}, separators=(",", ":"))
    icon_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-labelledby="title desc">
  <title>{html.escape(APP_NAME)}</title>
  <desc>AgentUsage app icon</desc>
  <defs>
    <linearGradient id="g" x1="16" y1="16" x2="112" y2="112" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#00aeef"/>
      <stop offset="1" stop-color="#ec008c"/>
    </linearGradient>
  </defs>
  <rect x="10" y="10" width="108" height="108" rx="26" fill="#0b0d10"/>
  <rect x="16" y="16" width="96" height="96" rx="22" fill="url(#g)" opacity="0.16"/>
  <circle cx="64" cy="64" r="30" fill="none" stroke="url(#g)" stroke-width="12"/>
  <path d="M48 78 64 38l16 40h-10.8l-2.8-7H61.5l-2.7 7H48Zm17-16-5-13-5 13h10Z" fill="#eef3f7"/>
</svg>"""
    (ROOT / APP_ICON).write_text(icon_svg)
    manifest = {
        "name": APP_NAME,
        "short_name": APP_NAME,
        "start_url": ".",
        "scope": ".",
        "display": "standalone",
        "background_color": "#0b0d10",
        "theme_color": "#0b0d10",
        "icons": [
            {
                "src": APP_ICON,
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    (ROOT / APP_MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    css = """
    :root{color-scheme:dark;--bg:#0b0d10;--panel:#12161b;--panel2:#171d24;--line:#27313b;--line2:#344251;--text:#eef3f7;--muted:#91a0ad;--soft:#c7d1da;--c:#00aeef;--m:#ec008c;--y:#ffd200;--k:#eef3f7;--a:#00aeef;--b:#ffd200;--d:#00aeef;--e:#ec008c;--good:#ffd200}
    *{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#0f1217 0,#0b0d10 46%,#090b0e 100%);color:var(--text);font:13px/1.42 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}
    header{position:sticky;top:0;z-index:5;background:rgba(11,13,16,.86);backdrop-filter:blur(18px);border-bottom:1px solid var(--line);padding:18px 28px}h1{font-size:20px;margin:0;font-weight:780}h2{font-size:15px;margin:0 0 12px;font-weight:720}h3{font-size:12px;margin:16px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}main{max-width:1680px;margin:0 auto;padding:22px 28px 44px}.topbar{display:flex;align-items:end;justify-content:space-between;gap:18px}.stamp{color:var(--muted);font-variant-numeric:tabular-nums}.grid{display:grid;gap:14px}.cards{grid-template-columns:repeat(6,minmax(150px,1fr));margin-bottom:14px}.card,section{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:8px;padding:14px;box-shadow:0 18px 60px rgba(0,0,0,.18)}.metric{font-size:25px;font-weight:800;line-height:1.05;font-variant-numeric:tabular-nums}.label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px}.sub{color:var(--muted);font-size:12px;margin-top:6px}.two{grid-template-columns:minmax(0,1.2fr) minmax(420px,.8fr)}.three{grid-template-columns:1fr 1fr 1fr}.span2{grid-column:span 2}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.chip{border:1px solid var(--line2);background:#10151b;border-radius:999px;color:var(--soft);padding:5px 9px;font-size:12px}.chip strong{color:var(--text)}table{width:100%;border-collapse:collapse}th,td{padding:8px 7px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}th{color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}td.num{text-align:right;font-variant-numeric:tabular-nums}.name{font-weight:700}.path{color:var(--muted);font-size:11px;margin-top:2px;max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bar{height:8px;background:#222b34;border-radius:999px;overflow:hidden;min-width:68px}.bar span{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--d))}.stack{display:flex;height:10px;border-radius:999px;overflow:hidden;background:#202832}.stack span:nth-child(1){background:var(--d)}.stack span:nth-child(2){background:var(--e)}.stack span:nth-child(3){background:var(--a)}.stack span:nth-child(4){background:var(--b)}svg{width:100%;height:auto;display:block}.legend{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(13px,1fr));gap:3px}.cell{aspect-ratio:1;border-radius:3px;background:#1d242d}.mini{height:78px}.muted{color:var(--muted)}.quality{display:grid;gap:9px}.quality-row{display:grid;grid-template-columns:92px 1fr auto;gap:10px;align-items:center}.quality-row .bar{height:9px}.section-gap{margin-top:14px}.scroll{max-height:470px;overflow:auto;padding-right:4px}.scroll::-webkit-scrollbar{width:8px}.scroll::-webkit-scrollbar-thumb{background:#2d3844;border-radius:999px}@media(max-width:1200px){.cards{grid-template-columns:repeat(3,1fr)}.two,.three{grid-template-columns:1fr}.span2{grid-column:auto}}@media(max-width:720px){main,header{padding-left:14px;padding-right:14px}.cards{grid-template-columns:1fr 1fr}.metric{font-size:21px}.topbar{display:block}.hide-sm{display:none}}
    """
    js = """
    const DATA=__DATA__;
    const fmt=new Intl.NumberFormat();
    const colors=['#00aeef','#ec008c','#ffd200','#eef3f7','#7a8491','#ff66c4','#a855f7'];
    const $=id=>document.getElementById(id);
    const n=v=>fmt.format(Math.round(v||0));
    const pct=(a,b)=>b?Math.round((a/b)*1000)/10:0;
    const tokenOf=r=>(r.total_tokens||0)||(r.activity_proxy||0);
    function sourceTotals(){return DATA.summary.tools.reduce((a,t)=>{a.total+=t.total_tokens||0;a.input+=t.input_tokens||0;a.output+=t.output_tokens||0;a.cache+=(t.cache_creation_tokens||0)+(t.cache_read_tokens||0);a.sessions+=t.sessions||0;a.exact+=t.exact_token_sessions||0;a.projects+=t.projects||0;a.days=Math.max(a.days,t.active_days||0);return a},{total:0,input:0,output:0,cache:0,sessions:0,exact:0,projects:0,days:0})}
    function cards(){const s=sourceTotals();$('cards').innerHTML=[['Total tokens',n(s.total),`${pct(s.cache,s.total)}% cache`],['Input',n(s.input),'non-cache prompt'],['Cache',n(s.cache),'read + create'],['Output',n(s.output),'assistant tokens'],['Records',n(s.sessions),`${n(s.exact)} exact`],['Projects',n(new Set(DATA.summary.projects.map(p=>p.project).filter(p=>p!='(unknown)')).size),`${n(s.days)} active days`]].map(c=>`<div class="card"><div class="label">${c[0]}</div><div class="metric">${c[1]}</div><div class="sub">${c[2]}</div></div>`).join('')}
    function table(id,rows,cols,score='total_tokens'){const max=Math.max(...rows.map(r=>r[score]||0),1);$(id).innerHTML=`<table><thead><tr>${cols.map(c=>`<th>${c[0]}</th>`).join('')}<th></th></tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td class="${c[2]?'num':''}">${c[1](r)}</td>`).join('')}<td><div class="bar"><span style="width:${Math.max(2,(r[score]||0)/max*100)}%"></span></div></td></tr>`).join('')}</tbody></table>`}
    function stackBar(r){const total=r.total_tokens||1;const input=r.input_tokens||0,cache=(r.cache_creation_tokens||0)+(r.cache_read_tokens||0),out=r.output_tokens||0;return `<div class="stack" title="input ${n(input)} · cache ${n(cache)} · output ${n(out)}"><span style="width:${pct(input,total)}%"></span><span style="width:${pct(cache,total)}%"></span><span style="width:${pct(out,total)}%"></span></div>`}
    function line(id){const days=DATA.summary.days,tools=DATA.summary.tools.map(t=>t.tool),w=980,h=250,p=32;const max=Math.max(...days.flatMap(d=>tools.map(t=>d[t]||0)),1);const x=i=>p+(w-p*2)*(i/Math.max(days.length-1,1)),y=v=>h-p-(h-p*2)*(v/max);const paths=tools.map((t,i)=>`<path fill="none" stroke="${colors[i%colors.length]}" stroke-width="2.4" d="${days.map((d,j)=>(j?'L':'M')+x(j)+' '+y(d[t]||0)).join(' ')}"/>`).join('');$('trend').innerHTML=`<svg viewBox="0 0 ${w} ${h}"><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}" stroke="#27313b"/><line x1="${p}" y1="${p}" x2="${p}" y2="${h-p}" stroke="#27313b"/>${paths}<text x="${p}" y="18" fill="#91a0ad">${n(max)} peak day</text></svg><div class="legend">${tools.map((t,i)=>`<span class="chip"><span class="dot" style="background:${colors[i%colors.length]}"></span>${t}</span>`).join('')}</div>`}
    function heat(){const rows=DATA.summary.days,tools=DATA.summary.tools.map(t=>t.tool);const max=Math.max(...rows.map(r=>tools.reduce((a,t)=>a+(r[t]||0),0)),1);$('heat').innerHTML=rows.map(r=>{const v=tools.reduce((a,t)=>a+(r[t]||0),0);const a=.14+Math.min(1,v/max)*.86;const tip=[`${r.day}`,`Total: ${n(v)}`,...tools.map(t=>`${t}: ${n(r[t]||0)}`)].join('\\n');return `<div class="cell" title="${tip.replaceAll('"','&quot;')}" style="background:rgba(0,174,239,${a})"></div>`}).join('')}
    function quality(){const rows=DATA.summary.tools;$('quality').innerHTML=rows.map(t=>{const p=pct(t.exact_token_sessions,t.sessions);return `<div class="quality-row"><strong>${t.tool}</strong><div class="bar"><span style="width:${p}%"></span></div><span class="muted">${p}%</span></div>`}).join('')}
    function render(){cards();$('generated').textContent=new Date(DATA.summary.generated_at).toLocaleString();table('tools',DATA.summary.tools,[['Tool',r=>`<span class="name">${r.tool}</span>`],['Total',r=>r.exact_token_sessions?n(r.total_tokens):'<span class="muted">n/a</span>',1],['Input',r=>n(r.input_tokens),1],['Cache',r=>n((r.cache_creation_tokens||0)+(r.cache_read_tokens||0)),1],['Output',r=>n(r.output_tokens),1],['Mix',r=>stackBar(r)],['Exact',r=>`${n(r.exact_token_sessions)}/${n(r.sessions)}`,1],['Projects',r=>n(r.projects),1]],'total_tokens');
      table('projects',DATA.summary.projects.slice(0,40),[['Project',r=>`<div class="name">${r.project}</div><div class="path">${r.tool}${r.project_path?' · '+r.project_path:''}</div>`],['Tokens',r=>n(r.total_tokens),1],['Sessions',r=>n(r.sessions),1],['Activity',r=>n(r.activity_proxy),1],['Lines',r=>`${n(r.lines_added)} / ${n(r.lines_removed)}`,1]],'total_tokens');
      const exactSessions=DATA.sessions.filter(s=>s.exact_tokens&&s.total_tokens).sort((a,b)=>b.total_tokens-a.total_tokens).slice(0,35);table('sessions',exactSessions,[['Session',r=>`<div class="name">${r.tool}</div><div class="path">${r.project_label} · ${r.model||'model n/a'}</div>`],['Total',r=>n(r.total_tokens),1],['Input',r=>n(r.input_tokens),1],['Cache',r=>n((r.cache_creation_tokens||0)+(r.cache_read_tokens||0)),1],['Output',r=>n(r.output_tokens),1],['Date',r=>r.day||'',1]],'total_tokens');
      table('models',DATA.summary.models.slice(0,26),[['Tool',r=>r.tool],['Model',r=>`<span class="name">${r.model}</span>`],['Sessions',r=>n(r.sessions),1]],'sessions');line('trend');heat();quality();$('sources').innerHTML=DATA.summary.tools.map(t=>`<span class="chip"><strong>${t.tool}</strong> ${t.exact_token_sessions?`${n(t.total_tokens)} tokens`:'proxy only'}</span>`).join('')}
    render();
    """
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="application-name" content="{APP_NAME}"><meta name="apple-mobile-web-app-title" content="{APP_NAME}"><link rel="icon" type="image/svg+xml" href="{APP_ICON}"><link rel="manifest" href="{APP_MANIFEST}"><link rel="apple-touch-icon" href="{APP_ICON}"><title>{APP_TITLE}</title><style>{css}</style></head>
<body><header><div class="topbar"><h1>{APP_NAME}</h1><div class="stamp">Updated <span id="generated"></span></div></div></header>
<main>
<div id="cards" class="grid cards"></div>
<div class="grid two"><section><h2>Daily Volume</h2><div id="trend"></div></section><section><h2>Calendar Heat</h2><div id="heat" class="heat"></div><h3>Source Coverage</h3><div id="quality" class="quality"></div></section></div>
<section class="section-gap"><div class="toolbar"><h2 style="margin:0">Tool Mix</h2><div id="sources" class="legend"></div></div><div id="tools"></div></section>
<div class="grid two section-gap"><section><h2>Top Projects</h2><div id="projects" class="scroll"></div></section><section><h2>Largest Sessions</h2><div id="sessions" class="scroll"></div></section></div>
<div class="grid three section-gap"><section class="span2"><h2>Model Mix</h2><div id="models"></div></section><section><h2>Token Legend</h2><div class="legend"><span class="chip"><span class="dot" style="background:var(--d)"></span>Input</span><span class="chip"><span class="dot" style="background:var(--e)"></span>Cache</span><span class="chip"><span class="dot" style="background:var(--a)"></span>Output</span></div><p class="sub">Prompts are excluded. Project paths and aggregate usage only.</p></section></div>
</main><script>{js.replace('__DATA__', payload)}</script></body></html>"""
    path = ROOT / "usage-dashboard.html"
    path.write_text(body)
    (ROOT / "index.html").write_text(body)
    return path


def parse_pi():
    sessions = []
    session_dir = HOME / ".pi" / "agent" / "sessions"
    if not session_dir.exists():
        return sessions

    for project_dir in session_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                lines = jsonl_file.read_text(errors="ignore").splitlines()
            except Exception:
                continue

            session_info = {}
            model_info = {}
            assistant_messages = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                etype = entry.get("type", "")

                if etype == "session":
                    session_info = {
                        "id": entry.get("id", ""),
                        "cwd": entry.get("cwd", ""),
                        "timestamp": entry.get("timestamp", ""),
                    }
                elif etype == "model_change":
                    model_info = {
                        "provider": entry.get("provider", ""),
                        "modelId": entry.get("modelId", ""),
                    }
                elif etype == "message":
                    msg = entry.get("message", {})
                    if msg.get("role") == "assistant":
                        usage = msg.get("usage", {})
                        if usage:
                            assistant_messages.append({
                                "timestamp": entry.get("timestamp", ""),
                                "usage": usage,
                                "model": msg.get("model", ""),
                                "provider": msg.get("provider", ""),
                            })

            if not session_info:
                continue

            rec = empty_session("Pi", session_info["id"])

            # Project path from cwd
            cwd = session_info.get("cwd", "")
            if cwd:
                rec["project_path"] = clean_project(cwd)
                rec["project_label"] = project_label(cwd)

            # Start time from session header
            ts = session_info.get("timestamp", "")
            if ts:
                rec["start_time"] = ts
                rec["day"] = day_from_iso(ts)

            # Model from model_change or last assistant message
            model_str = ""
            if model_info:
                model_str = " ".join(x for x in [model_info.get("provider", ""), model_info.get("modelId", "")] if x)
            if not model_str and assistant_messages:
                last = assistant_messages[-1]
                model_str = " ".join(x for x in [last.get("provider", ""), last.get("model", "")] if x)
            rec["model"] = model_str

            # Aggregate usage across all assistant messages
            total_input = 0
            total_output = 0
            total_cache_read = 0
            total_cache_write = 0
            total_tokens = 0
            total_cost = 0.0
            has_usage = False

            for msg in assistant_messages:
                usage = msg.get("usage", {})
                if not usage:
                    continue
                has_usage = True
                total_input += int(usage.get("input") or 0)
                total_output += int(usage.get("output") or 0)
                total_cache_read += int(usage.get("cacheRead") or 0)
                total_cache_write += int(usage.get("cacheWrite") or 0)
                total_tokens += int(usage.get("totalTokens") or 0)
                cost_obj = usage.get("cost", {})
                if isinstance(cost_obj, dict):
                    total_cost += float(cost_obj.get("total") or 0)

            rec["input_tokens"] = total_input
            rec["output_tokens"] = total_output
            rec["cache_read_tokens"] = total_cache_read
            rec["cache_creation_tokens"] = total_cache_write
            rec["total_tokens"] = total_tokens
            rec["exact_tokens"] = has_usage
            rec["activity_proxy"] = total_tokens if has_usage else len(assistant_messages)
            rec["cost_proxy"] = total_cost
            rec["message_count"] = len(assistant_messages)
            rec["confidence"] = "high" if has_usage else "medium"
            rec["data_notes"] = (
                "Pi token usage from ~/.pi/agent/sessions JSONL; exact per-message usage aggregated."
                if has_usage
                else "Pi session activity from ~/.pi/agent/sessions JSONL; token telemetry not available."
            )

            sessions.append(rec)

    return sessions


def parse_hermes():
    db = HOME / ".hermes" / "state.db"
    sessions = []
    if not db.exists():
        return sessions
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(
            "select id, source, model, started_at, ended_at, message_count, tool_call_count, "
            "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, "
            "estimated_cost_usd, actual_cost_usd, title, api_call_count from sessions"
        ):
            sid = row["id"] or "hermes-unknown"
            rec = empty_session("Hermes", sid)
            rec["model"] = row["model"] or ""
            rec["start_time"] = iso_from_ms(int(row["started_at"] * 1000)) if row["started_at"] else ""
            rec["end_time"] = iso_from_ms(int(row["ended_at"] * 1000)) if row["ended_at"] else ""
            rec["day"] = day_from_iso(rec["start_time"])
            rec["input_tokens"] = int(row["input_tokens"] or 0)
            rec["output_tokens"] = int(row["output_tokens"] or 0)
            rec["cache_read_tokens"] = int(row["cache_read_tokens"] or 0)
            rec["cache_creation_tokens"] = int(row["cache_write_tokens"] or 0)
            rec["total_tokens"] = (
                rec["input_tokens"] + rec["output_tokens"]
                + rec["cache_read_tokens"] + rec["cache_creation_tokens"]
            )
            rec["exact_tokens"] = rec["total_tokens"] > 0
            rec["activity_proxy"] = rec["total_tokens"]
            rec["cost_proxy"] = float(row["actual_cost_usd"] or row["estimated_cost_usd"] or 0)
            rec["message_count"] = int(row["message_count"] or 0)
            rec["read_ops"] = int(row["tool_call_count"] or 0)
            rec["write_ops"] = int(row["tool_call_count"] or 0)
            rec["confidence"] = "high" if rec["exact_tokens"] else "medium"
            rec["data_notes"] = "Hermes session data from ~/.hermes/state.db SQLite."
            sessions.append(rec)
    finally:
        conn.close()
    return sessions


def main():
    sessions = []
    sessions.extend(parse_claude())
    sessions.extend(parse_codex())
    sessions.extend(parse_cursor())
    sessions.extend(parse_opencode())
    sessions.extend(parse_pi())
    sessions.extend(parse_hermes())
    sessions = merge_session_archive(sessions)
    summary = aggregate(sessions)
    (ROOT / "usage-summary.json").write_text(json.dumps({"summary": summary, "sessions": sessions}, indent=2))
    csv_path = write_csv(sessions)
    html_path = render_dashboard(summary, sessions)
    save_session_archive(sessions)
    print(f"Wrote {html_path}")
    print(f"Wrote {ROOT / 'usage-summary.json'}")
    print(f"Wrote {csv_path}")
    print(f"Sessions: {len(sessions)}")


if __name__ == "__main__":
    main()
