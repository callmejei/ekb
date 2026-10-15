"""Object storage through fsspec. LAKE_URI decides the backend: s3:// (MinIO locally, S3 in prod),
file:// or hdfs://. Zones: staging (under review), raw (immutable, approved), processed, curated."""

from functools import lru_cache

import fsspec

from .config import get_settings


@lru_cache
def fs() -> fsspec.AbstractFileSystem:
    s = get_settings()
    protocol = s.lake_uri.split("://", 1)[0]
    if protocol == "s3":
        return fsspec.filesystem(
            "s3",
            key=s.s3_access_key,
            secret=s.s3_secret_key,
            client_kwargs={"endpoint_url": s.s3_endpoint_url} if s.s3_endpoint_url else {},
        )
    return fsspec.filesystem(protocol)


def uri(*parts: str) -> str:
    return "/".join([get_settings().lake_uri.rstrip("/"), *parts])


def write_bytes(path: str, data: bytes) -> None:
    with fs().open(path, "wb") as f:
        f.write(data)


def read_bytes(path: str) -> bytes:
    with fs().open(path, "rb") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    write_bytes(path, text.encode("utf-8"))


def copy(src: str, dst: str) -> None:
    write_bytes(dst, read_bytes(src))
