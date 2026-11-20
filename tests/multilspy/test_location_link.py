"""Tests for LSP 3.17 LocationLink parsing in LanguageServer.request_definition."""

import pathlib
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from multilspy.language_server import LanguageServer
from multilspy.multilspy_logger import MultilspyLogger


class _StubLanguageServer(LanguageServer):
    def __init__(self, repo_root: pathlib.Path, definition_response):
        self.logger = MultilspyLogger()
        self.repository_root_path = str(repo_root)
        self.server_started = True
        self.request_timeout = 5.0
        self.server = SimpleNamespace(
            send=SimpleNamespace(definition=AsyncMock(return_value=definition_response))
        )

    @contextmanager
    def open_file(self, relative_file_path: str):
        yield SimpleNamespace()

    def check_process_health(self):
        return True


@pytest.mark.asyncio
async def test_location_link_without_origin_selection_range(tmp_path):
    """LSP 3.17 LocationLink.originSelectionRange is optional; omitting it must not assert."""
    target_file = tmp_path / "pkg" / "mod.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("def foo(): pass\n")

    sel_range = {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 7}}
    full_range = {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 15}}

    response = [
        {
            "targetUri": target_file.as_uri(),
            "targetRange": full_range,
            "targetSelectionRange": sel_range,
        }
    ]
    ls = _StubLanguageServer(tmp_path, response)
    locs = await ls.request_definition("pkg/mod.py", 0, 4)

    assert len(locs) == 1
    assert locs[0]["relativePath"] == "pkg/mod.py"
    assert locs[0]["range"] == sel_range


@pytest.mark.asyncio
async def test_location_link_fallback_to_target_range(tmp_path):
    """If targetSelectionRange is omitted, fall back to targetRange."""
    target_file = tmp_path / "main.rs"
    target_file.write_text("fn main() {}\n")

    full_range = {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 12}}
    response = [
        {
            "targetUri": target_file.as_uri(),
            "targetRange": full_range,
        }
    ]
    ls = _StubLanguageServer(tmp_path, response)
    locs = await ls.request_definition("main.rs", 0, 3)

    assert len(locs) == 1
    assert locs[0]["relativePath"] == "main.rs"
    assert locs[0]["range"] == full_range
