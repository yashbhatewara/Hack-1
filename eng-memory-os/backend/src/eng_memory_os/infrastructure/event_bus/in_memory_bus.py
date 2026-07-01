"""
In-memory async event bus for domain event pub/sub.

Provides loose coupling between bounded contexts via the
Event-Driven Architecture pattern. Handlers are registered
by event type and called asynchronously when events are published.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

import structlog

from eng_memory_os.domain.shared.events import DomainEvent

logger = structlog.get_logger(__name__)

# Type alias for async event handlers
EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class InMemoryEventBus:
    """In-process async event bus using Python's asyncio.

    Usage:
        bus = InMemoryEventBus()

        # Register handlers
        bus.subscribe(MemoryIngested, handle_memory_ingested)
        bus.subscribe(MemoryIngested, trigger_entity_extraction)

        # Publish events
        await bus.publish(MemoryIngested(memory_id="abc"))

        # Or publish multiple events at once
        await bus.publish_all(memory.collect_events())
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Register a handler for a specific event type.

        Multiple handlers can be registered for the same event type.
        They will all be called when an event of that type is published.
        """
        event_key = f"{event_type.__module__}.{event_type.__qualname__}"
        self._handlers[event_key].append(handler)
        logger.debug(
            "handler_subscribed",
            event_type=event_key,
            handler=getattr(handler, "__qualname__", handler.__class__.__name__),
        )

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that receives ALL domain events.

        Useful for logging, auditing, or event sourcing.
        """
        self._global_handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event to all registered handlers.

        Handlers are executed concurrently. If any handler fails,
        the error is logged but does not prevent other handlers from running.
        """
        event_key = event.event_type

        # Get specific handlers for this event type
        specific_handlers = self._handlers.get(event_key, [])
        all_handlers = specific_handlers + self._global_handlers

        if not all_handlers:
            logger.debug("event_no_handlers", event_type=event_key)
            return

        # Execute all handlers concurrently
        tasks = [
            self._safe_handle(handler, event)
            for handler in all_handlers
        ]
        await asyncio.gather(*tasks)

        logger.debug(
            "event_published",
            event_type=event_key,
            handler_count=len(all_handlers),
            event_id=str(event.event_id),
        )

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple events sequentially.

        Events are published in order (important for maintaining
        causal ordering in event-driven workflows).
        """
        for event in events:
            await self.publish(event)

    async def _safe_handle(
        self,
        handler: EventHandler,
        event: DomainEvent,
    ) -> None:
        """Execute a handler with error isolation."""
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "event_handler_failed",
                event_type=event.event_type,
                handler=getattr(handler, "__qualname__", handler.__class__.__name__),
                event_id=str(event.event_id),
            )

    def get_handler_count(self, event_type: type[DomainEvent] | None = None) -> int:
        """Get the number of registered handlers, optionally for a specific event type."""
        if event_type:
            key = f"{event_type.__module__}.{event_type.__qualname__}"
            return len(self._handlers.get(key, []))
        return sum(len(h) for h in self._handlers.values()) + len(self._global_handlers)

    def clear(self) -> None:
        """Remove all registered handlers. Primarily for testing."""
        self._handlers.clear()
        self._global_handlers.clear()
