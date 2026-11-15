# ODP HQ check events

The adapter implements the HQ `b76c3cb` diagnostic-drain contract. HQ supplies
`HQ_CHECK_EVENTS`, `HQ_CHECK_RUN`, and `HQ_CHECK_COMMIT`; the runner appends one
complete required suite and durable per-attempt logs. A missing prerequisite is
nonzero, never a skipped success. A permitted WinError 4551 retry has a non-final
first result and one immutable final result. Later independent checks still run.

## Entry points

- Build: `win32/orchestrator-build.ps1` always uses this repository's
  `run-checks.py` through `run-checks-profiled.py`. The legacy `-Checks` parameter
  is accepted for command compatibility but cannot select an older external runner.
- Check: `win32/compile-check-changed.ps1` wraps its existing compile command as
  the required aggregate `compile-check`, preserving its complete live output.
- Deploy: `win32/orchestrator-deploy-selected.ps1` wraps delivery as the required
  aggregate `deploy-delivery`. Partial delivery failures remain nonzero.
- Build reports individual static scripts, selected levels, build stage exits,
  prerequisites, deployment readiness and snapshot integrity. Check/Deploy do not
  invent individual results inside their opaque child commands.

The successful-deploy receipt selects Mossgate plus changed levels for publication
probes before Push. Delivery repeats probes against the actually delivered EXE.
Missing or invalid baseline evidence fails explicitly; no automatic full campaign.

## Resources and deployment

`odp-integration-resources.toml` is a project-configuration fragment, not an
application to a running HQ instance. Install matching versioned entry points and
resource footprints together. Updating a branch does not update external bundled
Deploy commands or existing plan worktrees. Those must explicitly select this
version before this adapter can be considered active. Unknown footprints remain
conservatively blocked by HQ.

Shared builds, game processes, load ports and check history are exclusive resources.
The runner verifies its commit, tracked sources and declared build-artifact hashes.
Windows job objects account for newly created child trees; timeouts reap only those
owned children. Existing processes are never terminated.

This implementation conservatively reports `shared_writes_finished` after all
owned processes finish, and the profiler has finished shared timing-history writes.
It does not claim safe early queue release during arbitrary scripts. Resource
reservations remain HQ's responsibility through worker completion.

## Focused verification

Run `python source/tests/check_hq_check_events.py` and
`python source/tests/check_test_runtime_profile.py` for local regressions.
`verify-hq-check-protocol.py --hq-root <HQ checkout>` needs the HQ Python environment
and verifies the actual protocol implementation against commit `b76c3cb`.
It uses disposable Git worktrees and a disposable database; it does not touch live
HQ configuration, plans or agents. It checks failure latching, retry completion,
restart persistence, artifact mismatch and retained resource/core reservations.
This controlled interoperability test is not a live production deployment.
