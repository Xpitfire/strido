"""Shopping outputs of the BOM: the plan comparison page (docs/bom/shopping_list.md), the shop data
(docs/bom/shop.json) and the product information (docs/bom/products.json from hardware/products.yaml),
both read by the parts shop and print kit on the documentation site."""

import json
import math
import re
import urllib.parse
from collections import defaultdict

import yaml

from strido.workspace import path

from .pricing import money, offer_cost

OUT = path("docs/bom")
PRODUCTS = path("hardware/products.yaml")
PRINTED_STL = path("hardware/print/stl")
WIKI = path("docs/wiki")
# Amazon product id inside a SKU text, e.g. "B09X7CXWQQ (WayPonDEV)"
ASIN = re.compile(r"\bB0[A-Z0-9]{8}\b")
# DigiKey order number inside a SKU text, e.g. "SC1431 (2648-SC1431-ND)"
DIGIKEY_PN = re.compile(r"\b[\w./-]+-ND\b")
# AliExpress item id: a long run of digits, e.g. "4000135787995, variant 35kg-180 Waterproof"
ALIEXPRESS_ITEM = re.compile(r"\b\d{10,}\b")
# Seller note in brackets inside a SKU text, e.g. "P000461 (zinc-plated)" -> "zinc-plated"
SKU_NOTE = re.compile(r"\(([^)]+)\)")


# Plan letter and "choose it when" text per shopping strategy (keys of the strategies built in bom.main()).
PLAN_GUIDE = {
    "lowest": (
        "A",
        "the price matters most; servos come from AliExpress (2-3 weeks; above €150 split the order or expect import VAT)",
    ),
    "fewest": (
        "B",
        "you want as few parcels and accounts as possible; costs more because Amazon replaces cheaper shops",
    ),
    "eu": (
        "C",
        "everything from EU warehouses (no AliExpress), fastest delivery; DigiKey only where no EU shop lists the part",
    ),
    "genuine": ("D", "like A, but original Adafruit/Seeed/Pololu boards wherever a clone would be cheaper"),
}


def plan_title(key: str, label: str) -> str:
    return f"Plan {PLAN_GUIDE[key][0]}: {label}"


def plan_anchor(key: str, label: str) -> str:
    """VitePress heading slug of the plan section (lowercase, words joined by '-')."""
    words = "".join(ch.lower() if ch.isalnum() else " " for ch in plan_title(key, label)).split()
    return "-".join(words)


def differing_lines(strategies) -> list[tuple[str, list[tuple[str, float]]]]:
    """BOM lines bought from different shops depending on the plan: (item, [(shop, cost) per plan])."""
    per_plan = [{line["id"]: (line, offer) for line, offer in result["chosen"]} for _, result in strategies.values()]
    rows = []
    for line_id, (line, _) in per_plan[0].items():
        picks = [plan[line_id] for plan in per_plan]
        if len({offer["vendor"] for _, offer in picks}) > 1:
            rows.append((line["name"], [(offer["vendor"], offer_cost(line, offer)) for line, offer in picks]))
    return rows


def write_shopping(data, strategies):
    vendors = data["vendors"]
    cheapest_total = min(result["total"] for _, result in strategies.values())
    out = [
        "# Shopping list and bundles (Austria)",
        "",
        "**How to read this page.** There are four alternative ways to buy the parts. Each plan is a *complete* shopping "
        "list for the whole robot: every purchased part, every screw and nut with spares, and the filament. Pick **one** "
        "plan and order everything listed under it; do not mix plans. The plans differ only in which shop supplies an "
        "item, so the price, the number of parcels and the delivery time differ. Tools and the 3D printer are not "
        "included (see the [tools list](README.md#tools-not-in-the-totals)). To change single items, order for several "
        "robots or fill the shop carts, use the [parts shop](../shop.md).",
        "",
        "| Plan | Choose it when | Shops (parcels) | Parts | Shipping | **Total** | vs. cheapest |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, (label, result) in strategies.items():
        parts = sum(result["subtotal"].values())
        shipping = sum(result["shipping"].values())
        extra = result["total"] - cheapest_total
        out.append(
            f"| [{plan_title(key, label)}](#{plan_anchor(key, label)}) | {PLAN_GUIDE[key][1]} | {result['shops']} | "
            f"{money(parts)} | {money(shipping)} | **{money(result['total'])}** | {'cheapest' if extra < 0.005 else '+' + money(extra)} |"
        )
    differing = differing_lines(strategies)
    letters = [PLAN_GUIDE[key][0] for key in strategies]
    out += [
        "",
        "Prices EUR incl. VAT, observed 2026-10-30; shipping is to Austria (free-shipping thresholds and per-order fees "
        "included). Re-check prices and stock before ordering.",
        "",
        "## Where the plans differ",
        "",
        f"{len(differing)} of {len(data['lines'])} items come from different shops depending on the plan; every other "
        "item is bought from the same shop in all plans. Shop and cost per plan:",
        "",
        "| Item | " + " | ".join(f"Plan {letter}" for letter in letters) + " |",
        "|---|" + "---|" * len(letters),
    ]
    for name, picks in differing:
        out.append(f"| {name} | " + " | ".join(f"{vendors[v]['name']} {money(c)}" for v, c in picks) + " |")
    out += [
        "",
        "How the plans are computed (`strido_publish.bom`): for each plan the optimiser tries every subset of the "
        "allowed shops, takes the cheapest allowed offer per item inside the subset and adds each shop's shipping. It "
        "does not buy dearer offers just to reach a free-shipping threshold.",
        "",
    ]
    for key, (label, result) in strategies.items():
        out += [
            f"## {plan_title(key, label)}",
            "",
            f"**{money(result['total'])}** in {result['shops']} orders. Order everything below; the per-shop "
            "subtotals add up to this total.",
            "",
        ]
        by_vendor = defaultdict(list)
        for line, offer in result["chosen"]:
            by_vendor[offer["vendor"]].append((line, offer))
        for vendor, items in sorted(by_vendor.items(), key=lambda kv: -result["subtotal"][kv[0]]):
            info = vendors[vendor]
            out += [
                f"### {info['name']} – {money(result['subtotal'][vendor])} + shipping {money(result['shipping'][vendor])}",
                "",
                "| Order | Item | SKU | Cost |",
                "|---|---|---|---|",
            ]
            for line, offer in items:
                pack = offer.get("pack", 1)
                order = f"{math.ceil(line['qty'] / pack)} × pack of {pack}" if pack > 1 else f"{line['qty']}"
                out.append(f"| {order} | {line['name']} | {offer['sku']} | {money(offer_cost(line, offer))} |")
            if info.get("note"):
                out.append(f"\n_{info['note']}_")
            out.append("")
    out += [
        "## Caveats",
        "",
        "* Low stock at research time: 633ZZ 8-pack, bronze sleeves, Lindinger Hobbywing UBEC, Amazon M2 stand-offs. Order these first or use the alternatives in `hardware/bom.yaml`.",
        "* Servos: buy the SPT5435LV **-180W** (180°) variant. The Amazon listing does not state the angle; the AliExpress order exceeds the €150 IOSS limit (split it or expect import VAT).",
        "* DigiKey ships from the US (customs-cleared, VAT included). Pololu items on DigiKey are Marketplace items shipped by Pololu; their extra shipping fee is not modelled.",
        "* DE shops show German VAT; Austrian checkout may add ~1 %.",
        "* Clone boards are fine for the PCA9685 (Adafruit 815 footprint), horns and fuse holders; buy genuine LiPo, LiDAR, Pi, regulator and UBECs (only genuine UBEC offers are listed).",
        "",
    ]
    (OUT / "shopping_list.md").write_text("\n".join(out))


def order_code(vendor: str, sku: str) -> str:
    """The code a shop's search or cart understands: ASIN, DigiKey -ND number, AliExpress item id, else
    the SKU text without notes in brackets."""
    for pattern, applies in (
        (ASIN, vendor == "amazon_de"),
        (DIGIKEY_PN, vendor == "digikey_at"),
        (ALIEXPRESS_ITEM, vendor == "aliexpress"),
    ):
        match = pattern.search(sku) if applies else None
        if match:
            return match.group(0)
    return sku.split(" (")[0].split(",")[0].strip()


def offer_link(vendor_info: dict, vendor: str, code: str) -> str:
    if vendor == "amazon_de" and ASIN.fullmatch(code):
        return f"https://www.amazon.de/dp/{code}"
    template = vendor_info.get("search")
    return template.replace("{q}", urllib.parse.quote(code)) if template else vendor_info.get("url", "")


def write_shop_data(data, strategies):
    """docs/bom/shop.json: every line with every offer (order code, link) and the four plans as offer choices,
    for the parts shop on the documentation site (docs-site/.../components/PartsShop.vue, shop/cart.ts)."""
    vendors = data["vendors"]
    lines = []
    for line in data["lines"]:
        offers = []
        for offer in line["offers"]:
            code = order_code(offer["vendor"], str(offer["sku"]))
            offers.append(
                {
                    "vendor": offer["vendor"],
                    "sku": str(offer["sku"]),
                    "variant": note.group(1) if (note := SKU_NOTE.search(str(offer["sku"]))) else None,
                    "code": code,
                    "price": offer["price"],
                    "pack": offer.get("pack", 1),
                    "status": offer["status"],
                    "stock": offer.get("stock"),
                    "genuine": offer.get("genuine", True),
                    "url": offer_link(vendors[offer["vendor"]], offer["vendor"], code),
                }
            )
        lines.append(
            {
                "id": line["id"],
                "name": line["name"],
                "category": line["category"],
                "qty": line["qty"],
                "note": line.get("note"),
                "optional": line["category"].startswith("Bench"),
                "cad": sorted(line.get("cad", {})),  # CAD part ids: product image /parts/<id>.png
                "offers": offers,
            }
        )
    plans = []
    for key, (label, result) in strategies.items():
        chosen = {line["id"]: offer for line, offer in result["chosen"]}
        plans.append(
            {
                "key": key,
                "letter": PLAN_GUIDE[key][0],
                "label": label,
                "guide": PLAN_GUIDE[key][1],
                "total": round(result["total"], 2),
                "shops": result["shops"],
                "choice": {line["id"]: line["offers"].index(chosen[line["id"]]) for line in data["lines"]},
            }
        )
    shop_vendors = {
        key: {
            "name": info["name"],
            "shipping": info["shipping"],
            "free_from": info.get("free_from"),
            "per_order_fee": info.get("per_order_fee", 0.0),
            "note": info.get("note"),
            "region": info.get("region"),
            "url": info.get("url"),
        }
        for key, info in vendors.items()
    }
    document = {
        "generated_by": "strido_publish.bom",
        "prices_observed": "2026-10-30",
        "vendors": shop_vendors,
        "lines": lines,
        "plans": plans,
    }
    (OUT / "shop.json").write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")


def product_problems(data, products) -> list[str]:
    """Ids hardware/products.yaml misses or has extra (against the BOM lines and the printed STLs) and
    wiki links to pages that do not exist."""
    expected = {
        "purchased": {line["id"] for line in data["lines"]},
        "printed": {stl.stem for stl in PRINTED_STL.glob("*.stl")},
    }
    problems = []
    for kind, ids in expected.items():
        have = set(products[kind])
        if have != ids:
            problems.append(f"{kind}: missing {sorted(ids - have)}, unknown {sorted(have - ids)}")
        for item_id, info in products[kind].items():
            problems += [
                f"{kind}.{item_id}: no wiki page docs/wiki/{slug}.md"
                for slug in info.get("learn", [])
                if not (WIKI / f"{slug}.md").is_file()
            ]
    return problems


def write_product_data(data):
    """docs/bom/products.json: shop-style information (summary, description, features, specs, role, wiki
    links) for every BOM line and every printed part; fails on any product_problems()."""
    products = yaml.safe_load(PRODUCTS.read_text())
    problems = product_problems(data, products)
    if problems:
        raise SystemExit(f"{PRODUCTS.name}: " + "; ".join(problems))
    (OUT / "products.json").write_text(json.dumps(products, indent=1, ensure_ascii=False) + "\n")
