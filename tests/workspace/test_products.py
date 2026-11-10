"""Every part the shop and print kit sell has a product page, and its Learn links resolve."""

import yaml

from strido.workspace import path
from strido_publish.shopping import PRODUCTS, product_problems


def test_product_information_covers_every_bom_line_and_printed_part():
    data = yaml.safe_load(path("hardware/bom.yaml").read_text())
    products = yaml.safe_load(PRODUCTS.read_text())
    assert product_problems(data, products) == []


def test_a_missing_part_and_a_dead_wiki_link_are_reported():
    data = yaml.safe_load(path("hardware/bom.yaml").read_text())
    products = yaml.safe_load(PRODUCTS.read_text())
    removed = data["lines"][0]["id"]
    del products["purchased"][removed]
    products["printed"]["femur"]["learn"] = ["hardware/no-such-page"]
    problems = product_problems(data, products)
    assert any(removed in problem and "missing" in problem for problem in problems)
    assert "printed.femur: no wiki page docs/wiki/hardware/no-such-page.md" in problems
