#!/usr/bin/env python3
"""Render a Markdown scorecard from an AI-visibility results.json file.

Usage:
    python3 scripts/scorecard.py results.json [previous_results.json] > scorecard.md

Standard library only. Contract: schema/results.schema.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
import re

ENGINE_ORDER = ["chatgpt", "gemini", "google_ai_mode", "perplexity"]


class ValidationError(ValueError):
    """Input violates the local results contract."""


def _check(value, schema: dict, path: str = "$", /) -> None:
    """Check the keywords used in our bundled schema, not arbitrary JSON Schema."""
    kinds = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: type(v) is int or (type(v) is float and v.is_integer()),
        "null": lambda v: v is None,
    }
    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else expected
        if not any(kinds[k](value) for k in allowed):
            raise ValidationError(f"{path}: expected {' or '.join(allowed)}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: expected one of {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: unexpected value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValidationError(f"{path}.{key}: required field is missing")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                _check(value[key], child, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"{path}: expected at least {schema['minItems']} item(s)")
        if "items" in schema:
            for index, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{path}: must not be empty")
        if schema.get("format") == "date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError
                date.fromisoformat(value)
            except ValueError:
                raise ValidationError(f"{path}: expected a valid YYYY-MM-DD date") from None
    if type(value) in (int, float) and "minimum" in schema and value < schema["minimum"]:
        raise ValidationError(f"{path}: must be at least {schema['minimum']}")
    if "if" in schema:
        try:
            _check(value, schema["if"], path)
        except ValidationError:
            branch = "else"
        else:
            branch = "then"
        _check(value, schema.get(branch, {}), path)


def validate(data: dict) -> None:
    """Validate shape plus unique question IDs, references, and observation pairs."""
    schema_path = Path(__file__).resolve().parents[1] / "schema" / "results.schema.json"
    with schema_path.open(encoding="utf-8") as f:
        _check(data, json.load(f))
    ids = set()
    for index, question in enumerate(data["questions"]):
        if question["id"] in ids:
            raise ValidationError(f"$.questions[{index}].id: duplicate question ID")
        ids.add(question["id"])
    pairs = set()
    for index, result in enumerate(data["results"]):
        if result["question_id"] not in ids:
            raise ValidationError(f"$.results[{index}].question_id: unknown question ID")
        pair = (result["engine"], result["question_id"])
        if pair in pairs:
            raise ValidationError(f"$.results[{index}]: duplicate engine/question_id pair")
        pairs.add(pair)


def _reject_constant(value: str):
    raise ValidationError("$: non-finite numbers are not valid JSON")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f, parse_constant=_reject_constant)
    validate(data)
    return data


def _engines(data: dict) -> list[str]:
    seen = {r["engine"] for r in data.get("results", [])}
    ordered = [e for e in ENGINE_ORDER if e in seen]
    return ordered + sorted(seen - set(ordered))


def _cell(r: dict | None) -> str:
    if r is None:
        return "–"
    if r.get("status") == "failed":
        return "FAILED"
    if r.get("mentioned"):
        return f"✅ #{r['rank']}" if r.get("rank") else "✅"
    return "❌"


def summarize(data: dict) -> dict:
    """Hit rates per engine, counting failed calls separately (never as misses)."""
    per_engine: dict[str, dict] = {}
    for e in _engines(data):
        rows = [r for r in data["results"] if r["engine"] == e]
        ok = [r for r in rows if r.get("status") != "failed"]
        hits = [r for r in ok if r.get("mentioned")]
        per_engine[e] = {
            "asked": len(rows),
            "failed": len(rows) - len(ok),
            "valid": len(ok),
            "mentioned": len(hits),
            "hit_rate": (len(hits) / len(ok)) if ok else None,
        }
    valid = sum(v["valid"] for v in per_engine.values())
    mentioned = sum(v["mentioned"] for v in per_engine.values())
    competitors = Counter(
        c for r in data["results"] if r.get("status") != "failed" for c in r.get("competitors", [])
    )
    sources = Counter(
        s for r in data["results"] if r.get("status") != "failed" for s in r.get("third_party_sources", [])
    )
    return {
        "per_engine": per_engine,
        "overall_hit_rate": (mentioned / valid) if valid else None,
        "competitors": competitors.most_common(),
        "third_party_sources": sources.most_common(),
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def diff(curr: dict, prev: dict) -> list[str]:
    def key(r):
        return (r["engine"], r["question_id"])

    old = {key(r): r for r in prev.get("results", []) if r.get("status") != "failed"}
    lines = []
    for r in curr.get("results", []):
        if r.get("status") == "failed" or key(r) not in old:
            continue
        o = old[key(r)]
        if bool(o.get("mentioned")) != bool(r.get("mentioned")):
            state = "now mentioned" if r.get("mentioned") else "no longer mentioned"
            lines.append(f"- {r['engine']} / {r['question_id']}: {state}")
        elif r.get("mentioned") and o.get("rank") != r.get("rank"):
            lines.append(f"- {r['engine']} / {r['question_id']}: rank {o.get('rank')} → {r.get('rank')}")
    old_comp = {c for r in old.values() for c in r.get("competitors", [])}
    new_comp = sorted(
        {c for r in curr.get("results", []) if r.get("status") != "failed" for c in r.get("competitors", [])}
        - old_comp
    )
    if new_comp:
        lines.append("- New competitors: " + ", ".join(new_comp))
    return lines or ["- No changes."]


def render(data: dict, prev: dict | None = None) -> str:
    validate(data)
    if prev is not None:
        validate(prev)
    s = summarize(data)
    engines = _engines(data)
    idx = {(r["engine"], r["question_id"]): r for r in data.get("results", [])}
    out = [f"# AI Visibility Scorecard — {data.get('brand', 'Unknown brand')}", ""]
    if data.get("date"):
        out += [f"Audit date: {data['date']}", ""]
    out += [f"**Overall hit rate (valid answers only): {_pct(s['overall_hit_rate'])}**", ""]

    out += ["## Engine × question", "", "| Question | " + " | ".join(engines) + " |",
            "|---|" + "---|" * len(engines)]
    for q in data.get("questions", []):
        label = f"{q['id']} ({q.get('type', 'intent')}): {q['text']}"
        out.append(f"| {label} | " + " | ".join(_cell(idx.get((e, q["id"]))) for e in engines) + " |")
    out.append("")

    out += ["## Hit rate by engine", "", "| Engine | Asked | Failed | Mentioned | Hit rate |", "|---|---|---|---|---|"]
    for e, v in s["per_engine"].items():
        out.append(f"| {e} | {v['asked']} | {v['failed']} | {v['mentioned']}/{v['valid']} | {_pct(v['hit_rate'])} |")
    out.append("")

    out += ["## Competitors named by AI engines", ""]
    out += [f"- {c} ({n})" for c, n in s["competitors"]] or ["- None recorded."]
    out += ["", "## Third-party sources cited", ""]
    out += [f"- {c} ({n})" for c, n in s["third_party_sources"]] or ["- None recorded."]

    if prev is not None:
        out += ["", "## Compared with last audit", ""] + diff(data, prev)
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        prev = load(argv[2]) if len(argv) == 3 else None
        report = render(load(argv[1]), prev)
    except ValidationError as exc:
        print(f"Invalid results: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON at line {exc.lineno}, column {exc.colno}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("Invalid JSON encoding: expected UTF-8.", file=sys.stderr)
        return 2
    except OSError:
        print("Cannot read input or bundled schema; check file access.", file=sys.stderr)
        return 2
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
