"""
This file contains tests for running the Expert Elixir Language Server.
"""

import pytest
from pathlib import PurePath

from multilspy import LanguageServer
from multilspy.multilspy_config import Language
from tests.test_utils import create_test_context

pytest_plugins = ("pytest_asyncio",)

@pytest.mark.asyncio
async def test_multilspy_elixir_document_symbols() -> None:
    params = {
        "code_language": Language.ELIXIR,
        "repo_url": "https://github.com/ueberauth/guardian/",
        "repo_commit": "09be7ddf773119104284a8812db615b4ff6c7dae"
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        test_file = str(PurePath("lib/guardian.ex"))

        async with lsp.start_server():
            result = await lsp.request_document_symbols(test_file)

            symbols = result[0]
            assert len(symbols) > 0, "Should find document symbols"

            # Verify the Guardian module symbol
            guardian_symbol = next((s for s in symbols if s["name"] == "Guardian"), None)
            assert guardian_symbol is not None, "Guardian module should be present"

@pytest.mark.asyncio
async def test_multilspy_elixir_definition() -> None:
    params = {
        "code_language": Language.ELIXIR,
        "repo_url": "https://github.com/ueberauth/guardian/",
        "repo_commit": "09be7ddf773119104284a8812db615b4ff6c7dae"
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        test_file = str(PurePath("lib/guardian.ex"))

        async with lsp.start_server():
            definition_result = await lsp.request_definition(test_file, 1, 10)

            assert definition_result is not None, "Definition result should not be None"

@pytest.mark.asyncio
async def test_multilspy_elixir_references() -> None:
    params = {
        "code_language": Language.ELIXIR,
        "repo_url": "https://github.com/ueberauth/guardian/",
        "repo_commit": "09be7ddf773119104284a8812db615b4ff6c7dae"
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        test_file = str(PurePath("lib/guardian.ex"))

        async with lsp.start_server():
            references = await lsp.request_references(test_file, 0, 10)

            assert references is not None, "References should not be None"
            assert len(references) >= 1, "Should find at least one reference to Guardian"

@pytest.mark.asyncio
async def test_multilspy_elixir_completions() -> None:
    params = {
        "code_language": Language.ELIXIR,
        "repo_url": "https://github.com/ueberauth/guardian/",
        "repo_commit": "09be7ddf773119104284a8812db615b4ff6c7dae"
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        test_file = str(PurePath("lib/guardian.ex"))

        async with lsp.start_server():
            completions = await lsp.request_completions(test_file, 1, 10)

            assert completions is not None, "Completions result should not be None"
            assert len(completions) > 0, "Should find at least one completion item"

            for item in completions:
                assert "completionText" in item, "Completion item should have completionText"
                assert "kind" in item, "Completion item should have kind"

@pytest.mark.asyncio
async def test_multilspy_elixir_hover() -> None:
    params = {
        "code_language": Language.ELIXIR,
        "repo_url": "https://github.com/ueberauth/guardian/",
        "repo_commit": "09be7ddf773119104284a8812db615b4ff6c7dae"
    }
    with create_test_context(params) as context:
        lsp = LanguageServer.create(context.config, context.logger, context.source_directory)
        test_file = str(PurePath("lib/guardian.ex"))

        async with lsp.start_server():
            hover_result = await lsp.request_hover(test_file, 0, 10)

            assert hover_result is not None, "Hover result should not be None"
            assert "contents" in hover_result, "Hover result should contain contents"
