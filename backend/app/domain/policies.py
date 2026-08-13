"""Inventory replenishment policies.

Two families are supported in V1:

- ``RQPolicy(r, Q)`` - fixed order size ``Q`` triggered whenever the inventory
  position falls to or below ``r``.
- ``SsPolicy(s, S)`` - order-up-to ``S`` whenever inventory position falls to
  or below ``s``.

Both operate as vectorized "decide" functions that take the current
``inventory_position`` array (shape ``(n_sims,)``) and return a same-shape
integer order-quantity array.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class PolicyFamily(StrEnum):
    RQ = "r_Q"
    SS = "s_S"


class Policy(ABC):
    family: PolicyFamily

    @abstractmethod
    def order(self, inventory_position: np.ndarray) -> np.ndarray:
        """Return per-simulation order quantities (>= 0, integer)."""

    @abstractmethod
    def as_dict(self) -> dict[str, float]:
        """Return a JSON-serializable representation."""

    @abstractmethod
    def key(self) -> tuple[float, ...]:
        """Return a hashable key for de-duplication."""


@dataclass(frozen=True)
class RQPolicy(Policy):
    reorder_point: int
    order_quantity: int
    family: PolicyFamily = PolicyFamily.RQ

    def __post_init__(self) -> None:
        if self.reorder_point < 0:
            raise ValueError("reorder_point must be >= 0")
        if self.order_quantity <= 0:
            raise ValueError("order_quantity must be > 0")

    def order(self, inventory_position: np.ndarray) -> np.ndarray:
        trigger = inventory_position <= self.reorder_point
        return np.where(trigger, self.order_quantity, 0).astype(np.int64, copy=False)

    def as_dict(self) -> dict[str, float]:
        return {
            "policy_family": "r_Q",
            "reorder_point": int(self.reorder_point),
            "order_quantity": int(self.order_quantity),
        }

    def key(self) -> tuple[float, ...]:
        return (0.0, float(self.reorder_point), float(self.order_quantity))


@dataclass(frozen=True)
class SsPolicy(Policy):
    reorder_point: int
    order_up_to: int
    family: PolicyFamily = PolicyFamily.SS

    def __post_init__(self) -> None:
        if self.reorder_point < 0:
            raise ValueError("reorder_point must be >= 0")
        if self.order_up_to <= self.reorder_point:
            raise ValueError("order_up_to must be > reorder_point")

    def order(self, inventory_position: np.ndarray) -> np.ndarray:
        trigger = inventory_position <= self.reorder_point
        qty = np.where(trigger, self.order_up_to - inventory_position, 0)
        return np.maximum(qty, 0).astype(np.int64, copy=False)

    def as_dict(self) -> dict[str, float]:
        return {
            "policy_family": "s_S",
            "reorder_point": int(self.reorder_point),
            "order_up_to": int(self.order_up_to),
        }

    def key(self) -> tuple[float, ...]:
        return (1.0, float(self.reorder_point), float(self.order_up_to))
