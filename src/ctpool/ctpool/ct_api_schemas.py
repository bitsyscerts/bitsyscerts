"""Pydantic models for raw CT HTTP API responses.

These models validate data received from external CT log servers before it
enters the internal pipeline. All fields match the CT log v1 HTTP API spec
(RFC 6962, §4).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignedTreeHead(BaseModel):
    """Response model for GET /ct/v1/get-sth."""

    tree_size: int = Field(..., ge=0)
    timestamp: int = Field(..., ge=0)
    sha256_root_hash: str
    tree_head_signature: str


class CtLeafEntry(BaseModel):
    """A single entry as returned by GET /ct/v1/get-entries."""

    leaf_input: str  # base64-encoded MerkleTreeLeaf
    extra_data: str  # base64-encoded certificate chain


class CtEntriesResponse(BaseModel):
    """Response model for GET /ct/v1/get-entries."""

    entries: list[CtLeafEntry]


class CtLogTemporalInterval(BaseModel):
    """Optional temporal shard window for a CT log."""

    start_inclusive: str | None = None
    end_exclusive: str | None = None


class CtLogInfo(BaseModel):
    """Metadata for a single CT log as returned by the Chrome log list."""

    description: str
    log_id: str  # base64-encoded log ID
    key: str  # base64-encoded DER public key
    url: str
    mmd: int = Field(..., ge=0)  # maximum merge delay, seconds
    state: dict[str, object] | None = None
    temporal_interval: CtLogTemporalInterval | None = None


class CtLogOperator(BaseModel):
    """A CT log operator with one or more logs."""

    name: str
    email: list[str] = Field(default_factory=list)
    logs: list[CtLogInfo] = Field(default_factory=list)


class CtLogListResponse(BaseModel):
    """Chrome CT log list JSON (https://www.gstatic.com/ct/log_list/v3/log_list.json)."""

    version: str | None = None
    log_list_timestamp: str | None = None
    operators: list[CtLogOperator] = Field(default_factory=list)
