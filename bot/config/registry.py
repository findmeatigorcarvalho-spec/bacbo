import copy
import fcntl
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Dict, FrozenSet, Iterable, Mapping, Set

logger = logging.getLogger(__name__)


class EngineGateRegistry:
    CURRENT_SCHEMA_VERSION = 2

    def __init__(self, file_path: str = "bot/data/disabled_gates.json"):
        self.file_path = file_path
        self.lock_file_path = file_path + ".lock"

        self._thread_lock = threading.RLock()
        self._runtime_disabled: FrozenSet[str] = frozenset()
        self._raw_config: Dict[str, Any] = {}
        self._dirty = False

        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        self.load()

    @staticmethod
    def _validate_gate_name(gate_name: str) -> str:
        if not isinstance(gate_name, str):
            raise TypeError("gate_name must be string")

        gate_name = gate_name.strip()
        if not gate_name:
            raise ValueError("gate_name cannot be empty")

        return gate_name

    @staticmethod
    def _normalize_gates(gates: Iterable[str]) -> Set[str]:
        return {EngineGateRegistry._validate_gate_name(gate) for gate in gates}

    def _publish_state(
        self,
        config: Dict[str, Any],
        runtime_disabled: FrozenSet[str],
        dirty: bool = False,
    ) -> None:
        self._raw_config = config
        self._runtime_disabled = runtime_disabled
        self._dirty = dirty

    def load(self) -> None:
        with self._thread_lock:
            self._load_unlocked()

    def _load_unlocked(self) -> None:
        if not os.path.exists(self.file_path):
            self._init_empty()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            logger.exception("Load failed; resetting.")
            self._init_empty()
            return

        if not isinstance(cfg, dict):
            self._init_empty()
            return

        version = cfg.get("schema_version", 1)

        if version >= 2:
            runtime = cfg.get("runtime_disabled", [])
            if not isinstance(runtime, list):
                runtime = []

            runtime_set = frozenset(
                self._validate_gate_name(gate)
                for gate in runtime
                if isinstance(gate, str) and gate.strip()
            )
        else:
            legacy_disabled = cfg.get("disabled", [])
            legacy_manual = cfg.get("manual_disabled", [])

            if not isinstance(legacy_disabled, list):
                legacy_disabled = []
            if not isinstance(legacy_manual, list):
                legacy_manual = []

            runtime_set = frozenset(
                {
                    self._validate_gate_name(item["gate"])
                    for item in legacy_disabled
                    if isinstance(item, dict)
                    and isinstance(item.get("gate"), str)
                    and item["gate"].strip()
                }
                | {
                    self._validate_gate_name(item["gate"])
                    for item in legacy_manual
                    if isinstance(item, dict)
                    and isinstance(item.get("gate"), str)
                    and item["gate"].strip()
                }
            )

        self._publish_state(cfg, runtime_set, dirty=False)

    def _init_empty(self) -> None:
        cfg = {
            "schema_version": self.CURRENT_SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "runtime_disabled": [],
            "retired_gates": [],
            "retest_candidates": [],
            "audit_log": [],
        }
        self._publish_state(cfg, frozenset(), dirty=False)

    def is_disabled(self, gate_name: str) -> bool:
        gate_name = self._validate_gate_name(gate_name)
        return gate_name in self._runtime_disabled

    def disabled_gates_snapshot(self) -> FrozenSet[str]:
        return self._runtime_disabled

    def config_snapshot(self) -> Mapping[str, Any]:
        with self._thread_lock:
            return MappingProxyType(copy.deepcopy(self._raw_config))

    def _transaction(self, fn: Callable[[], Any]) -> Any:
        lock_file = open(self.lock_file_path, "a", encoding="utf-8")

        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)

            with self._thread_lock:
                self._load_unlocked()
                before = self._runtime_disabled

                result = fn()

                if self._runtime_disabled != before or self._dirty:
                    self._save_atomic_unlocked()
                    self._dirty = False

                return result
        finally:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            finally:
                lock_file.close()

    def _disable_gate(self, gate: str) -> None:
        gate = self._validate_gate_name(gate)

        if gate in self._runtime_disabled:
            return

        new_disabled = set(self._runtime_disabled)
        new_disabled.add(gate)

        self._publish_state(self._raw_config, frozenset(new_disabled), dirty=True)

    def _enable_gate(self, gate: str) -> None:
        gate = self._validate_gate_name(gate)

        if gate not in self._runtime_disabled:
            return

        new_disabled = set(self._runtime_disabled)
        new_disabled.remove(gate)

        self._publish_state(self._raw_config, frozenset(new_disabled), dirty=True)

    def _bulk_disable(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized - self._runtime_disabled

        if not diff:
            return

        new_disabled = set(self._runtime_disabled)
        new_disabled.update(diff)

        self._publish_state(self._raw_config, frozenset(new_disabled), dirty=True)

    def _bulk_enable(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized & self._runtime_disabled

        if not diff:
            return

        new_disabled = set(self._runtime_disabled)
        new_disabled.difference_update(diff)

        self._publish_state(self._raw_config, frozenset(new_disabled), dirty=True)

    def disable_gate(self, gate: str) -> None:
        self._transaction(lambda: self._disable_gate(gate))

    def enable_gate(self, gate: str) -> None:
        self._transaction(lambda: self._enable_gate(gate))

    def bulk_disable(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_disable(gates))

    def bulk_enable(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_enable(gates))

    def _save_atomic_unlocked(self) -> None:
        doc = dict(self._raw_config)

        doc["schema_version"] = self.CURRENT_SCHEMA_VERSION
        doc["runtime_disabled"] = sorted(self._runtime_disabled)
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        doc.pop("disabled", None)
        doc.pop("manual_disabled", None)

        doc.setdefault("retired_gates", [])
        doc.setdefault("retest_candidates", [])
        doc.setdefault("audit_log", [])

        dir_name = os.path.dirname(self.file_path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix="gates_", suffix=".json", dir=dir_name)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.file_path)
            self._publish_state(doc, frozenset(doc["runtime_disabled"]), dirty=False)

        except Exception as e:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

            raise IOError(f"Atomic save failed: {e}") from e
