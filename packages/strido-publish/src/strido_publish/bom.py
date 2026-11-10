"""BOM, CAD coverage check and shopping-bundle optimiser.

Reads hardware/bom.yaml and the CAD assembly, then writes
  docs/bom/README.md         full BOM by category + fastener table + CAD coverage
  docs/bom/shopping_list.md  vendor bundles for several strategies
  docs/bom/bom.csv           flat BOM (cheapest offer per line)

Optimiser: for every subset of shops it takes the cheapest offer per line inside the subset
and adds shipping (free-shipping thresholds, per-order fees); the best subset wins. It does not
explore buying a dearer offer only to reach a free-shipping threshold.

Exit code 1 if, for the offers any strategy picks, a purchased part or fastener of the CAD is
not covered (fasteners need max(2, 10 %) spares), or a BOM line references an unknown CAD id.
"""

import csv
import itertools
import math
import sys
from collections import Counter, defaultdict

import yaml

from strido.workspace import path
from strido_cad import catalog
from strido_cad.paths import FASTENER_CATALOGUE

from .pricing import money, offer_cost, pieces_bought
from .shopping import write_product_data, write_shop_data, write_shopping

BOM = path("hardware/bom.yaml")
OUT = path("docs/bom")
NON_EU = {"aliexpress", "digikey_at"}
FASTENER_KEYS = set(yaml.safe_load(FASTENER_CATALOGUE.read_text())["items"])


def spare_target(count: int, is_fastener: bool) -> int:
    return count + max(2, math.ceil(0.1 * count)) if is_fastener else count


def cad_counts() -> tuple[Counter, dict]:
    counts = Counter()
    usage = defaultdict(Counter)
    for item in catalog.full_assembly():
        if item.kind not in ("purchased", "fastener"):
            continue
        name = item.part.split("/")[1]
        counts[name] += 1
        if item.kind == "fastener":
            usage[name][item.meta.get("joint", "?")] += 1
    return counts, usage


def coverage(chosen, counts) -> tuple[list, list]:
    """Supply from the chosen offers (packs rounded up) against the CAD counts."""
    supplied = Counter()
    for line, offer in chosen:
        for key, per_piece in line.get("cad", {}).items():
            supplied[key] += per_piece * pieces_bought(line, offer)
    rows, problems = [], []
    for key, count in sorted(counts.items()):
        need = spare_target(count, key in FASTENER_KEYS)
        ok = supplied[key] >= need
        rows.append((key, count, need, supplied[key], ok))
        if not ok:
            problems.append(f"{key}: CAD needs {need} (incl. spares), BOM supplies {supplied[key]:g}")
    problems += [f"BOM line covers {key}, which is not in the CAD assembly" for key in supplied if key not in counts]
    return rows, problems


def solve(lines, vendors, allowed_vendor, allowed_offer=lambda line, offer: True):
    """Best shop subset with the cheapest allowed offer per line inside it, shipping included."""
    candidates = sorted(v for v in vendors if allowed_vendor(v))
    best = None
    for size in range(1, len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            chosen = []
            for line in lines:
                offers = [o for o in line["offers"] if o["vendor"] in subset and allowed_offer(line, o)]
                if not offers:
                    break
                chosen.append((line, min(offers, key=lambda o: offer_cost(line, o))))
            else:
                result = price(chosen, vendors)
                if best is None or result["total"] < best["total"] - 1e-9:
                    best = result
    return best


def price(chosen, vendors) -> dict:
    subtotal = defaultdict(float)
    for line, offer in chosen:
        subtotal[offer["vendor"]] += offer_cost(line, offer)
    shipping = {}
    for vendor, amount in subtotal.items():
        info = vendors[vendor]
        free = info.get("free_from") is not None and amount >= info["free_from"]
        shipping[vendor] = (0.0 if free else info["shipping"]) + info.get("per_order_fee", 0.0)
    return {
        "total": sum(subtotal.values()) + sum(shipping.values()),
        "chosen": chosen,
        "subtotal": dict(subtotal),
        "shipping": shipping,
        "shops": len(subtotal),
    }


def fewest_shops(lines, vendors):
    """Smallest number of shops first, then the lowest total among those."""
    for size in range(1, len(vendors) + 1):
        results = [
            solve(lines, {v: vendors[v] for v in subset}, lambda v: True)
            for subset in itertools.combinations(sorted(vendors), size)
        ]
        results = [r for r in results if r is not None]
        if results:
            return min(results, key=lambda r: r["total"])
    return None


def genuine_offer(line, offer) -> bool:
    has_genuine = any(o.get("genuine", True) for o in line["offers"])
    return offer.get("genuine", True) or not has_genuine


def eu_offer(line, offer) -> bool:
    """EU warehouse offers; a line without any EU offer may fall back to DigiKey."""
    has_eu = any(o["vendor"] not in NON_EU for o in line["offers"])
    return offer["vendor"] not in NON_EU or (not has_eu and offer["vendor"] == "digikey_at")


def cheapest(line):
    return min(line["offers"], key=lambda o: offer_cost(line, o))


def write_bom(data, usage, cover_rows, problems):
    lines = data["lines"]
    vendors = data["vendors"]
    out = [
        "# Bill of materials",
        "",
        "Generated by `strido_publish.bom` from `hardware/bom.yaml` and the CAD assembly. Prices: EUR incl. VAT, observed 2026-10-30 "
        "(cheapest offer shown; all offers and bundles in [shopping_list.md](shopping_list.md); research notes in [sources.md](sources.md)). "
        "Printed parts: [hardware/print/print_list.md](../../hardware/print/print_list.md).",
        "",
    ]
    by_category = defaultdict(list)
    for line in lines:
        by_category[line["category"]].append(line)
    grand = 0.0
    for category, items in by_category.items():
        out += [f"## {category}", "", "| Qty | Item | Cheapest offer | Price | Note |", "|---|---|---|---|---|"]
        subtotal = 0.0
        for line in items:
            offer = cheapest(line)
            cost = offer_cost(line, offer)
            subtotal += cost
            pack = f" (packs of {offer['pack']})" if offer.get("pack", 1) > 1 else ""
            flags = []
            if not offer.get("genuine", True):
                flags.append("clone/third-party")
            if offer["status"] != "observed":
                flags.append(f"price {offer['status']}")
            note = "; ".join(filter(None, [line.get("note", ""), ", ".join(flags)]))
            out.append(
                f"| {line['qty']} | {line['name']} | {vendors[offer['vendor']]['name']} {offer['sku']}{pack} | {money(cost)} | {note} |"
            )
        grand += subtotal
        out += [f"| | **Subtotal** | | **{money(subtotal)}** | |", ""]
    out += [
        f"**Parts total (cheapest offers, before shipping): {money(grand)}.** Shipping-optimised bundles: [shopping_list.md](shopping_list.md).",
        "",
    ]
    out += [
        "## Fasteners by joint (from the CAD)",
        "",
        "| Fastener | In CAD | Buy (incl. spares) | Used at |",
        "|---|---|---|---|",
    ]
    for key, count, need, _supplied, _ok in cover_rows:
        if key in FASTENER_KEYS:
            joints = ", ".join(f"{joint} ×{n}" for joint, n in usage[key].most_common())
            out.append(f"| `{key}` | {count} | {need} | {joints} |")
    out += [
        "",
        "## CAD coverage check (cheapest offers)",
        "",
        "Every purchased part and fastener instance in the assembled CAD model must be supplied by the offers a strategy buys "
        "(packs rounded up; fasteners with max(2, 10 %) spares). Checked for every strategy in the shopping list.",
        "",
        "| CAD id | In CAD | Needed | Supplied | OK |",
        "|---|---|---|---|---|",
    ]
    for key, count, need, supplied, ok in cover_rows:
        out.append(f"| `{key}` | {count} | {need} | {supplied:g} | {'yes' if ok else '**NO**'} |")
    out += [
        "",
        f"Result: {'all covered' if not problems else 'PROBLEMS: ' + '; '.join(problems)}",
        "",
        "Not modelled in the CAD and therefore bought from the lines above without a coverage check: cables, wire, fuses, "
        "consumables, microSD, charger.",
        "",
        "## Tools (not in the totals)",
        "",
        "| Tool | Vendor | Price |",
        "|---|---|---|",
    ]
    for tool in data["tools"]:
        cost = money(tool["price"]) if tool.get("price") is not None else "—"
        out.append(f"| {tool['name']} | {tool['vendor']} {tool.get('sku', '')} | {cost} |")
    (OUT / "README.md").write_text("\n".join(out) + "\n")
    with (OUT / "bom.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "category",
                "qty",
                "name",
                "vendor",
                "sku",
                "pack",
                "price_eur",
                "line_cost_eur",
                "price_status",
                "genuine",
            ]
        )
        for line in lines:
            offer = cheapest(line)
            writer.writerow(
                [
                    line["id"],
                    line["category"],
                    line["qty"],
                    line["name"],
                    vendors[offer["vendor"]]["name"],
                    offer["sku"],
                    offer.get("pack", 1),
                    offer["price"],
                    round(offer_cost(line, offer), 2),
                    offer["status"],
                    offer.get("genuine", True),
                ]
            )


def main():
    data = yaml.safe_load(BOM.read_text())
    counts, usage = cad_counts()
    OUT.mkdir(parents=True, exist_ok=True)
    vendors = data["vendors"]
    lines = data["lines"]
    strategies = {
        "lowest": ("Lowest total", solve(lines, vendors, lambda v: True)),
        "fewest": ("Fewest shops", fewest_shops(lines, vendors)),
        "eu": (
            "EU warehouses (DigiKey only for parts without an EU offer, no AliExpress)",
            solve(lines, vendors, lambda v: v != "aliexpress", eu_offer),
        ),
        "genuine": ("Genuine boards where available", solve(lines, vendors, lambda v: True, genuine_offer)),
    }
    problems = []
    for key, (label, result) in strategies.items():
        assert result is not None, f"strategy {key} is infeasible"
        _, strategy_problems = coverage(result["chosen"], counts)
        problems += [f"{label}: {problem}" for problem in strategy_problems]
    cover_rows, cheapest_problems = coverage([(line, cheapest(line)) for line in lines], counts)
    write_bom(data, usage, cover_rows, cheapest_problems + problems)
    write_shopping(data, strategies)
    write_shop_data(data, strategies)
    write_product_data(data)
    for label, result in strategies.values():
        print(f"{label:75s} {result['shops']} shops  {money(result['total'])}")
    if problems or cheapest_problems:
        print("COVERAGE PROBLEMS:\n  " + "\n  ".join(cheapest_problems + problems))
        sys.exit(1)
    print("CAD coverage: all purchased parts and fasteners supplied in every strategy")


if __name__ == "__main__":
    main()
