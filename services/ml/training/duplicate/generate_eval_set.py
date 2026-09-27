"""100-pair test set for duplicate-check precision/recall (technical.md §9.5).
Built from a template combinator: SCENARIOS x PHRASING_STYLE x LANGUAGE gives
real semantic diversity without hand-typing 100 one-off sentences. Duplicate
pairs = two phrasings of the same scenario, close in space/time.
Non-duplicate pairs = different scenarios (some deliberately close in space
or time only, to test the gate isn't fooled by proximity alone), or the same
scenario TYPE but different underlying incident (different family member /
different place), which text similarity alone would wrongly call a match."""

import json
import random

RNG = random.Random(7)
BASE_PUNE = (18.5204, 73.8567)

# Each scenario: (english_a, english_b_paraphrase, hindi, marathi, landmark)
SCENARIOS = [
    ("Father having severe chest pain, sweating a lot",
     "My dad is having bad chest pain and is sweating heavily",
     "पिताजी को सीने में तेज़ दर्द है और बहुत पसीना आ रहा है",
     "वडिलांना छातीत तीव्र वेदना होत आहेत आणि खूप घाम येत आहे", "near Ganesh temple Akurdi"),
    ("Road accident, two people injured, one unconscious",
     "There has been a road accident, 2 injured, one of them not responding",
     "सड़क दुर्घटना हुई है, दो लोग घायल हैं, एक बेहोश है",
     "रस्ता अपघात झाला आहे, दोन जण जखमी, एक बेशुद्ध", "on the Mumbai highway"),
    ("Mother having trouble breathing",
     "My mother is having difficulty breathing",
     "मेरी मां को सांस लेने में तकलीफ हो रही है",
     "आईला श्वास घ्यायला त्रास होत आहे", "near Akurdi market"),
    ("Woman in labour, contractions close together",
     "A pregnant woman is in labour, contractions are close",
     "एक गर्भवती महिला प्रसव पीड़ा में है, संकुचन करीब-करीब हो रहे हैं",
     "गरोदर स्त्री प्रसूतीत आहे, कळा जवळजवळ येत आहेत", "at home near the market"),
    ("Old man fell down stairs, cannot move his leg",
     "Elderly man fell down the stairs and cannot move his leg",
     "एक बुजुर्ग सीढ़ियों से गिर गया और अपना पैर नहीं हिला पा रहा",
     "म्हातारा माणूस जिन्यावरून पडला आणि पाय हलवू शकत नाही", "at Kothrud society"),
    ("Building fire, people trapped on second floor",
     "There's a fire in a building, some people trapped on the 2nd floor",
     "इमारत में आग लगी है, दूसरी मंजिल पर कुछ लोग फंसे हैं",
     "इमारतीला आग लागली आहे, दुसऱ्या मजल्यावर काही लोक अडकले आहेत", "near the railway station"),
    ("Child has fever and is vomiting",
     "My kid has a high fever and keeps vomiting",
     "बच्चे को बुखार है और उल्टी हो रही है",
     "मुलाला ताप आहे आणि उलटी होत आहे", "near Baner Balewadi"),
    ("Motorcycle skidded, rider bleeding from head",
     "Bike accident, rider is bleeding from the head",
     "मोटरसाइकिल फिसल गई, चालक के सिर से खून बह रहा है",
     "मोटारसायकल घसरली, चालकाच्या डोक्यातून रक्त वाहत आहे", "on MG road"),
    ("Person collapsed, not breathing normally",
     "Someone collapsed and is having trouble breathing",
     "एक व्यक्ति गिर गया है और ठीक से सांस नहीं ले पा रहा",
     "एक व्यक्ती कोसळली आहे आणि नीट श्वास घेत नाही", "at the market"),
    ("Snake bite victim, leg swelling fast",
     "A person was bitten by a snake, leg is swelling quickly",
     "एक व्यक्ति को सांप ने काट लिया है, पैर तेज़ी से सूज रहा है",
     "एका व्यक्तीला सापाने चावा घेतला आहे, पाय वेगाने सुजत आहे", "near a farm on Sinhagad road"),
    ("Elderly woman confused and slurring speech",
     "Grandmother is confused and her speech is slurred",
     "दादी भ्रमित हैं और उनकी बोली लड़खड़ा रही है",
     "आजी गोंधळलेली आहे आणि तिचे बोलणे अस्पष्ट आहे", "near Deccan Gymkhana"),
    ("Worker fell from scaffolding at construction site",
     "A construction worker fell from the scaffolding",
     "एक मजदूर निर्माण स्थल पर मचान से गिर गया",
     "एक कामगार बांधकाम साइटवर मचाणावरून पडला", "near Hinjewadi IT park"),
    ("Child swallowed something and is choking",
     "My child swallowed something and is choking",
     "मेरे बच्चे ने कुछ निगल लिया है और उसका दम घुट रहा है",
     "माझ्या मुलाने काहीतरी गिळले आहे आणि त्याचा गुदमरत आहे", "near Camp area"),
    ("Man burned by boiling water in the kitchen",
     "Someone got burned by hot water in the kitchen",
     "एक आदमी रसोई में उबलते पानी से जल गया",
     "एक माणूस स्वयंपाकघरात उकळत्या पाण्याने भाजला", "near Shivajinagar"),
    ("Cyclist hit by a car, leg possibly broken",
     "A cyclist was hit by a car, leg might be broken",
     "एक साइकिल चालक कार से टकरा गया, पैर टूटा हो सकता है",
     "एक सायकलस्वार कारने धडकला, पाय मोडलेला असू शकतो", "near Fergusson College road"),
]

# Non-duplicate distractor texts: different symptom in the same style, so text
# similarity alone might be fooled without the location/time gate.
DISTRACTORS = [
    "Neighbour having seizures, shaking uncontrollably",
    "Man complaining of severe stomach pain since morning",
    "Woman fainted after a wasp sting, swelling on the arm",
    "Teenager fell off a bicycle, arm looks dislocated",
    "Old woman found unconscious on the floor at home",
    "Worker exposed to chemical fumes at the factory",
    "Baby has been crying non-stop and feels very hot",
    "Man vomiting blood after a fight",
    "Woman went into shock after seeing a robbery",
    "Boy stuck his hand in a moving fan, bleeding badly",
]


def offset_location(base: tuple, dx_m: float, dy_m: float) -> dict:
    dlat = dy_m / 111320
    dlng = dx_m / (111320 * 0.9)
    return {"lat": base[0] + dlat, "lng": base[1] + dlng}


def main() -> None:
    pairs = []

    # 50 duplicate pairs: each scenario contributes ~3-4 paraphrase-pair combos
    combos = []
    for en_a, en_b, hi, mr, landmark in SCENARIOS:
        combos.append((en_a, en_b))       # english paraphrase
        combos.append((en_a, hi))          # cross-lingual en/hi
        combos.append((en_b, mr))          # cross-lingual en/mr
        combos.append((hi, mr))            # cross-lingual hi/mr
    RNG.shuffle(combos)
    for text_a, text_b in combos[:50]:
        dist_m = RNG.uniform(10, 480)      # within the 500m gate
        time_gap = RNG.uniform(20, 890)    # within the 15min gate
        pairs.append({
            "text_a": text_a, "text_b": text_b,
            "loc_a": offset_location(BASE_PUNE, 0, 0),
            "loc_b": offset_location(BASE_PUNE, dist_m, 0),
            "time_gap_sec": time_gap, "label": 1,
        })

    # 50 non-duplicate pairs
    non_dup = []
    scenario_texts = [s[0] for s in SCENARIOS]
    # a) different scenario, close in space/time (tests the gate isn't fooled by proximity)
    for i in range(20):
        a, b = RNG.sample(scenario_texts, 2)
        non_dup.append((a, b, RNG.uniform(10, 400), RNG.uniform(20, 800)))
    # b) same scenario TYPE, different incident far away (tests text similarity alone isn't enough)
    for i in range(15):
        a, _, hi, mr, _ = SCENARIOS[i % len(SCENARIOS)]
        non_dup.append((a, RNG.choice([hi, mr]), RNG.uniform(2000, 8000), RNG.uniform(600, 1200)))
    # c) scenario vs. an unrelated distractor, far apart
    for i in range(15):
        a = RNG.choice(scenario_texts)
        b = RNG.choice(DISTRACTORS)
        non_dup.append((a, b, RNG.uniform(1000, 6000), RNG.uniform(100, 900)))

    for text_a, text_b, dist_m, time_gap in non_dup:
        pairs.append({
            "text_a": text_a, "text_b": text_b,
            "loc_a": offset_location(BASE_PUNE, 0, 0),
            "loc_b": offset_location(BASE_PUNE, dist_m, 0),
            "time_gap_sec": time_gap, "label": 0,
        })

    RNG.shuffle(pairs)
    with open("services/ml/data/duplicate/eval_pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)
    n_dup = sum(1 for p in pairs if p["label"] == 1)
    print(f"wrote {len(pairs)} pairs ({n_dup} duplicate, {len(pairs) - n_dup} non-duplicate)")


if __name__ == "__main__":
    main()
