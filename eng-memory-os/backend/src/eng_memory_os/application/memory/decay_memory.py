"""
Decay Memory use case.

Periodically recalculates decay factors for active memories
using the exponential decay formula from the domain service.
"""

from __future__ import annotations

import structlog

from eng_memory_os.domain.memory.repositories import MemoryRepository
from eng_memory_os.domain.memory.services import MemoryDomainService
from eng_memory_os.infrastructure.event_bus.in_memory_bus import InMemoryEventBus

logger = structlog.get_logger(__name__)


class DecayMemoryUseCase:
    """Applies time-based decay to active memories in batches.

    Called periodically by the background worker. Memories that
    aren't accessed gradually lose relevance. When decay drops
    below the threshold, they transition to STALE status.
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        event_bus: InMemoryEventBus,
        batch_size: int = 500,
    ) -> None:
        self._memory_repo = memory_repo
        self._event_bus = event_bus
        self._batch_size = batch_size
        self._domain_service = MemoryDomainService()

    async def execute(self) -> dict[str, int]:
        """Execute decay recalculation on a batch of active memories.

        Returns a summary dict with counts of processed, decayed, and stale memories.
        """
        memories = await self._memory_repo.find_for_decay(batch_size=self._batch_size)

        processed = 0
        decayed = 0
        became_stale = 0

        for memory in memories:
            last_access = memory.last_accessed_at or memory.created_at
            hours_elapsed = self._domain_service.hours_since(last_access)

            old_decay = float(memory.decay_factor)
            new_decay_factor = self._domain_service.calculate_decay(
                current_decay=memory.decay_factor,
                hours_since_last_access=hours_elapsed,
            )

            # Only update if decay actually changed meaningfully
            if abs(float(new_decay_factor) - old_decay) > 0.001:
                memory.apply_decay()
                await self._memory_repo.save(memory)
                processed += 1
                decayed += 1

                # Collect and publish any domain events (e.g., MemoryDecayed)
                events = memory.collect_events()
                if events:
                    became_stale += 1
                    await self._event_bus.publish_all(events)

        summary = {
            "batch_size": len(memories),
            "processed": processed,
            "decayed": decayed,
            "became_stale": became_stale,
        }

        logger.info("decay_batch_completed", **summary)
        return summary
