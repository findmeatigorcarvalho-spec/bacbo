"""
card_content_atlas.py — enumerate every card ever fired by what it actually says.

The DB knows 7 signal_kinds. That is the coarse bucket, not the system: two
cards can share signal_kind SOLO_ELITE and encode completely different setups
(one gated on an hour slot, one on a pair of source rooms, one on a tie
cluster). The only way to tell them apart is the card body, so this reads the
bodies and classifies on content.

Three things it produces:

1. A row per distinct card type (the museum's 827), with the content features
   that distinguish it and the claim it makes about itself.
2. Design groups — bodies normalised so that numbers, room handles and times
   become placeholders. Many "distinct types" are one template with different
   numbers substituted in, because the archaeology fingerprinted the rendered
   text including its statistics.
3. The claim-versus-evidence table. Many cards print their own win rate and
   sample size. Grouping those claims by sample size shows whether the edge
   is a property of the setup or of how little data backs it.

Reads committed artifacts only. Writes a report, a markdown summary, and a CSV
with every card so each one can be reviewed by hand.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import re
import statistics
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REPO = os.path.dirname(os.path.dirname(HERE))
ALT_DATA = os.path.join(REPO, "bot", "data")

JSON_PATH = os.path.join(DATA, "card_content_atlas.json")
CSV_PATH = os.path.join(DATA, "card_content_atlas.csv")
MD_PATH = os.path.join(os.path.dirname(HERE), "CARD_CONTENT_ATLAS.md")

# A claim needs this much evidence before its rate means anything at all, and
# even then only if the cell was not chosen for being the best of many.
MIN_CREDIBLE_N = 100

# An n= and its win rate sit within a few characters of each other on a card;
# beyond this they belong to different statistics on the same card.
CLAIM_PAIR_WINDOW = 40

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
WR_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
N_RE = re.compile(r"\bn\s*=\s*(\d+)", re.I)
HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{3,}")
BARE_ROOM_RE = re.compile(r"\b[a-z][a-z0-9_]{5,}\b")
HOUR_RE = re.compile(r"\bH\d{2}\b")
PAIR_RE = re.compile(r"([a-z][a-z0-9_]{4,})\s*\+\s*([a-z][a-z0-9_]{4,})")
TIME_RE = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")

BET_WORDS = (
    "apostar", "aposte", "enter now", "entrada", "entre", "faça agora",
    "act now", "do not bet", "bet ", "gale",
)
RESULT_WORDS = ("win", "loss", "green", "empate", "tie", "ganhou", "perdeu", "✅", "❌")


def _load(name: str, *, alt: bool = False) -> dict | None:
    for base in ((ALT_DATA, DATA) if alt else (DATA, ALT_DATA)):
        path = os.path.join(base, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    return None


_ROOM_VOCAB: set[str] | None = None


def room_vocabulary(bodies: list[str] | None = None) -> set[str]:
    """Source-room handles as they actually appear in the corpus.

    Guessing a room from its shape (lowercase, long enough) also swallows plain
    words like `historico` or `combinado` and collapses unrelated designs, so
    the vocabulary is harvested from @handles and `roomA+roomB` pair lines and
    then matched literally.
    """
    global _ROOM_VOCAB
    if bodies is None and _ROOM_VOCAB is not None:
        return _ROOM_VOCAB

    if bodies is None:
        museum = _load("museum_full_catalog.json") or {}
        bodies = [str(i.get("body") or "") for i in museum.get("items") or []]

    vocab: set[str] = set()
    for b in bodies:
        for m in HANDLE_RE.finditer(b):
            vocab.add(m.group(0).lstrip("@").lower())
        for m in PAIR_RE.finditer(b):
            vocab.add(m.group(1).lower())
            vocab.add(m.group(2).lower())
    vocab = {v for v in vocab if len(v) >= 5}
    if bodies is None or _ROOM_VOCAB is None:
        _ROOM_VOCAB = vocab
    return vocab


def skeleton(body: str | None, vocab: set[str] | None = None) -> str:
    """Normalise a body so cards differing only in their data collapse together."""
    s = str(body or "")
    rooms = room_vocabulary() if vocab is None else vocab
    s = TIME_RE.sub("<TIME>", s)
    s = HANDLE_RE.sub("<ROOM>", s)
    if rooms:
        s = re.sub(
            r"\b[a-z][a-z0-9_]{4,}\b",
            lambda m: "<ROOM>" if m.group(0).lower() in rooms else m.group(0),
            s,
        )
    s = NUM_RE.sub("<N>", s)
    # `WR=<N>%` and `WR= <N>%` are the same design rendered with padding.
    s = re.sub(r"\s*([=:+])\s*", r"\1", s)
    s = re.sub(r"[ \t]+", " ", s)
    return "\n".join(line.strip() for line in s.splitlines()).strip()


def wilson(wins: int, n: int) -> tuple[float, float] | None:
    if n <= 0:
        return None
    z = 1.96
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, centre - half), 2), round(100 * min(1.0, centre + half), 2))


def primary_claim(body: str | None) -> tuple[float | None, int | None]:
    """The card's own (win rate, sample size), taken as a colocated pair.

    A stats card prints several rates and several sample sizes, often with a
    tight parenthetical like `b=86.4%(n=22)` after the headline. Anchoring on
    the first n= and taking the percentage nearest to it keeps the headline
    claim; pairing the highest rate with the smallest n, or simply taking the
    tightest pair anywhere, would invent a claim the card never made.
    """
    b = str(body or "")
    pcts = [
        (m.start(), float(m.group(1).replace(",", ".")))
        for m in WR_RE.finditer(b)
        if 0 < float(m.group(1).replace(",", ".")) <= 100
    ]
    ns = [(m.start(), int(m.group(1))) for m in N_RE.finditer(b)]
    if not pcts:
        return (None, None)
    if not ns:
        return (max(v for _, v in pcts), None)

    npos, nval = ns[0]
    near = min(pcts, key=lambda p: abs(p[0] - npos))
    if abs(near[0] - npos) > CLAIM_PAIR_WINDOW:
        return (max(v for _, v in pcts), nval)
    return (near[1], nval)


def features(body: str | None) -> dict:
    """What this card actually does, read off its text."""
    b = str(body or "")
    low = b.lower()
    wr, n = primary_claim(b)
    pair = PAIR_RE.search(b)
    return {
        "claims_wr_pct": wr,
        "claims_n": n,
        "room_pair": f"{pair.group(1)}+{pair.group(2)}" if pair else None,
        "hour_gate": sorted(set(HOUR_RE.findall(b))) or None,
        "instructs_bet": any(w in low for w in BET_WORDS),
        "reports_outcome": any(w in low for w in RESULT_WORDS),
        "has_color_call": any(c in b for c in ("🔵", "🔴")) or "blue" in low or "red" in low,
        "has_countdown": bool(re.search(r"\b\d+\s*s\b|left|window|janela|restam", low)),
        "mentions_gale": "gale" in low or re.search(r"\bg[123]\b", low) is not None,
        "lines": len([line for line in b.splitlines() if line.strip()]),
        "chars": len(b),
    }


def claim_verdict(wr: float | None, n: int | None) -> str:
    if wr is None:
        return "NO_CLAIM"
    if n is None:
        return "CLAIM_WITHOUT_SAMPLE_SIZE"
    if n < MIN_CREDIBLE_N:
        return "CLAIM_ON_THIN_SAMPLE"
    ci = wilson(round(wr / 100 * n), n)
    if ci and ci[0] > 50.0:
        return "CLAIM_SURVIVES_ITS_OWN_SAMPLE"
    return "CLAIM_WITHIN_NOISE"


def build_cards() -> list[dict]:
    museum = _load("museum_full_catalog.json") or {}
    out = []
    for item in museum.get("items") or []:
        body = item.get("body")
        feat = features(body)
        out.append(
            {
                "chrono_order": item.get("chrono_order"),
                "family_id": item.get("family_id"),
                "registry_family": item.get("registry_family") or "",
                "role": item.get("role"),
                "label": item.get("label"),
                "era": item.get("era"),
                "first_chat": item.get("first_chat"),
                "existence_at": item.get("existence_at"),
                "tg_count": item.get("tg_count") or 0,
                "never_fired": bool(item.get("never_fired")),
                "had_original_result": bool(item.get("had_original_result")),
                "first_line": (item.get("example_first_line") or "").strip(),
                "skeleton": skeleton(body),
                **feat,
                "claim_verdict": claim_verdict(feat["claims_wr_pct"], feat["claims_n"]),
            }
        )
    out.sort(key=lambda c: c["chrono_order"] or 0)
    return out


def design_groups(cards: list[dict]) -> list[dict]:
    """Collapse cards whose only difference is the data substituted into them."""
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for card in cards:
        groups[card["skeleton"]].append(card)

    out = []
    for sk, members in groups.items():
        out.append(
            {
                "skeleton_first_line": (sk.splitlines() or [""])[0][:160],
                "variants": len(members),
                "tg_count": sum(m["tg_count"] for m in members),
                "roles": sorted({m["role"] for m in members if m["role"]}),
                "instructs_bet": any(m["instructs_bet"] for m in members),
                "example_family": next(
                    (m["registry_family"] for m in members if m["registry_family"]), ""
                ),
                "chrono_first": min((m["chrono_order"] or 0) for m in members),
            }
        )
    out.sort(key=lambda g: (-g["variants"], -g["tg_count"]))
    return out


def claim_table(cards: list[dict]) -> dict:
    """Does the claimed rate depend on the setup, or on how little data backs it?"""
    rows = [
        c for c in cards if c["claims_wr_pct"] is not None and c["claims_n"] is not None
    ]
    buckets = [(0, 15, "n<=15"), (16, 30, "n=16-30"), (31, 60, "n=31-60"),
               (61, 150, "n=61-150"), (151, 10 ** 9, "n>150")]
    by_bucket = []
    for lo, hi, label in buckets:
        g = [c["claims_wr_pct"] for c in rows if lo <= c["claims_n"] <= hi]
        if g:
            by_bucket.append(
                {
                    "bucket": label,
                    "cards": len(g),
                    "mean_wr_pct": round(statistics.mean(g), 1),
                    "max_wr_pct": round(max(g), 1),
                    "min_wr_pct": round(min(g), 1),
                }
            )

    perfect = sorted(
        ({"n": c["claims_n"], "first_line": c["first_line"][:80], "tg_count": c["tg_count"]}
         for c in rows if c["claims_wr_pct"] >= 99.9),
        key=lambda r: r["n"],
    )
    credible = [c for c in rows if c["claims_n"] >= MIN_CREDIBLE_N]
    survives = [c for c in rows if c["claim_verdict"] == "CLAIM_SURVIVES_ITS_OWN_SAMPLE"]

    trend = None
    if len(by_bucket) >= 2:
        trend = round(by_bucket[0]["mean_wr_pct"] - by_bucket[-1]["mean_wr_pct"], 1)

    return {
        "cards_with_claim_and_sample": len(rows),
        "by_sample_size": by_bucket,
        "mean_wr_drop_smallest_to_largest_bucket": trend,
        "perfect_claims": perfect,
        "perfect_claims_max_n": max((p["n"] for p in perfect), default=None),
        "claims_with_credible_n": len(credible),
        "claims_surviving_own_sample": [
            {"n": c["claims_n"], "wr": c["claims_wr_pct"], "first_line": c["first_line"][:80]}
            for c in survives
        ],
        "min_credible_n": MIN_CREDIBLE_N,
    }


def _as_pct(value: float | None) -> float | None:
    """The cross-compare stores map rates as fractions; render them as percents."""
    if value is None:
        return None
    return round(value * 100, 2) if value <= 1 else round(value, 2)


def selection_math(cards: list[dict]) -> dict:
    """How many perfect cells pure chance would hand you for free.

    The high-rate setups are pairs of source rooms agreeing. Every pair of the
    rooms in the corpus is a candidate, each candidate is scored on a handful of
    observations, and only the winners got a card. That search has to be priced
    before a 100% cell means anything.
    """
    rooms = room_vocabulary()
    pairs = len(rooms) * (len(rooms) - 1) // 2

    perfect = [c for c in cards if (c["claims_wr_pct"] or 0) >= 99.9 and c["claims_n"]]
    observed = len(perfect)
    typical_n = int(statistics.median([c["claims_n"] for c in perfect])) if perfect else None

    # Baseline is the bot's own overall label rate, since these cells were
    # scored against those same labels rather than against casino results.
    baseline = 0.775
    expected = None
    if typical_n:
        expected = round(pairs * baseline ** typical_n, 1)

    return {
        "source_rooms_in_corpus": len(rooms),
        "candidate_pairs": pairs,
        "baseline_label_win_rate": baseline,
        "perfect_cells_observed": observed,
        "typical_n_behind_a_perfect_cell": typical_n,
        "perfect_cells_expected_by_chance": expected,
        "verdict": (
            "FEWER_PERFECT_CELLS_THAN_CHANCE_PRODUCES"
            if expected is not None and observed <= expected
            else "MORE_PERFECT_CELLS_THAN_CHANCE_PRODUCES"
            if expected is not None
            else "NOT_COMPUTABLE"
        ),
        "note": (
            "Expected count is candidate_pairs * baseline**n — how many pairs reach a "
            "spotless record on n observations with no skill at all. Pairs with fewer "
            "than n shared signals cannot produce a cell, so the true expected count is "
            "lower than this ceiling; the comparison is still the right order of "
            "magnitude for pricing the search."
        ),
    }


def coverage() -> dict:
    cross = _load(os.path.join("tg_cross_compare", "tg_cross_compare.json"), alt=True)
    if cross is None:
        path = os.path.join(ALT_DATA, "tg_cross_compare", "tg_cross_compare.json")
        cross = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return {
        "distinct_tg_types": cross.get("total_distinct_types"),
        "product_looking_types": cross.get("product_looking_types"),
        "mapped_types": cross.get("mapped_product_types"),
        "unmapped_types": cross.get("unmapped_product_types"),
        "type_map_rate_pct": _as_pct(cross.get("map_rate_product")),
        "product_msgs": cross.get("product_msgs"),
        "mapped_msgs": cross.get("mapped_msgs"),
        "msg_map_rate_pct": _as_pct(cross.get("map_rate_msgs")),
        "by_chat_msgs": cross.get("by_first_chat_msg_counts") or {},
        "registry_never_seen": cross.get("registry_never_seen_count"),
        "note": (
            "Type ids were fingerprinted from rendered text including the statistics, "
            "so one template renders a new 'type' for every number it prints. Unmapped "
            "types are mostly that long tail, which is why message coverage is far "
            "higher than type coverage."
        ),
    }


def build_report() -> dict:
    cards = build_cards()
    designs = design_groups(cards)
    claims = claim_table(cards)
    cov = coverage()

    bet_cards = [c for c in cards if c["instructs_bet"]]
    fired = [c for c in cards if c["tg_count"] > 0]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Every distinct card type the Telegram archaeology catalogued, classified "
            "on body content rather than signal_kind."
        ),
        "totals": {
            "card_types": len(cards),
            "distinct_designs": len(designs),
            "designs_with_one_variant": sum(1 for g in designs if g["variants"] == 1),
            "card_types_that_fired": len(fired),
            "card_types_never_fired": len(cards) - len(fired),
            "card_types_instructing_a_bet": len(bet_cards),
            "card_types_with_paired_result": sum(1 for c in cards if c["had_original_result"]),
            "by_role": dict(collections.Counter(c["role"] for c in cards)),
            "by_claim_verdict": dict(collections.Counter(c["claim_verdict"] for c in cards)),
        },
        "claims": claims,
        "selection_math": selection_math(cards),
        "coverage": cov,
        "top_designs": designs[:25],
        "cards": cards,
    }


def write_csv(cards: list[dict], path: str) -> None:
    cols = [
        "chrono_order", "role", "registry_family", "era", "first_chat", "existence_at",
        "tg_count", "never_fired", "had_original_result", "instructs_bet",
        "reports_outcome", "has_color_call", "has_countdown", "mentions_gale",
        "room_pair", "claims_wr_pct", "claims_n", "claim_verdict", "lines", "first_line",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for card in cards:
            row = dict(card)
            row["hour_gate"] = ",".join(card["hour_gate"] or [])
            writer.writerow(row)


def render_markdown(rep: dict) -> str:
    t = rep["totals"]
    cl = rep["claims"]
    cov = rep["coverage"]
    lines: list[str] = []
    add = lines.append

    add("# CARD CONTENT ATLAS — every card type, read by what it says")
    add("")
    add(f"Generated {rep['generated_at']}. Reproduce with `python3 bot/card_content_atlas.py`.")
    add("")
    add("`signal_kind` only knows 7 buckets. Two cards sharing one kind can encode "
        "entirely different setups, so everything here is classified on body content.")
    add("")

    add("## 1. How many distinct cards there really are")
    add("")
    add("| Measure | Count |")
    add("| --- | --- |")
    add(f"| Card types catalogued | {t['card_types']} |")
    add(f"| Distinct designs after normalising numbers/rooms/times | {t['distinct_designs']} |")
    add(f"| Designs with a single variant | {t['designs_with_one_variant']} |")
    add(f"| Card types that actually fired | {t['card_types_that_fired']} |")
    add(f"| Card types built but never fired | {t['card_types_never_fired']} |")
    add(f"| Card types that instruct a bet | {t['card_types_instructing_a_bet']} |")
    add(f"| Card types with their original result preserved | {t['card_types_with_paired_result']} |")
    add("")
    add(f"Telegram holds {cov['distinct_tg_types']:,} distinct type fingerprints, of which "
        f"{cov['product_looking_types']:,} look like product cards. Only "
        f"{cov['mapped_types']:,} map to a registry family ({cov['type_map_rate_pct']}% of "
        f"types) — but those cover {cov['msg_map_rate_pct']}% of product messages. "
        f"{cov['note']}")
    add("")
    add("Message volume by chat (first appearance):")
    add("")
    add("| Chat | Messages |")
    add("| --- | --- |")
    for chat, n in sorted((cov["by_chat_msgs"] or {}).items(), key=lambda kv: -kv[1]):
        add(f"| {chat} | {n:,} |")
    add("")

    add("## 2. Designs carrying the most variants")
    add("")
    add("Each row is one template; variants are the same card with different numbers in it.")
    add("")
    add("| Variants | TG msgs | Bet? | Roles | First line of design |")
    add("| --- | --- | --- | --- | --- |")
    for g in rep["top_designs"][:15]:
        bet = "yes" if g["instructs_bet"] else "no"
        first = g["skeleton_first_line"].replace("|", "\\|") or "(empty)"
        add(f"| {g['variants']} | {g['tg_count']:,} | {bet} | {'/'.join(g['roles'])} | `{first}` |")
    add("")

    add("## 3. What the cards claim about themselves")
    add("")
    add(f"{cl['cards_with_claim_and_sample']} card types print both a win rate and a sample "
        f"size. Grouped by how much data backs the claim:")
    add("")
    add("| Sample size | Cards | Mean claimed WR | Best claim |")
    add("| --- | --- | --- | --- |")
    for b in cl["by_sample_size"]:
        add(f"| {b['bucket']} | {b['cards']} | {b['mean_wr_pct']}% | {b['max_wr_pct']}% |")
    add("")
    if cl["mean_wr_drop_smallest_to_largest_bucket"]:
        add(f"Mean claimed win rate falls "
            f"{cl['mean_wr_drop_smallest_to_largest_bucket']} points from the smallest "
            f"samples to the largest. A real edge does not weaken as you measure it more; "
            f"a selected one does, because the selection is what produced the number.")
        add("")
    perfect = cl["perfect_claims"]
    if perfect:
        add(f"### Every 100% claim, and the evidence under it")
        add("")
        add(f"{len(perfect)} card types claim a perfect rate. The largest sample behind any "
            f"of them is **n={cl['perfect_claims_max_n']}**.")
        add("")
        add("| n | TG msgs | Card |")
        add("| --- | --- | --- |")
        for p in perfect:
            add(f"| {p['n']} | {p['tg_count']:,} | `{p['first_line'].replace('|', chr(92) + '|')}` |")
        add("")
    add(f"Claims resting on at least n={cl['min_credible_n']}: "
        f"**{cl['claims_with_credible_n']}**.")
    add("")
    surviving = cl["claims_surviving_own_sample"]
    if surviving:
        add("These clear even money against their own stated sample, before accounting for "
            "having been picked as the best of many candidates:")
        add("")
        for s in surviving:
            add(f"- {s['wr']}% on n={s['n']} — `{s['first_line']}`")
    else:
        add("No claim clears even money against its own stated sample at 95% confidence.")
    add("")
    sm = rep["selection_math"]
    add("### Pricing the search that produced those cells")
    add("")
    add(f"Most high claims are keyed to a pair of source rooms agreeing. The corpus "
        f"contains **{sm['source_rooms_in_corpus']} source rooms**, which is "
        f"**{sm['candidate_pairs']:,} candidate pairs**. Scoring every pair against the "
        f"bot's own labels, which run about "
        f"{sm['baseline_label_win_rate'] * 100:.1f}% overall, you would expect roughly "
        f"**{sm['perfect_cells_expected_by_chance']:,} pairs** to show a spotless record "
        f"on n={sm['typical_n_behind_a_perfect_cell']} with no skill whatsoever.")
    add("")
    add(f"The corpus contains **{sm['perfect_cells_observed']}**. {sm['note']}")
    add("")
    add("So the perfect cells are not merely weak evidence, they are fewer than the search "
        "hands out for free. The card records the winner without recording the contest.")
    add("")

    add("## 4. How to use the CSV")
    add("")
    add("`bot/data/card_content_atlas.csv` has one row per card type with its content "
        "features, so every card can be reviewed by hand. Useful filters:")
    add("")
    add("- `instructs_bet=True` — cards that tell you to place money")
    add("- `tg_count=0` — built in code, never fired once")
    add("- `claim_verdict=CLAIM_ON_THIN_SAMPLE` — prints a rate with too little behind it")
    add("- `room_pair` non-empty — setup is a pair of source rooms agreeing")
    add("- `had_original_result=True` — the original outcome card survives next to it")
    add("")
    return "\n".join(lines)


def save_report(json_path: str = JSON_PATH, csv_path: str = CSV_PATH,
                md_path: str = MD_PATH) -> dict:
    rep = build_report()
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    os.makedirs(os.path.dirname(md_path), exist_ok=True)

    slim = {k: v for k, v in rep.items() if k != "cards"}
    slim["cards_csv"] = os.path.relpath(csv_path, REPO)
    for path, payload in (
        (json_path, json.dumps(slim, indent=2, ensure_ascii=False) + "\n"),
        (md_path, render_markdown(rep)),
    ):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    write_csv(rep["cards"], csv_path)
    return rep


def main() -> int:
    parser = argparse.ArgumentParser(description="Enumerate every card type by content")
    parser.add_argument("--json", default=JSON_PATH)
    parser.add_argument("--csv", default=CSV_PATH)
    parser.add_argument("--md", default=MD_PATH)
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    rep = save_report(args.json, args.csv, args.md)
    if args.print:
        print(render_markdown(rep))
    else:
        t = rep["totals"]
        cl = rep["claims"]
        print(
            "[CARD-ATLAS]",
            f"types={t['card_types']}",
            f"designs={t['distinct_designs']}",
            f"bet_cards={t['card_types_instructing_a_bet']}",
            f"never_fired={t['card_types_never_fired']}",
            f"claims={cl['cards_with_claim_and_sample']}",
            f"credible_n={cl['claims_with_credible_n']}",
            f"perfect_max_n={cl['perfect_claims_max_n']}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
