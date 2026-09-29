import random
import json
import numpy as np
import pandas as pd

def generate_nowcast_data(days=60):
    hospitals = [f"h_{i}" for i in range(8)]
    room_types = ["ER", "ICU", "Ward", "OR", "NICU"]
    
    data = []
    
    for h in hospitals:
        for r in room_types:
            capacity = random.randint(10, 50)
            current_occupancy = random.randint(0, capacity)
            
            for day in range(days):
                for hour in range(24):
                    # rate varies by hour (peaks at 9-11 and 18-20)
                    if 9 <= hour <= 11 or 18 <= hour <= 20:
                        lambda_arr = 2.0
                    else:
                        lambda_arr = 0.5
                        
                    arrivals = np.random.poisson(lambda_arr)
                    discharges = np.random.poisson(current_occupancy / 4.0) # avg 4h stay
                    
                    next_occupancy = max(0, min(capacity, current_occupancy + arrivals - discharges))
                    
                    # Store event
                    data.append({
                        "hospital_id": h,
                        "room_type": r,
                        "day": day,
                        "hour": hour,
                        "reported_free": capacity - current_occupancy,
                        "arrivals_next_1h": arrivals,
                        "discharges_next_1h": discharges,
                        "target_free_at_eta": capacity - next_occupancy
                    })
                    
                    current_occupancy = next_occupancy

    df = pd.DataFrame(data)
    df.to_csv("nowcast_train.csv", index=False)
    print(f"Generated {len(df)} nowcast events.")

    # Generate simulator params
    with open("hospital_params.json", "w") as f:
        json.dump({"hospitals": hospitals, "types": room_types}, f)

if __name__ == "__main__":
    generate_nowcast_data()
