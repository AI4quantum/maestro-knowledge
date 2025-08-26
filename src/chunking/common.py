"""Common chunking framework pieces: config and public API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ChunkingConfig:
    strategy: str = "None"
    parameters: Dict[str, object] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


# Public API: chunk_text delegates to registered strategies
from typing import Callable

# Strategy registry is populated by importing strategy modules which register
# themselves here by updating _STRATEGIES.
_STRATEGIES: Dict[str, Callable[..., List[Dict[str, object]]]] = {}


def register_strategy(name: str, func: Callable[..., List[Dict[str, object]]]):
    _STRATEGIES[name] = func


def chunk_text(
    text: str, config: Optional[ChunkingConfig] = None
) -> List[Dict[str, object]]:
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
    if strategy != "None":
        params = {"chunk_size": 1000, "overlap": 0}
        params.update(parameters)
    else:
        params = {}

    return func(text, **params)
