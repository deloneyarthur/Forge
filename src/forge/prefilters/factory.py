"""Build the production FeatureCache — real writer socket first, synthetic only when allowed.

WHY here: the constructor lived in ``cli/main.py`` beside the daemon loop; the
weekly campaign builds the same cache with ``require_real=True``, and the loop
is retired in the final state (plan 2026-09 §12.4). The 2026-05-28 RCA is the
reason the fallback is loud and refusable: a post-reboot silent fallback to the
synthetic cache rejected every config at ``permutation_test``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crucible_contracts import RegistrySnapshot


def build_feature_cache(
    registry: RegistrySnapshot,
    seed: int,
    *,
    require_real: bool = False,
    data_root: Path | None = None,
) -> object:
    """Construct the production FeatureCache; fall back to synthetic on failure.

    Tries ``crucible_contracts.FeatureCacheClient`` against the writer socket
    under ``data_root`` (default ``~/optbt_data``). When the socket is not
    reachable (no Crucible running, writer restarting, test environments) the
    behaviour depends on ``require_real``:

      - ``require_real=False`` (dev/test default): fall back to
        ``SyntheticFeatureCache`` so offline flows keep working — but warn
        LOUDLY, because synthetic returns are pure noise that make the whole
        pre-filter battery meaningless.
      - ``require_real=True`` (every production submission path): raise
        ``FeatureCacheUnavailableError`` rather than degrade silently, so the
        caller skips the run instead of filtering/submitting on noise.

    ``data_root`` is injectable so tests can point at a socket-free directory
    without depending on whether a live writer exists on the host.
    """
    import typer  # noqa: PLC0415 — the warning goes to the operator's terminal/journal, as before
    from crucible_contracts import FeatureCacheClient, FeatureCacheUnavailableError  # noqa: PLC0415

    from forge.prefilters import SyntheticFeatureCache  # noqa: PLC0415
    from forge.prefilters.crucible_feature_cache import CrucibleFeatureCache  # noqa: PLC0415

    root = data_root if data_root is not None else Path.home() / "optbt_data"
    socket_path = root / "db_writer.sock"
    authkey_path = root / "db_writer.authkey"
    db_path = root / "runs.duckdb"

    unavailable_reason: str | None = None
    if socket_path.exists() and authkey_path.exists():
        try:
            client = FeatureCacheClient(
                socket_path=socket_path,
                authkey_path=authkey_path,
                db_path=db_path,
            )
            cache = CrucibleFeatureCache(
                client,
                data_history_days=registry.data_history_days,
                data_start_date=registry.data_start_date,
            )
            # Probe — Crucible's writer may not yet support feature_batch requests.
            cache.probe()
            return cache
        except FeatureCacheUnavailableError as exc:
            unavailable_reason = str(exc)
    else:
        unavailable_reason = f"writer socket not found at {socket_path}"

    # Real cache unavailable. Hard rule: production never degrades silently.
    if require_real:
        raise FeatureCacheUnavailableError(
            f"{unavailable_reason}; refusing to run on the synthetic cache "
            "(--require-real-cache is set)."
        )
    typer.echo(
        f"warning: {unavailable_reason}; falling back to SyntheticFeatureCache "
        "— pre-filter results are NOT data-grounded.",
        err=True,
    )
    return SyntheticFeatureCache(
        root_seed=seed,
        data_history_days=registry.data_history_days,
        start_date=registry.data_start_date,
    )


__all__ = ["build_feature_cache"]
