"""
Background worker process.

Runs three scheduled jobs:
  1. Memory decay recalculation — every hour
  2. Knowledge graph optimization — every 6 hours
  3. Stale memory archival — every 24 hours

Uses asyncio with structured concurrency. Designed to run as a
separate Docker container or process alongside the API server.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from eng_memory_os.cmd.config import Settings

logger = structlog.get_logger(__name__)


class BackgroundWorker:
    """Orchestrates scheduled background tasks for the Memory OS."""

    def __init__(self) -> None:
        self._running = False
        self._settings = Settings()

        self._memory_repo = None
        self._graph_repo = None
        self._event_bus = None
        self._decay_uc = None
        self._optimize_uc = None

    async def start(self) -> None:
        logger.info("background_worker_starting")
        await self._initialize_services()
        self._running = True
        logger.info("background_worker_started")

        await asyncio.gather(
            self._decay_job_loop(),
            self._optimize_job_loop(),
            self._stale_archive_job_loop(),
            return_exceptions=True,
        )

    async def stop(self) -> None:
        self._running = False
        logger.info("background_worker_stopped")

    async def _initialize_services(self) -> None:
        from eng_memory_os.infrastructure.db.connection import DatabaseSessionManager
        from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus
        from eng_memory_os.infrastructure.cognee.cognee_adapter import CogneeGraphAdapter
        from eng_memory_os.application.memory.decay_memory import DecayMemoryUseCase
        from eng_memory_os.application.knowledge.optimize_graph import OptimizeGraphUseCase
        from eng_memory_os.presentation.dependencies import _MemoryRepoFactory

        self._event_bus = InMemoryEventBus()
        db_manager = DatabaseSessionManager(self._settings.database_url)
        await db_manager.initialize()
        self._memory_repo = _MemoryRepoFactory(db_manager)
        self._graph_repo = CogneeGraphAdapter(db_manager)
        await self._graph_repo.load_graph()

        self._decay_uc = DecayMemoryUseCase(
            memory_repo=self._memory_repo,
            event_bus=self._event_bus,
        )
        self._optimize_uc = OptimizeGraphUseCase(
            graph_repo=self._graph_repo,
            event_bus=self._event_bus,
        )

    async def _decay_job_loop(self) -> None:
        while self._running:
            try:
                logger.info("decay_job_started")
                result = await self._decay_uc.execute()
                logger.info(
                    "decay_job_completed",
                    processed=result.get("processed", 0),
                    staled=result.get("became_stale", 0),
                )
            except Exception:
                logger.exception("decay_job_failed")
            await asyncio.sleep(3600)

    async def _optimize_job_loop(self) -> None:
        await asyncio.sleep(300)  # 5 min warmup delay
        while self._running:
            try:
                logger.info("graph_optimization_started")
                result = await self._optimize_uc.execute()
                logger.info("graph_optimization_completed", **result)
            except Exception:
                logger.exception("graph_optimization_failed")
            await asyncio.sleep(6 * 3600)

    async def _stale_archive_job_loop(self) -> None:
        await asyncio.sleep(600)  # 10 min warmup delay
        while self._running:
            try:
                logger.info("stale_archive_started")
                count = await self._archive_very_stale_memories(decay_threshold=0.1)
                logger.info("stale_archive_completed", archived=count)
            except Exception:
                logger.exception("stale_archive_failed")
            await asyncio.sleep(24 * 3600)

    async def _archive_very_stale_memories(self, decay_threshold: float = 0.1) -> int:
        memories = await self._memory_repo.find_stale(
            decay_threshold=decay_threshold, limit=200
        )
        archived = 0
        for memory in memories:
            try:
                memory.archive()
                await self._memory_repo.save(memory)
                archived += 1
            except Exception:
                logger.exception("archive_memory_failed", memory_id=str(memory.id))
        return archived


async def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
    )

    worker = BackgroundWorker()
    loop = asyncio.get_running_loop()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=sig.name)
        asyncio.create_task(worker.stop())

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal, sig)
    except NotImplementedError:
        import sys
        if sys.platform == "win32":
            def _win_handle(sig_num, frame):
                logger.info("shutdown_signal_received", signal=signal.Signals(sig_num).name)
                loop.create_task(worker.stop())

            signal.signal(signal.SIGINT, _win_handle)
            signal.signal(signal.SIGTERM, _win_handle)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
