"""Tests for the (r, Q) and (s, S) policies."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.policies import RQPolicy, SsPolicy


def test_rq_policy_triggers_only_at_or_below_reorder_point() -> None:
    p = RQPolicy(reorder_point=5, order_quantity=10)
    ip = np.array([-1, 0, 5, 6, 100])
    qty = p.order(ip)
    assert qty.tolist() == [10, 10, 10, 0, 0]


def test_rq_policy_rejects_invalid_args() -> None:
    with pytest.raises(ValueError):
        RQPolicy(reorder_point=-1, order_quantity=5)
    with pytest.raises(ValueError):
        RQPolicy(reorder_point=5, order_quantity=0)


def test_ss_policy_orders_up_to_target() -> None:
    p = SsPolicy(reorder_point=5, order_up_to=20)
    ip = np.array([-3, 0, 5, 6, 25])
    qty = p.order(ip)
    assert qty.tolist() == [23, 20, 15, 0, 0]


def test_ss_policy_rejects_invalid_args() -> None:
    with pytest.raises(ValueError):
        SsPolicy(reorder_point=5, order_up_to=5)
    with pytest.raises(ValueError):
        SsPolicy(reorder_point=-1, order_up_to=5)


def test_as_dict_shape() -> None:
    assert RQPolicy(reorder_point=3, order_quantity=7).as_dict() == {
        "policy_family": "r_Q",
        "reorder_point": 3,
        "order_quantity": 7,
    }
    assert SsPolicy(reorder_point=3, order_up_to=10).as_dict() == {
        "policy_family": "s_S",
        "reorder_point": 3,
        "order_up_to": 10,
    }
