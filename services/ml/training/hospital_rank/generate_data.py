import random
import json
import numpy as np
import pandas as pd

def generate_hospital_rank_data(num_queries=10000):
    data = []
    
    for qid in range(num_queries):
        # Emergency context
        acuity = random.choice(["stable", "urgent", "critical"])
        fragility = random.choice(["low", "medium", "high"])
        
        num_candidates = random.randint(3, 10)
        candidates = []
        for cid in range(num_candidates):
            eta_sec = random.uniform(300, 1800)
            p_no_bed = random.uniform(0, 0.5)
            p_no_spec = random.uniform(0, 0.3)
            staleness = random.uniform(0, 60)
            road_comfort = random.uniform(40, 100)
            
            # utility calc
            reroute_delay = 900
            specialist_delay = 1800
            staleness_penalty = staleness * 10
            
            comfort_penalty = (100 - road_comfort) * (10 if fragility == "high" else 2)
            
            utility = eta_sec + (p_no_bed * reroute_delay) + (p_no_spec * specialist_delay) + staleness_penalty + comfort_penalty
            
            candidates.append({
                "query_id": qid,
                "hospital_id": f"h_{cid}",
                "eta_sec": eta_sec,
                "p_bed_available": 1 - p_no_bed,
                "staleness_min": staleness,
                "road_comfort": road_comfort,
                "utility": utility
            })
            
        # Assign relevance
        candidates.sort(key=lambda x: x["utility"]) # Lower utility is better
        n = len(candidates)
        for i, c in enumerate(candidates):
            # 0 to 4
            pct = i / n
            if pct < 0.2: rel = 4
            elif pct < 0.4: rel = 3
            elif pct < 0.6: rel = 2
            elif pct < 0.8: rel = 1
            else: rel = 0
            
            c["relevance"] = rel
            data.append(c)
            
    df = pd.DataFrame(data)
    df.to_csv("lambdarank_train.csv", index=False)
    print(f"Generated {len(df)} training rows for Hospital Rank.")

if __name__ == "__main__":
    generate_hospital_rank_data()
