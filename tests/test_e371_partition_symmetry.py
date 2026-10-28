"""Exact combinatorial checks for E371, independent of live observations."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "e371_partition_symmetry",
    Path(__file__).resolve().parents[1] / "scripts" / "e371_partition_symmetry.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_all_valid_partitions_and_tied_optima():
    receipt = module.audit()
    assert len(receipt["valid_partitions"]) == 3
    assert receipt["optimal_pair_count"] == 1
    assert len(receipt["optimal_partitions"]) == 2
    assert receipt["reflection_fixed_optima"] == 0
    assert receipt["reflection_fixed_valid_pair_count"] == 0


def test_reflection_exchanges_optima_not_identity():
    edges = {frozenset((0, 1)), frozenset((1, 2))}
    options = [
        module.canonical(p)
        for p in module.partitions([0, 1, 2])
        if all(module.compatible(g, edges) for g in p)
    ]
    optimal = {p for p in options if module.score(p) == 1}
    reflect = {0: 2, 1: 1, 2: 0}
    assert len(optimal) == 2
    assert all(module.permute(p, reflect) in optimal for p in optimal)
    assert all(module.permute(p, reflect) != p for p in optimal)


def test_complete_and_empty_graph_controls():
    from itertools import combinations

    vertices = [0, 1, 2]
    complete = {frozenset(pair) for pair in combinations(vertices, 2)}
    all_partitions = [module.canonical(p) for p in module.partitions(vertices)]
    full = [p for p in all_partitions if all(module.compatible(g, complete) for g in p)]
    empty = [p for p in all_partitions if all(module.compatible(g, set()) for g in p)]
    assert len(full) == 5
    assert max(map(module.score, full)) == 3
    assert len(empty) == 1 and module.score(empty[0]) == 0
