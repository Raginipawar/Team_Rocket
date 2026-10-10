"""Real OSM edge attributes for road comfort (technical.md Section9.12).
Was a pure stub (get_comfort_for_nodes always returned a constant 75.0 for
every input, never touched real data). Loads the real Pune drive-network
graph via OSMnx (surface/highway-class/lit/traffic-calming tags) and scores
the nearest edge to a given point -- the graph is fetched once and cached
in memory for the process's lifetime (one real HTTP cost at first use, not
per request)."""

from functools import lru_cache

import osmnx as ox

PUNE_BBOX = (18.42, 73.72, 18.63, 73.97)  # south, west, north, east

# technical.md Section9.12's highway-class comfort tiers: faster, better-
# maintained road classes score higher.
HIGHWAY_CLASS_SCORE = {
    "motorway": 1.0, "trunk": 0.95, "primary": 0.85, "secondary": 0.75,
    "tertiary": 0.65, "unclassified": 0.5, "residential": 0.45,
    "living_street": 0.4, "track": 0.2, "path": 0.1,
}

SURFACE_SCORE = {
    "asphalt": 1.0, "concrete": 0.95, "paved": 0.9, "paving_stones": 0.7,
    "concrete:plates": 0.65, "compacted": 0.5, "gravel": 0.35, "unpaved": 0.3,
    "ground": 0.2, "dirt": 0.2, "sand": 0.15,
}
DEFAULT_SURFACE_SCORE = 0.6  # unknown/untagged -- neutral, not penalized for missing data


@lru_cache
def _load_graph():
    south, west, north, east = PUNE_BBOX
    return ox.graph_from_bbox((west, south, east, north), network_type="drive")


def _first(value, default=None):
    """OSM tags are sometimes a list (multiple values on one way) -- take the first."""
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def _score_edge(edge: dict) -> dict:
    highway = _first(edge.get("highway"), "unclassified")
    surface = _first(edge.get("surface"))
    lit = edge.get("lit") == "yes"
    has_traffic_calming = bool(edge.get("traffic_calming"))

    class_val = HIGHWAY_CLASS_SCORE.get(highway, 0.5)
    surface_val = SURFACE_SCORE.get(surface, DEFAULT_SURFACE_SCORE)
    smoothness_val = surface_val  # no separate OSM smoothness tag on most Pune ways -- derive from surface
    breakers_val = 0.3 if has_traffic_calming else 1.0  # traffic_calming present -> less comfortable, not a hard fact

    return {
        "surface": round(surface_val, 3), "smoothness": round(smoothness_val, 3),
        "class_val": round(class_val, 3), "breakers": round(breakers_val, 3),
        "lit": lit,
    }


class EdgesStore:
    def get_comfort_for_point(self, lat: float, lng: float) -> dict:
        graph = _load_graph()
        u, v, _key = ox.distance.nearest_edges(graph, lng, lat)
        edge = graph.get_edge_data(u, v)[0]
        return _score_edge(edge)

    def get_comfort_for_points(self, points: list[tuple[float, float]]) -> list[dict]:
        return [self.get_comfort_for_point(lat, lng) for lat, lng in points]
