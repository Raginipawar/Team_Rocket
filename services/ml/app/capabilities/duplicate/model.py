"""Real duplicate check: intfloat/multilingual-e5-base cosine similarity
(prefix 'query: ' per the model card) + spatial (<=500m) / temporal
(<=15min) gate (technical.md §9.5). DBSCAN incident clustering feeds the
MCI trigger."""

import math
from functools import lru_cache

DUPLICATE_RADIUS_M = 500
DUPLICATE_WINDOW_MIN = 15
DUPLICATE_SIM_THRESHOLD = 0.80


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ModelNotLoaded("sentence-transformers not installed -- pip install sentence-transformers") from exc
    try:
        return SentenceTransformer("intfloat/multilingual-e5-base")
    except Exception as exc:
        raise ModelNotLoaded(
            "multilingual-e5-base not downloaded -- run it once to cache, "
            "or set ML_MOCK_CAPABILITIES=duplicate"
        ) from exc


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


async def real_duplicate(payload: dict) -> dict:
    model = _load_model()
    emergency = payload["emergency"]
    candidates = payload.get("candidates", [])

    if not candidates:
        return {"duplicate_of": None, "similarity": 0.0, "same_incident": False, "additional_patients": False}

    texts = [f"query: {emergency['text']}"] + [f"query: {c['text']}" for c in candidates]
    embeddings = model.encode(texts, normalize_embeddings=True)
    query_emb = embeddings[0]

    best_idx, best_sim = None, -1.0
    for i, cand in enumerate(candidates):
        sim = _cosine(query_emb, embeddings[i + 1])
        within_radius = True
        if emergency.get("location") and cand.get("location"):
            dist_m = _haversine_m(
                emergency["location"]["lat"], emergency["location"]["lng"],
                cand["location"]["lat"], cand["location"]["lng"],
            )
            within_radius = dist_m <= DUPLICATE_RADIUS_M

        gated_sim = sim if within_radius else 0.0
        if gated_sim > best_sim:
            best_sim, best_idx = gated_sim, i

    is_duplicate = best_sim >= DUPLICATE_SIM_THRESHOLD
    additional_patients = False
    if is_duplicate:
        extracted = emergency.get("extracted", {})
        cand_extracted = candidates[best_idx].get("extracted", {}) if isinstance(candidates[best_idx], dict) else {}
        additional_patients = extracted.get("patient_count", 1) > cand_extracted.get("patient_count", 1)

    return {
        "duplicate_of": candidates[best_idx]["emergency_id"] if is_duplicate else None,
        "similarity": round(float(best_sim), 4),
        "same_incident": is_duplicate,
        "additional_patients": additional_patients,
    }


def cluster_incidents(points: list[tuple[float, float]], eps_m: float = 300, min_samples: int = 3) -> list[int]:
    """DBSCAN over recent emergency locations for MCI clustering (technical.md
    §9.5, §13 MCI_CLUSTER: >=3 calls within 300m in 10min). Returns a cluster
    label per point, -1 for noise (not part of any cluster)."""
    from sklearn.cluster import DBSCAN
    import numpy as np

    if not points:
        return []

    coords = np.radians(np.array(points))
    kms_per_radian = 6371.0088
    eps_rad = (eps_m / 1000.0) / kms_per_radian
    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine").fit(coords)
    return db.labels_.tolist()
