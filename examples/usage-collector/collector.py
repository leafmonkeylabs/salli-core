"""
A minimal receiver for `salli-server stats --send` (salli.usage/1): stores
each instance's weekly totals, one row per install id and week, in SQLite.
An example to run beside a pilot, not part of Salli: standard library only.

    python collector.py --db usage.sqlite --port 8085
    # instances: SALLI_USAGE_REPORT_URL=https://counts.example.org/v1/usage
    # summary:   GET /v1/usage  (totals by week, every install)

Put it behind TLS (a reverse proxy) and, if it is reachable from anywhere,
a shared secret in the proxy: the reports carry no one's data, but anyone
could post a number.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIELDS = ("active_members", "entries_imported", "reconciliations_completed")
SCHEMA = """create table if not exists usage (
    install_id text not null, week_ending text not null, salli_version text,
    active_members integer not null, entries_imported integer not null,
    reconciliations_completed integer not null,
    primary key (install_id, week_ending))"""


def make_handler(db: sqlite3.Connection) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _answer(self, status: int, body: object = None) -> None:
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/usage":
                return self._answer(404)
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 4096)
                report = json.loads(self.rfile.read(length))
                assert report["schema"] == "salli.usage/1"
                row = [str(report["install_id"])[:100], str(report["week_ending"])[:10]]
                row.append(str(report.get("salli_version", ""))[:40])
                row += [int(report[f]) for f in FIELDS]
            except (ValueError, KeyError, TypeError, AssertionError):
                return self._answer(400, {"error": "not a salli.usage/1 report"})
            # A second report for the same install and week replaces the first.
            db.execute("insert or replace into usage values (?, ?, ?, ?, ?, ?)", row)
            db.commit()
            self._answer(204)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/usage":
                return self._answer(404)
            rows = db.execute(
                "select week_ending, count(*), sum(active_members), sum(entries_imported),"
                " sum(reconciliations_completed) from usage group by week_ending"
                " order by week_ending"
            ).fetchall()
            keys = ("week_ending", "installs", *FIELDS)
            self._answer(200, [dict(zip(keys, r, strict=True)) for r in rows])

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", default="usage.sqlite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8085)
    args = parser.parse_args()
    db = sqlite3.connect(args.db, check_same_thread=False)
    db.execute(SCHEMA)
    ThreadingHTTPServer((args.host, args.port), make_handler(db)).serve_forever()


if __name__ == "__main__":
    main()
