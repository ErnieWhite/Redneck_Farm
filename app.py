from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse


ALLOWED_CROPS = ("Corn", "Taters", "Okra", "Pumpkin")
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 '\-]{0,23}")
PLOT_COUNT = 6
MAX_LOG_ENTRIES = 12
STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class Plot:
    crop: str | None = None
    stage: int = 0
    tended_by: str = ""

    def to_dict(self, index: int) -> dict[str, Any]:
        stages = ("Fresh dirt", "Seeded", "Sprouting", "Ready to harvest")
        return {
            "index": index,
            "crop": self.crop,
            "stage": self.stage,
            "status": stages[self.stage] if self.crop else stages[0],
            "tended_by": self.tended_by,
        }


class FarmGame:
    def __init__(self, plot_count: int = PLOT_COUNT) -> None:
        self._lock = Lock()
        self._plots = [Plot() for _ in range(plot_count)]
        self._players: dict[str, dict[str, Any]] = {}
        self._activity_log = ["Welcome to the Holler Co-op. Grab a plot and get growin'."]

    def join_player(self, name: str) -> dict[str, Any]:
        clean_name = self._validate_name(name)
        with self._lock:
            self._players.setdefault(clean_name, {"name": clean_name, "harvests": 0})
            self._log(f"{clean_name} rolled up to the co-op.")
            return self._snapshot()

    def apply_action(self, player: str, action: str, plot_index: int, crop: str | None = None) -> dict[str, Any]:
        clean_name = self._validate_name(player)
        with self._lock:
            if clean_name not in self._players:
                raise ValueError("Player must join before taking actions.")
            if plot_index < 0 or plot_index >= len(self._plots):
                raise ValueError("That plot doesn't exist.")

            plot = self._plots[plot_index]
            if action == "plant":
                crop_name = self._validate_crop(crop)
                if plot.crop:
                    raise ValueError("That patch already has something planted.")
                plot.crop = crop_name
                plot.stage = 1
                plot.tended_by = clean_name
                self._log(f"{clean_name} planted {crop_name.lower()} in plot {plot_index + 1}.")
            elif action == "water":
                if not plot.crop:
                    raise ValueError("You can't water bare dirt.")
                if plot.stage >= 3:
                    raise ValueError("That crop is already ready to harvest.")
                plot.stage += 1
                plot.tended_by = clean_name
                self._log(f"{clean_name} watered the {plot.crop.lower()} in plot {plot_index + 1}.")
            elif action == "harvest":
                if not plot.crop or plot.stage < 3:
                    raise ValueError("That crop ain't ready yet.")
                harvested_crop = plot.crop
                self._players[clean_name]["harvests"] += 1
                self._plots[plot_index] = Plot()
                self._log(f"{clean_name} hauled in {harvested_crop.lower()} from plot {plot_index + 1}.")
            else:
                raise ValueError("Unknown action.")

            return self._snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        players = sorted(
            self._players.values(),
            key=lambda player: (-player["harvests"], player["name"].lower()),
        )
        return {
            "allowed_crops": list(ALLOWED_CROPS),
            "plots": [plot.to_dict(index) for index, plot in enumerate(self._plots)],
            "players": players,
            "activity_log": list(self._activity_log),
        }

    def _log(self, entry: str) -> None:
        self._activity_log.append(entry)
        self._activity_log = self._activity_log[-MAX_LOG_ENTRIES:]

    @staticmethod
    def _validate_name(name: str) -> str:
        clean_name = str(name or "").strip()
        if not NAME_PATTERN.fullmatch(clean_name):
            raise ValueError("Use 1-24 letters, numbers, spaces, apostrophes, or hyphens for player names.")
        return clean_name

    @staticmethod
    def _validate_crop(crop: str | None) -> str:
        if crop not in ALLOWED_CROPS:
            raise ValueError("Pick one of the listed crops.")
        return crop


GAME = FarmGame()


class FarmRequestHandler(BaseHTTPRequestHandler):
    server_version = "RedneckFarm/0.1"

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if route == "/state":
            self._send_json(HTTPStatus.OK, GAME.snapshot())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        payload = self._read_json()
        if payload is None:
            return

        try:
            if route == "/join":
                body = GAME.join_player(payload.get("name", ""))
            elif route == "/action":
                body = GAME.apply_action(
                    player=payload.get("player", ""),
                    action=payload.get("action", ""),
                    plot_index=int(payload.get("plot", -1)),
                    crop=payload.get("crop"),
                )
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        self._send_json(HTTPStatus.OK, body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            return json.loads(raw_body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Send valid JSON."})
            return None

    def _serve_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), FarmRequestHandler)
    print(f"Holler Co-op is open on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
