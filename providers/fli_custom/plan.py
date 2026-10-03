"""Bounded multi-origin / multi-destination route planning (Issue #8).

The product of origins x destinations is capped so a flexible request can
never fan out into an unbounded number of upstream queries. Locally authored.
"""
from itertools import product
from typing import List, Tuple

MAX_ROUTES = 8


def bound_route_matrix(origins: List[str], destinations: List[str],
                       max_routes: int = MAX_ROUTES) -> List[Tuple[str, str]]:
    if not origins or not destinations:
        raise ValueError("origins and destinations must be non-empty")
    pairs = [(o.strip().upper(), d.strip().upper())
             for o, d in product(origins, destinations)]
    if len(pairs) > max_routes:
        raise ValueError(
            f"Route matrix has {len(pairs)} pairs; budget is {max_routes}")
    return pairs
