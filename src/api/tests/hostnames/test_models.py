"""Tests for hostnames/models.py — Pydantic validation rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from certsapi.hostnames.models import HostnameSearchParams, SortField


class TestHostnameSearchParams:
    def test_valid_minimal_params(self) -> None:
        params = HostnameSearchParams(q="example.com")
        assert params.q == "example.com"
        assert params.limit == 50
        assert params.recursive is False
        assert params.depth is None
        assert params.sort == SortField.not_before_desc
        assert params.cursor is None
        assert params.include_certs is False

    def test_limit_below_1_raises(self) -> None:
        with pytest.raises(ValidationError):
            HostnameSearchParams(q="x", limit=0)

    def test_limit_above_200_raises(self) -> None:
        with pytest.raises(ValidationError):
            HostnameSearchParams(q="x", limit=201)

    def test_limit_at_max_boundary_is_valid(self) -> None:
        params = HostnameSearchParams(q="x", limit=200)
        assert params.limit == 200

    def test_limit_at_min_boundary_is_valid(self) -> None:
        params = HostnameSearchParams(q="x", limit=1)
        assert params.limit == 1

    def test_depth_below_0_raises(self) -> None:
        with pytest.raises(ValidationError):
            HostnameSearchParams(q="x", depth=-1)

    def test_sort_accepts_all_four_values(self) -> None:
        for sort in SortField:
            params = HostnameSearchParams(q="x", sort=sort)
            assert params.sort == sort

    def test_depth_defaults_to_none(self) -> None:
        params = HostnameSearchParams(q="example.com")
        assert params.depth is None

    def test_include_certs_defaults_false(self) -> None:
        params = HostnameSearchParams(q="example.com")
        assert params.include_certs is False
