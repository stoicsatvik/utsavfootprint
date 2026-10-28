"""E371: exact graph-symmetry audit of ambiguous three-report clustering.

This uses abstract pairwise compatibility, not measured waste identity. A valid
cluster is a clique; objective is to maximize within-cluster compatible pairs.
"""

from itertools import combinations


def partitions(items):
    """Enumerate all set partitions, independent of ordering."""
    if not items:
        yield ()
        return
    first, *rest = items
    for smaller in partitions(rest):
        yield ((first,),) + smaller
        for i, block in enumerate(smaller):
            yield smaller[:i] + ((first,) + block,) + smaller[i + 1 :]


def canonical(groups):
    return tuple(sorted(tuple(sorted(group)) for group in groups))


def compatible(group, edges):
    return all(frozenset(pair) in edges for pair in combinations(group, 2))


def score(groups):
    return sum(len(group) * (len(group) - 1) // 2 for group in groups)


def permute(groups, mapping):
    return canonical(tuple(tuple(mapping[x] for x in group) for group in groups))


def audit():
    # Three reports in a 0,100,200 m chain, with a 120 m all-pairs cap.
    vertices = (0, 1, 2)
    edges = {frozenset((0, 1)), frozenset((1, 2))}
    valid = sorted(
        {
            canonical(p)
            for p in partitions(list(vertices))
            if all(compatible(g, edges) for g in p)
        }
    )
    best_score = max(map(score, valid))
    optima = [p for p in valid if score(p) == best_score]
    reflection = {0: 2, 1: 1, 2: 0}
    fixed_optima = [p for p in optima if permute(p, reflection) == p]
    fixed_valid = [p for p in valid if permute(p, reflection) == p]
    assert len(valid) == 3
    assert len(optima) == 2 and best_score == 1
    assert not fixed_optima
    assert len(fixed_valid) == 1 and score(fixed_valid[0]) == 0
    return {
        "model": "abstract 3-node path compatibility graph",
        "synthetic_offsets_m": [0, 100, 200],
        "pairwise_cap_m": 120,
        "valid_partitions": [[list(group) for group in p] for p in valid],
        "optimal_pair_count": best_score,
        "optimal_partitions": [[list(group) for group in p] for p in optima],
        "reflection_fixed_optima": len(fixed_optima),
        "reflection_fixed_valid": len(fixed_valid),
        "reflection_fixed_valid_pair_count": score(fixed_valid[0]),
        "conclusion": (
            "No deterministic single-partition policy can be both reflection-equivariant "
            "and maximize grouped pairs on this symmetric path; abstention or additional "
            "evidence is required."
        ),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(audit(), sort_keys=True, indent=2))
