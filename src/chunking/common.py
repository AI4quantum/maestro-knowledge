"""Common chunking framework pieces: config and public API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ChunkingConfig:
    strategy: str = "Sentence"
    parameters: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = {}


# Public API: chunk_text delegates to registered strategies

# Strategy registry is populated by importing strategy modules which register
# themselves here by updating _STRATEGIES.
_STRATEGIES: dict[str, Callable[..., list[dict[str, object]]]] = {}


def register_strategy(name: str, func: Callable[..., list[dict[str, object]]]) -> None:
    _STRATEGIES[name] = func


def chunk_text(
    text: str, config: ChunkingConfig | None = None
) -> list[dict[str, object]]:
    """Chunk text according to the provided ChunkingConfig.

    Returns list of dicts containing keys: text, offset_start, offset_end, chunk_size, sequence, total
    """
    if config is None:
        config = ChunkingConfig()

    strategy = config.strategy or "None"
    parameters = config.parameters or {}

    func = _STRATEGIES.get(strategy)
    if func is None:
        raise ValueError(f"Unknown chunking strategy: {strategy}")

    # apply defaults when strategy is set and parameters missing
    params: dict[str, object]
    if strategy != "None":
        if strategy == "Semantic":
            params = {"chunk_size": 768, "overlap": 0}
        else:
            params = {"chunk_size": 512, "overlap": 0}
        params.update(parameters)
    else:
        params = {}

    return func(text, **params)
