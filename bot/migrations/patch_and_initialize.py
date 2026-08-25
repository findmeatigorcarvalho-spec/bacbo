from bot.config.registry import EngineGateRegistry


def run_migration():
    registry = EngineGateRegistry("bot/data/disabled_gates.json")

    # Turns ON winning strategies to bring your signal volume back.
    gates_to_enable = [
        "auto_vault_block",
        "color_acc_all_weak",
        "g3_predictor_hard",
        "solo_proven_room_main",
    ]

    # Retires losing strategies causing engine drain. Retiring removes them from
    # the active rotation (they are disabled) and records the decision in the
    # registry audit log so the change is traceable.
    gates_to_retire = [
        "streak_reversal",
        "solo_red_death_minute_gate",
        "m8sinais_lead_anchor",
    ]

    print(f"Activating high-yield paths: {gates_to_enable}...")
    registry.bulk_enable(gates_to_enable)

    print(f"Retiring high-drain paths: {gates_to_retire}...")
    registry.bulk_retire(gates_to_retire)

    disabled = sorted(registry.disabled_gates_snapshot())
    retired = sorted(registry.retired_gates_snapshot())
    audit_entries = len(registry.audit_log_snapshot())

    print(f"\nDisabled gates: {disabled}")
    print(f"Retired gates: {retired}")
    print(f"Audit log entries: {audit_entries}")
    print("\n[SUCCESS] Your bot's strategies have been updated!")


if __name__ == "__main__":
    run_migration()
