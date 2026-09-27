"""Extraction eval set with known ground truth (technical.md §9.2: 'field-level
accuracy on 200 hand-labelled transcripts'). This is synthetic, not the human-
labelled set the spec calls for -- ground truth here is simply the fields I
constructed the sentence from, which is legitimate for THIS capability (unlike
the triage holdout, nothing in §9.2 requires human labelling; the point of a
triage holdout is specifically to catch a model gaming its own training
distribution, which doesn't apply to a stateless per-utterance extraction
eval). Flagged honestly in REPORT.json as synthetic, not a substitute if the
team later wants a human-labelled version too."""

import json
import random

RNG = random.Random(99)

TEMPLATES = [
    # (template_en, template_hi_romanized, template_hi_deva, fields)
    ("My {rel} has severe chest pain and is sweating",
     "mere {rel_hi} ko seene mein bahut dard ho raha hai aur paseena aa raha hai",
     "मेरे {rel_hi_d} को सीने में बहुत दर्द हो रहा है और पसीना आ रहा है",
     {"symptoms": ["chest_pain", "sweating"], "breathing": None, "bleeding": "none", "conscious": None}),
    ("My {rel} fell down and is bleeding heavily from the head, not responding",
     "mera {rel_hi} gir gaya hai aur sar se bahut khoon beh raha hai, hosh mein nahi hai",
     "मेरा {rel_hi_d} गिर गया है और सर से बहुत खून बह रहा है, होश में नहीं है",
     {"symptoms": [], "breathing": None, "bleeding": "severe", "conscious": False, "mechanism": "fall"}),
    ("My {rel} is having trouble breathing and lips are turning blue",
     "mere {rel_hi} ko saans lene mein takleef ho rahi hai aur hoth neele pad rahe hain",
     "मेरे {rel_hi_d} को सांस लेने में तकलीफ हो रही है और होंठ नीले पड़ रहे हैं",
     {"symptoms": ["breathlessness"], "breathing": "difficult", "bleeding": "none", "conscious": True}),
    ("My {rel} was in a road accident, unconscious, bleeding from the leg",
     "mera {rel_hi} sadak durghatna mein hai, behosh hai, pair se khoon beh raha hai",
     "मेरा {rel_hi_d} सड़क दुर्घटना में है, बेहोश है, पैर से खून बह रहा है",
     {"symptoms": [], "breathing": None, "bleeding": "mild", "conscious": False, "mechanism": "road_accident"}),
    ("I am pregnant and having contractions, they are close together",
     "main pregnant hoon aur mujhe labour pain ho raha hai, contractions paas paas aa rahe hain",
     "मैं गर्भवती हूं और मुझे प्रसव पीड़ा हो रही है, संकुचन पास पास आ रहे हैं",
     {"symptoms": ["labour_pain"], "pregnant": True, "breathing": None, "bleeding": "none", "conscious": True}),
    ("My {rel} drank some chemical by mistake and is vomiting",
     "mere {rel_hi} ne galti se koi chemical pi liya hai aur ulti kar raha hai",
     "मेरे {rel_hi_d} ने गलती से कोई रसायन पी लिया है और उल्टी कर रहा है",
     {"symptoms": ["vomiting"], "mechanism": "poisoning", "breathing": None, "bleeding": "none", "conscious": True}),
    ("My {rel} was burned by hot water in the kitchen, screaming in pain",
     "mere {rel_hi} ka haath garam pani se jal gaya hai, dard se chilla raha hai",
     "मेरे {rel_hi_d} का हाथ गरम पानी से जल गया है, दर्द से चिल्ला रहा है",
     {"symptoms": ["burn_pain"], "mechanism": "burn", "breathing": None, "bleeding": "none", "conscious": True}),
    ("My {rel} is an old man, confused and his speech is slurred since morning",
     "mere {rel_hi} bujurg hain, subah se confused hain aur unki baat lardkhadaa rahi hai",
     "मेरे {rel_hi_d} बुजुर्ग हैं, सुबह से भ्रमित हैं और उनकी बात लड़खड़ा रही है",
     {"symptoms": ["confusion", "slurred_speech"], "breathing": None, "bleeding": "none", "conscious": True}),
]

RELATIONS = [
    ("father", "papa", "पापा", "M"), ("mother", "mummy", "मम्मी", "F"),
    ("brother", "bhai", "भाई", "M"), ("son", "bete", "बेटे", "M"), ("husband", "pati", "पति", "M"),
]


def main() -> None:
    samples = []
    for template_en, template_hi_rom, template_hi_deva, fields in TEMPLATES:
        for rel_en, rel_hi, rel_hi_d, sex in RELATIONS:
            base_fields = {**fields, "for_whom": rel_en, "sex": sex, "patient_count": 1, "pregnant": fields.get("pregnant", False)}
            samples.append({"text": template_en.format(rel=rel_en), "language": "en", "true": dict(base_fields)})
            samples.append({"text": template_hi_rom.format(rel_hi=rel_hi), "language": "hi", "true": dict(base_fields)})
            samples.append({"text": template_hi_deva.format(rel_hi_d=rel_hi_d), "language": "hi", "true": dict(base_fields)})

    RNG.shuffle(samples)
    samples = samples[:120]
    with open("services/ml/data/extraction/eval_set.json", "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(samples)} samples")


if __name__ == "__main__":
    main()
