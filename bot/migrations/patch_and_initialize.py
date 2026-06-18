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

    # Turns OFF losing strategies causing engine drain.
    gates_to_disable = [
        "streak_reversal",
        "solo_red_death_minute_gate",
        "m8sinais_lead_anchor",
    ]

    print(f"Activating high-yield paths: {gates_to_enable}...")
    registry.bulk_enable(gates_to_enable)

    print(f"Deactivating high-drain paths: {gates_to_disable}...")
    registry.bulk_disable(gates_to_disable)

    print("\n[SUCCESS] Your bot's strategies have been updated!")


if __name__ == "__main__":
    run_migration()
