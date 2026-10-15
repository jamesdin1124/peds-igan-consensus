"""Build SQL that loads the v2 core recommendations into the Supabase `recs` table.

Usage:
    python3 build_load_sql.py <recs_core_seed.json> <out_dir> [tian_notes.json]

- Adds a KDIGO-style grade derived from COR/LOE (rule below).
- Appends Dr. Tian's crosswalk note to the "待討論" line when a notes file is given.
- Writes one SQL file per batch (<= 12 rows) so each execute_sql call stays small.
"""
import json
import sys
from pathlib import Path

LOE_TO_KDIGO = {"A": "A", "B-R": "B", "B-NR": "C", "C-LD": "D"}


def kdigo(cor: str, loe: str) -> str:
    """COR/LOE -> KDIGO grade. C-EO maps to an ungraded Practice Point (PP)."""
    if loe == "C-EO" or loe not in LOE_TO_KDIGO:
        return "PP"
    q = LOE_TO_KDIGO[loe]
    if cor == "I":
        return "1" + q
    if cor in ("IIa", "IIb"):
        return "2" + q
    # Direction (recommend for / against) lives in the statement and the site's direction tag, not in the grade.
    if cor == "III-H":
        return "1" + q
    if cor == "III-NB":
        return ("1" if loe in ("A", "B-R") else "2") + q
    return ""


def rec_id(code: str) -> str:
    return "c" + "".join(ch if ch.isalnum() else "_" for ch in code)


def main() -> None:
    seed = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    notes = {}
    if len(sys.argv) > 3:
        notes = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")).get("notes", {})

    rows = []
    for r in seed:
        rationale = r.get("rationale", "")
        note = notes.get(r["code"])
        if note:
            rationale = rationale.rstrip() + "\n田祐霖醫師彙整表對照：" + note
        rows.append({
            "id": rec_id(r["code"]),
            "grp": r["group"],
            "ord": int(r.get("order", 1)),
            "code": r["code"],
            "topic": r.get("topic", ""),
            "text": r["text"],
            "text_en": r.get("textEn", ""),
            "cor": r.get("cor"),
            "loe": r.get("loe"),
            "kdigo": kdigo(r.get("cor", ""), r.get("loe", "")),
            "taiwan": r.get("taiwan", ""),
            "rationale": rationale,
            "refs": r.get("refs", []),
            "details": r.get("details", []),
            "src": r.get("from", []),
            "status": r.get("status", "voting"),
        })

    ids = [x["id"] for x in rows]
    assert len(ids) == len(set(ids)), "duplicate ids"
    cols = "id text, grp text, ord int, code text, topic text, text text, text_en text, cor text, loe text, kdigo text, taiwan text, rationale text, refs jsonb, details jsonb, src jsonb, status text"
    names = "id, grp, ord, code, topic, text, text_en, cor, loe, kdigo, taiwan, rationale, refs, details, src, status"
    for i in range(0, len(rows), 12):
        payload = json.dumps(rows[i:i + 12], ensure_ascii=False)
        assert "$recs$" not in payload
        sql = (f"insert into public.recs ({names})\n"
               f"select {names} from jsonb_to_recordset($recs${payload}$recs$::jsonb) as x({cols})\n"
               f"on conflict (id) do update set grp=excluded.grp, ord=excluded.ord, code=excluded.code, topic=excluded.topic, text=excluded.text, "
               f"text_en=excluded.text_en, cor=excluded.cor, loe=excluded.loe, kdigo=excluded.kdigo, taiwan=excluded.taiwan, rationale=excluded.rationale, "
               f"refs=excluded.refs, details=excluded.details, src=excluded.src, status=excluded.status, updated_at=now();\n")
        (out / f"load_{i // 12:02d}.sql").write_text(sql, encoding="utf-8")
    (out / "kdigo_table.json").write_text(json.dumps([{"code": x["code"], "cor": x["cor"], "loe": x["loe"], "kdigo": x["kdigo"]} for x in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} rows -> {len(range(0, len(rows), 12))} sql files in {out}")


if __name__ == "__main__":
    main()
