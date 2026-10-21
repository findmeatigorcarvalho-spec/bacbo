import copy
import fcntl
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class EngineGateRegistry:
    CURRENT_SCHEMA_VERSION = 2
    DEFAULT_MAX_AUDIT_ENTRIES = 1000

    # Lifecycle actions recorded in the audit log. Routine runtime enable/disable
    # toggling is intentionally NOT audited; only durable lifecycle decisions are.
    ACTION_RETIRE = "retire"
    ACTION_UNRETIRE = "unretire"
    ACTION_MARK_RETEST = "mark_retest_candidate"
    ACTION_CLEAR_RETEST = "clear_retest_candidate"

    def __init__(
        self,
        file_path: str = "bot/data/disabled_gates.json",
        max_audit_entries: int = DEFAULT_MAX_AUDIT_ENTRIES,
    ):
        self.file_path = file_path
        self.lock_file_path = file_path + ".lock"
        self.max_audit_entries = max(0, int(max_audit_entries))

        self._thread_lock = threading.RLock()
        self._runtime_disabled: FrozenSet[str] = frozenset()
        self._retired_gates: FrozenSet[str] = frozenset()
        self._retest_candidates: FrozenSet[str] = frozenset()
        self._audit_log: List[Dict[str, Any]] = []
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

    @staticmethod
    def _coerce_gate_list(value: Any) -> FrozenSet[str]:
        if not isinstance(value, list):
            return frozenset()
        return frozenset(
            EngineGateRegistry._validate_gate_name(gate)
            for gate in value
            if isinstance(gate, str) and gate.strip()
        )

    def _publish_state(
        self,
        config: Dict[str, Any],
        runtime_disabled: FrozenSet[str],
        retired_gates: FrozenSet[str],
        retest_candidates: FrozenSet[str],
        audit_log: List[Dict[str, Any]],
        dirty: bool = False,
    ) -> None:
        self._raw_config = config
        self._runtime_disabled = runtime_disabled
        self._retired_gates = retired_gates
        self._retest_candidates = retest_candidates
        self._audit_log = audit_log
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

        retired = self._coerce_gate_list(cfg.get("retired_gates", []))
        retest = self._coerce_gate_list(cfg.get("retest_candidates", []))

        raw_audit = cfg.get("audit_log", [])
        audit = [entry for entry in raw_audit if isinstance(entry, dict)] if isinstance(raw_audit, list) else []

        self._publish_state(cfg, runtime_set, retired, retest, audit, dirty=False)

    def _init_empty(self) -> None:
        cfg = {
            "schema_version": self.CURRENT_SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "runtime_disabled": [],
            "retired_gates": [],
            "retest_candidates": [],
            "audit_log": [],
        }
        self._publish_state(cfg, frozenset(), frozenset(), frozenset(), [], dirty=False)

    def is_disabled(self, gate_name: str) -> bool:
        gate_name = self._validate_gate_name(gate_name)
        return gate_name in self._runtime_disabled

    def is_retired(self, gate_name: str) -> bool:
        gate_name = self._validate_gate_name(gate_name)
        return gate_name in self._retired_gates

    def is_retest_candidate(self, gate_name: str) -> bool:
        gate_name = self._validate_gate_name(gate_name)
        return gate_name in self._retest_candidates

    def disabled_gates_snapshot(self) -> FrozenSet[str]:
        return self._runtime_disabled

    def retired_gates_snapshot(self) -> FrozenSet[str]:
        return self._retired_gates

    def retest_candidates_snapshot(self) -> FrozenSet[str]:
        return self._retest_candidates

    def audit_log_snapshot(self) -> Tuple[Mapping[str, Any], ...]:
        with self._thread_lock:
            return tuple(MappingProxyType(copy.deepcopy(entry)) for entry in self._audit_log)

    def config_snapshot(self) -> Mapping[str, Any]:
        with self._thread_lock:
            return MappingProxyType(copy.deepcopy(self._raw_config))

    def _transaction(self, fn: Callable[[], Any]) -> Any:
        lock_file = open(self.lock_file_path, "a", encoding="utf-8")

        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)

            with self._thread_lock:
                self._load_unlocked()

                result = fn()

                if self._dirty:
                    self._save_atomic_unlocked()
                    self._dirty = False

                return result
        finally:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            finally:
                lock_file.close()

    def _record_audit(self, action: str, gates: Iterable[str]) -> None:
        gates = sorted(gates)
        if not gates:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "gates": gates,
        }
        self._audit_log = self._audit_log + [entry]
        self._dirty = True

    # ── Runtime enable/disable (routine, not audited) ────────────────────────
    def _disable_gate(self, gate: str) -> None:
        gate = self._validate_gate_name(gate)

        if gate in self._runtime_disabled:
            return

        self._runtime_disabled = frozenset(self._runtime_disabled | {gate})
        self._dirty = True

    def _enable_gate(self, gate: str) -> None:
        gate = self._validate_gate_name(gate)

        if gate not in self._runtime_disabled:
            return

        self._runtime_disabled = frozenset(self._runtime_disabled - {gate})
        self._dirty = True

    def _bulk_disable(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized - self._runtime_disabled

        if not diff:
            return

        self._runtime_disabled = frozenset(self._runtime_disabled | diff)
        self._dirty = True

    def _bulk_enable(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized & self._runtime_disabled

        if not diff:
            return

        self._runtime_disabled = frozenset(self._runtime_disabled - diff)
        self._dirty = True

    # ── Lifecycle: retire / unretire (durable, audited) ──────────────────────
    def _bulk_retire(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        newly_retired = normalized - self._retired_gates

        if not newly_retired:
            return

        self._retired_gates = frozenset(self._retired_gates | newly_retired)
        # Retiring a gate removes it from active rotation, so it is also disabled.
        self._runtime_disabled = frozenset(self._runtime_disabled | newly_retired)
        # A retired gate is no longer a candidate for re-testing.
        self._retest_candidates = frozenset(self._retest_candidates - newly_retired)
        self._record_audit(self.ACTION_RETIRE, newly_retired)

    def _bulk_unretire(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized & self._retired_gates

        if not diff:
            return

        self._retired_gates = frozenset(self._retired_gates - diff)
        self._record_audit(self.ACTION_UNRETIRE, diff)

    # ── Lifecycle: retest candidates (durable, audited) ──────────────────────
    def _bulk_mark_retest(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        newly = normalized - self._retest_candidates

        if not newly:
            return

        self._retest_candidates = frozenset(self._retest_candidates | newly)
        # Flagging a gate for re-test brings it back into consideration, so it is
        # no longer retired.
        self._retired_gates = frozenset(self._retired_gates - newly)
        self._record_audit(self.ACTION_MARK_RETEST, newly)

    def _bulk_clear_retest(self, gates: Iterable[str]) -> None:
        normalized = self._normalize_gates(gates)
        diff = normalized & self._retest_candidates

        if not diff:
            return

        self._retest_candidates = frozenset(self._retest_candidates - diff)
        self._record_audit(self.ACTION_CLEAR_RETEST, diff)

    # ── Public API ───────────────────────────────────────────────────────────
    def disable_gate(self, gate: str) -> None:
        self._transaction(lambda: self._disable_gate(gate))

    def enable_gate(self, gate: str) -> None:
        self._transaction(lambda: self._enable_gate(gate))

    def bulk_disable(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_disable(gates))

    def bulk_enable(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_enable(gates))

    def retire_gate(self, gate: str) -> None:
        self._transaction(lambda: self._bulk_retire([gate]))

    def unretire_gate(self, gate: str) -> None:
        self._transaction(lambda: self._bulk_unretire([gate]))

    def bulk_retire(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_retire(gates))

    def bulk_unretire(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_unretire(gates))

    def mark_retest_candidate(self, gate: str) -> None:
        self._transaction(lambda: self._bulk_mark_retest([gate]))

    def clear_retest_candidate(self, gate: str) -> None:
        self._transaction(lambda: self._bulk_clear_retest([gate]))

    def bulk_mark_retest(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_mark_retest(gates))

    def bulk_clear_retest(self, gates: Iterable[str]) -> None:
        self._transaction(lambda: self._bulk_clear_retest(gates))

    # ── Telegram skin family gating ──────────────────────────────────────────
    def is_blocked(self, gate_name: str) -> bool:
        """True when the gate is runtime-disabled or retired."""
        gate_name = self._validate_gate_name(gate_name)
        return gate_name in self._runtime_disabled or gate_name in self._retired_gates

    def is_skin_blocked(self, gate_keys: Iterable[str]) -> bool:
        """True if any skin gate key (family or FAMILY:KIND) is disabled/retired."""
        for key in gate_keys:
            if not isinstance(key, str) or not key.strip():
                continue
            if self.is_blocked(key):
                return True
        return False

    def classify_skin(
        self,
        text: Optional[str] = None,
        *,
        signal_kind: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        """Classify Telegram card text into a SkinMatch (lazy import)."""
        from bot.config.skin_families import classify_telegram_skin

        return classify_telegram_skin(text, signal_kind=signal_kind, meta=meta)

    def is_telegram_skin_blocked(
        self,
        text: Optional[str] = None,
        *,
        signal_kind: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Classify card text, then check family / FAMILY:KIND against this registry."""
        match = self.classify_skin(text, signal_kind=signal_kind, meta=meta)
        return self.is_skin_blocked(match.gate_keys)

    def _trim_audit(self, audit_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.max_audit_entries and len(audit_log) > self.max_audit_entries:
            return audit_log[-self.max_audit_entries :]
        return list(audit_log)

    def _save_atomic_unlocked(self) -> None:
        doc = dict(self._raw_config)

        trimmed_audit = self._trim_audit(self._audit_log)

        doc["schema_version"] = self.CURRENT_SCHEMA_VERSION
        doc["runtime_disabled"] = sorted(self._runtime_disabled)
        doc["retired_gates"] = sorted(self._retired_gates)
        doc["retest_candidates"] = sorted(self._retest_candidates)
        doc["audit_log"] = trimmed_audit
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        doc.pop("disabled", None)
        doc.pop("manual_disabled", None)

        dir_name = os.path.dirname(self.file_path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix="gates_", suffix=".json", dir=dir_name)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.file_path)
            self._publish_state(
                doc,
                frozenset(doc["runtime_disabled"]),
                frozenset(doc["retired_gates"]),
                frozenset(doc["retest_candidates"]),
                trimmed_audit,
                dirty=False,
            )

        except Exception as e:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass

            raise IOError(f"Atomic save failed: {e}") from e
