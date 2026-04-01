"""
Provides Elixir specific instantiation of the LanguageServer class using Expert. Contains various configurations and settings specific to Elixir.
"""

import asyncio
import json
import logging
import os
import pathlib
import stat
from contextlib import asynccontextmanager
from typing import AsyncIterator

from multilspy.multilspy_logger import MultilspyLogger
from multilspy.language_server import LanguageServer
from multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from multilspy.lsp_protocol_handler.lsp_types import InitializeParams
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_utils import FileUtils
from multilspy.multilspy_utils import PlatformUtils


class ExpertElixir(LanguageServer):
    """
    Provides Elixir specific instantiation of the LanguageServer class using Expert. Contains various configurations and settings specific to Elixir.
    """

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger, repository_root_path: str):
        """
        Creates an ExpertElixir instance. This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        expert_executable_path = self.setup_runtime_dependencies(logger, config)

        # Expert requires --stdio flag for LSP communication
        cmd = f"{expert_executable_path} --stdio"

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, cwd=repository_root_path),
            "elixir",
        )

    def setup_runtime_dependencies(self, logger: MultilspyLogger, config: MultilspyConfig) -> str:
        """
        Setup runtime dependencies for Expert Elixir Language Server.
        Expert ships self-contained binaries with the BEAM VM bundled via Burrito,
        so no Elixir or Erlang runtime is needed on the target machine.
        """
        platform_id = PlatformUtils.get_platform_id()

        with open(os.path.join(os.path.dirname(__file__), "runtime_dependencies.json"), "r") as f:
            d = json.load(f)
            del d["_description"]

        runtime_dependencies = d["runtimeDependencies"]
        runtime_dependencies = [
            dependency for dependency in runtime_dependencies if dependency["platformId"] == platform_id.value
        ]
        assert len(runtime_dependencies) == 1, \
            f"Expected exactly one runtime dependency for platform {platform_id.value}, found {len(runtime_dependencies)}"
        dependency = runtime_dependencies[0]

        expert_ls_dir = os.path.join(os.path.dirname(__file__), "static", "ExpertElixir")
        expert_executable_path = os.path.join(expert_ls_dir, dependency["binaryName"])

        if not os.path.exists(expert_executable_path):
            os.makedirs(expert_ls_dir, exist_ok=True)
            logger.log(f"Downloading Expert Elixir Language Server for {platform_id.value}...", logging.INFO)
            # Expert releases are raw binaries (not archives), so download directly
            FileUtils.download_file(logger, dependency["url"], expert_executable_path)

        assert os.path.exists(expert_executable_path), f"Expert binary not found at {expert_executable_path}"

        if not platform_id.value.startswith("win-"):
            os.chmod(expert_executable_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

        logger.log(f"Expert Elixir Language Server ready at {expert_executable_path}", logging.INFO)
        return expert_executable_path

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Expert Elixir Language Server.
        """
        with open(os.path.join(os.path.dirname(__file__), "initialize_params.json"), "r") as f:
            d = json.load(f)

        del d["_description"]

        assert d["processId"] == "os.getpid()"
        d["processId"] = os.getpid()

        assert d["rootPath"] == "$rootPath"
        d["rootPath"] = repository_absolute_path

        assert d["rootUri"] == "$rootUri"
        d["rootUri"] = pathlib.Path(repository_absolute_path).as_uri()

        assert d["workspaceFolders"][0]["uri"] == "$uri"
        d["workspaceFolders"][0]["uri"] = pathlib.Path(repository_absolute_path).as_uri()

        assert d["workspaceFolders"][0]["name"] == "$name"
        d["workspaceFolders"][0]["name"] = os.path.basename(repository_absolute_path)

        return d

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["ExpertElixir"]:
        """
        Starts the Expert Elixir Language Server, waits for the server to be ready and yields the LanguageServer instance.

        Usage:
        ```
        async with lsp.start_server():
            # LanguageServer has been initialized and ready to serve requests
            await lsp.request_definition(...)
            await lsp.request_references(...)
            # Shutdown the LanguageServer on exit from scope
        # LanguageServer has been shutdown
        ```
        """
        # Track $/progress tokens to detect when Expert finishes project compilation
        active_progress_tokens: set = set()
        indexing_complete = asyncio.Event()
        no_indexing_started = True

        async def execute_client_command_handler(params):
            return []

        async def do_nothing(params):
            return

        async def window_log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        async def handle_progress(params):
            nonlocal no_indexing_started
            token = params.get("token", "")
            value = params.get("value", {})
            kind = value.get("kind", "")

            if kind == "begin":
                no_indexing_started = False
                active_progress_tokens.add(token)
                self.logger.log(
                    f"LSP: $/progress begin: {value.get('title', '')} ({token})",
                    logging.INFO,
                )
            elif kind == "end":
                active_progress_tokens.discard(token)
                self.logger.log(
                    f"LSP: $/progress end: {value.get('message', '')} ({token})",
                    logging.INFO,
                )
                if not active_progress_tokens and not indexing_complete.is_set():
                    indexing_complete.set()

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", handle_progress)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        async with super().start_server():
            self.logger.log("Starting Expert Elixir server process", logging.INFO)
            await self.server.start()
            initialize_params = self._get_initialize_params(self.repository_root_path)

            self.logger.log(
                "Sending initialize request from LSP client to LSP server and awaiting response",
                logging.INFO,
            )
            init_response = await self.server.send.initialize(initialize_params)

            capabilities = init_response["capabilities"]
            assert "textDocumentSync" in capabilities, "Server must support textDocumentSync"
            assert "completionProvider" in capabilities, "Server must support code completion"
            assert "definitionProvider" in capabilities, "Server must support go to definition"
            assert "referencesProvider" in capabilities, "Server must support find references"
            assert "documentSymbolProvider" in capabilities, "Server must support document symbols"

            self.server.notify.initialized({})
            self.completions_available.set()

            # NOTE ON READINESS WAIT:
            # Expert compiles the project asynchronously after receiving the
            # initialized notification. We wait for compilation to complete
            # via $/progress tokens to ensure definition/references results
            # are complete. If no progress tokens arrive within 5 seconds,
            # the project may not need compilation (standalone files) and we
            # proceed immediately.
            self.logger.log(
                "Waiting for Expert to complete project compilation and indexing...",
                logging.INFO,
            )
            try:
                await asyncio.wait_for(indexing_complete.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                if no_indexing_started:
                    self.logger.log(
                        "No background indexing detected, proceeding immediately",
                        logging.INFO,
                    )
                else:
                    self.logger.log(
                        "Background compilation in progress, waiting for completion...",
                        logging.INFO,
                    )
                    await indexing_complete.wait()

            self.logger.log("Expert Elixir Language Server is ready", logging.INFO)

            yield self

            try:
                await self.server.shutdown()
            except Exception as e:
                self.logger.log(f"Error during Expert Elixir server shutdown: {str(e)}", logging.WARNING)
            finally:
                await self.server.stop()
