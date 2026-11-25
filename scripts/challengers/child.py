"""The challenger's own process: freeze checked first, then built, then closed off, then served.

Freeze W's rule (``FREEZE-W.md``, "Rules from here"): every comparison runs the challenger in a
process of its own, apart from the harness that measures it, imports
``synapse_kernel.release.integrity`` before any challenger code, and asserts the freeze. This module
is that process's entry point, in this order:

1. ``integrity`` is imported before anything of SYNAPSE (the first import below);
2. the world, the incumbent's tables and the component's parameters are loaded, and the freeze is
   asserted against them (files, bindings, world, tables);
3. the component is built by :func:`synapse_kernel.challengers.registry.build`, from those inputs
   only, never from a cell;
4. the process closes itself off with an audit hook (:func:`close_off`): no file is opened but the
   frozen files, no file written, no socket, no subprocess, no garbage-collector walk, no frame
   inspection, no new import. ``integrity`` imports the world's simulator into this process, so the
   hook and the rules on challenger code (``tests/kernel/challengers/test_rules.py``), not the
   process boundary alone, keep it out of reach;
5. it serves: ``("start", replicates)`` and ``("decide", observation)`` from the harness, orders
   back; no scenario ever exists here, because the engine runs in the harness's process;
6. on ``("stop",)`` it asserts the freeze again and reports.

What it receives before its first observation (the spawn arguments, the environment, the handshake)
is the same whatever the cell, and it reports a digest of all three so the harness can prove it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import synapse_kernel.release.integrity as integrity  # first: freeze W's rule

if TYPE_CHECKING:
    from multiprocessing.connection import Connection

ROOT = Path(__file__).resolve().parents[2]
#: The audit events a challenger's process refuses once it is serving.
REFUSED_EVENTS = frozenset(
    {
        "import",
        "gc.get_objects",
        "gc.get_referrers",
        "gc.get_referents",
        "sys._getframe",
        "sys._current_frames",
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.spawn",
        "os.posix_spawn",
        "os.startfile",
        "os.fork",
        "os.chdir",
        "os.remove",
        "os.rename",
        "os.mkdir",
        "ctypes.dlopen",
        "ctypes.dlsym",
        "socket.__new__",
        "socket.connect",
        "socket.bind",
        "shutil.rmtree",
        "code.__new__",
        "compile",
        "exec",
    }
)


def load(world_label: str) -> tuple[Any, dict[str, Any], list[Path]]:
    """The world and the incumbent's tables for ``world_label``, checked, and the files they are.

    ``"W"`` is freeze W's world (primary); ``"W-d1"`` is deviation 1's (secondary), checked against
    ``SHA256SUMS-D1`` by :mod:`synapse_kernel.deviation1` as well as freeze W's own checks.

    Raises:
        ValueError: An unknown world.
    """
    from synapse_kernel.release.incumbent import INCUMBENT_TABLES, load_incumbent_tables
    from synapse_kernel.release.world import RELEASE_WORLD, load_release_world

    files = [integrity.SUMS, *[ROOT / name for name in integrity.read_sums()]]
    if world_label == "W":
        world = load_release_world(RELEASE_WORLD)
        tables = load_incumbent_tables(INCUMBENT_TABLES)
    elif world_label == "W-d1":
        from synapse_kernel import deviation1

        world, tables = deviation1.load(ROOT)
        files += [deviation1.SUMS, *[ROOT / name for name in integrity.read_sums(deviation1.SUMS)]]
    else:
        raise ValueError(f"unknown world {world_label!r}")
    check(world_label, world, tables)
    return world, tables, files


def check(world_label: str, world: Any, tables: dict[str, Any]) -> None:
    """Refuse unless ``world`` and ``tables`` are the frozen ones for ``world_label``.

    Raises:
        synapse_kernel.release.integrity.FrozenKernelError: Either differs from its freeze.
    """
    if world_label == "W":
        integrity.assert_world_frozen(world)
        integrity.assert_tables_frozen(tables)
    else:
        from synapse_kernel import deviation1

        deviation1.assert_world(world)
        deviation1.assert_tables(tables)


def close_off(allowed_files: list[Path]) -> None:
    """Install an audit hook that refuses everything a decision has no business doing."""
    allowed = {os.path.normcase(str(p.resolve())) for p in allowed_files}

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event in REFUSED_EVENTS:
            raise PermissionError(f"refused in a challenger's process: {event}")
        if event == "open":
            path, mode = args[0], args[1] if len(args) > 1 else "r"
            if isinstance(path, int):
                return  # an already-open descriptor (the pipe), not a file by name
            name = os.path.normcase(str(Path(os.fsdecode(path)).resolve()))
            writing = isinstance(mode, str) and any(c in mode for c in "wax+")
            if writing or name not in allowed:
                raise PermissionError(f"refused in a challenger's process: open {path!r}")

    sys.addaudithook(hook)


def handshake_digest(spec: bytes) -> dict[str, str]:
    """What this process received before its first observation, as digests."""
    environment = json.dumps(sorted(os.environ.items()), separators=(",", ":"))
    return {
        "spec": hashlib.sha256(spec).hexdigest(),
        "environment": hashlib.sha256(environment.encode("utf-8")).hexdigest(),
        "argv": hashlib.sha256(json.dumps(sys.argv[1:]).encode("utf-8")).hexdigest(),
        "workdir_empty": str(not any(Path.cwd().iterdir())),
        "pid": str(os.getpid()),  # the child's own, not something it was given
    }


def serve(conn: Connection, spec: bytes) -> None:
    """The child's main: build, close off, answer the harness until it says stop."""
    request = json.loads(spec)
    workdir = tempfile.mkdtemp(prefix="challenger-")
    os.chdir(workdir)
    world, tables, files = load(request["world"])
    params: dict[str, Any] = {}
    if request.get("params"):
        params_path = ROOT / request["params"]
        params = json.loads(params_path.read_text(encoding="utf-8"))
        files.append(params_path)
    integrity.assert_frozen()
    from synapse_kernel.challengers.registry import build
    from synapse_kernel.release.observation import StoreObservation

    policy = build(request["component"], world, tables, params)
    info = handshake_digest(spec)
    close_off(files)
    conn.send(("ready", info))
    while True:
        message = conn.recv()
        if message[0] == "start":
            policy.start(int(message[1]))
            conn.send(("ok",))
        elif message[0] == "decide":
            conn.send(("orders", policy.decide(StoreObservation(**message[1]))))
        elif message[0] == "report":
            # A component's own summary (e.g. the largest evidence a detector saw), never a file.
            report = getattr(policy, "report", None)
            conn.send(("report", report() if callable(report) else {}))
        elif message[0] == "stop":
            break
    integrity.assert_frozen()
    check(request["world"], world, tables)
    conn.send(("done", True))
