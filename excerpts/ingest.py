# Excerpt from Salud (not the complete source).
"""Generic ingestion: keep every download verbatim, then derive the working tables.

Each source (smart ring API, phone app, weather API) follows the same two steps:
1. `save_import` stores the response untouched, with a checksum, in `raw_import`.
2. A source-specific parser upserts the derived rows. Every download replaces the
   days it covers, so re-running an import is idempotent and late corrections from
   the source simply overwrite the previous "latest version".
"""
import hashlib
import json


def save_import(c, source, content, endpoint=None, params=None, device_id=None,
                day_from=None, day_to=None, status="ok", notes=None):
    """Store a download exactly as received and return its id."""
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    raw = content.encode("utf-8")
    cur = c.execute(
        """INSERT INTO raw_import (source, endpoint, params, device_id, imported_at,
           day_from, day_to, sha256, bytes, content, status, notes)
           VALUES (?,?,?,?, datetime('now','localtime'), ?,?,?,?,?,?,?)""",
        (source, endpoint, json.dumps(params, ensure_ascii=False) if params else None, device_id,
         day_from, day_to, hashlib.sha256(raw).hexdigest(), len(raw), content, status, notes))
    return cur.lastrowid


def local_time(iso):
    """'2000-01-01T07:31:00+01:00' -> '2000-01-01 07:31:00' (the source already gives local time)."""
    return iso[:19].replace("T", " ")


def import_sleep(c, device_id, response, field_map, day_from, day_to):
    """Parse a sleep response into ring_sleep.

    `field_map` maps our column names to the source's field names; it is stored in
    device.config_json, so switching device or provider only changes configuration.
    """
    import_id = save_import(c, "ring_api", response, "sleep", {"from": day_from, "to": day_to},
                            device_id, day_from, day_to)
    # replace the days covered by this download
    c.execute("DELETE FROM ring_sleep WHERE device_id=? AND day BETWEEN ? AND ?",
              (device_id, day_from, day_to))
    for item in response.get("data", []):
        row = {col: item.get(src) for col, src in field_map.items()}
        row["start"] = local_time(item["bedtime_start"])
        row["end"] = local_time(item["bedtime_end"])
        cols = ["device_id", "import_id", "updated_at", *row]
        c.execute(
            f"INSERT OR REPLACE INTO ring_sleep ({', '.join(cols)}) "
            f"VALUES (?, ?, datetime('now','localtime'), {', '.join('?' * len(row))})",
            (device_id, import_id, *row.values()))
    return import_id
