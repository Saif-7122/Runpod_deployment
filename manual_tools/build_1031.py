"""plans_1031.json: 3 Meta ads. Hooks per the Hyderabad hooks codex (contrast, need call-out, bold number),
HOI voice (plain, calm, say the number, no urgency tricks, no "starting from"), one honest trade-off each,
brand type (hoi_en / hoi_te). Ad 1 carries the Kling clips (k1..k4). Shots were matched to meaning, not words:
"space for a farmhouse" shows a farmhouse on its land, never a bedroom."""
import json
from pathlib import Path

TAGS = ["OxygenForest", "Kamareddy", "ForestEstate", "FarmLand", "HyderabadRealEstate", "WeekendHome"]
CALL = "Call or WhatsApp +91 81217 77770."
CTA_EN, CTA_TE = "Contact us right now", "ఇప్పుడే సంప్రదించండి"


def S(beat, text, shots, overlay=""):
    return {"beat": beat, "text": text, "shots": shots, "overlay": overlay,
            **({"caption_style": "cta"} if beat == "cta" else {})}


def ad(title, lang, voice, angle, lines, caption):
    return {"language": lang, "voice": voice, "theme": "hoi_te" if lang == "te" else "hoi_en", "video_title": title,
            "angle": angle, "core_idea": angle, "target_seconds": 32.0, "duration_range": [24, 42],
            "post_caption": caption + "\n" + CALL, "hashtags": TAGS, "sentences": [S(*l) for l in lines],
            "allow_price_hook": True}


P = [
    ad("Your balcony faces a wall", "en", "en_main", "Problem aware: city flat vs forest estate (Kling for the city)", [
        ("hook", "Your balcony faces the next building's *wall*.", ["k1"]),
        ("context", "And your weekend starts in this.", ["k2"]),
        ("main", "Two hours from Hyderabad, *mornings* look like this.", ["k3"]),
        ("main", "Twenty-five thousand acres of protected forest around one gated community.", ["v035_5", "v029_7"]),
        ("main", "Each estate comes planted with *four hundred and fifty plus* fruit and timber trees.", ["w222"]),
        ("main", "A farm team waters them, seven days a week.", ["w208"]),
        ("proof", "Yes, it is two hours away. That distance is why the forest is *still standing*.", ["w006", "w218"]),
        ("payoff", "Registered land, clear title, and the papers shown *before* you commit.", ["w134"]),
        ("cta", "To get more details, *contact us* right now.", ["w216"], CTA_EN)],
        "Your balcony faces the next building's wall.\nTwo hours from Hyderabad: 25,000 acres of protected forest, "
        "450+ trees on every estate, a farm team seven days a week.\nRegistered land with clear title; papers before you commit."),
    ad("వీకెండ్‌లో మాల్‌కి కాకుండా", "te", "anusha", "Need call-out: what the weekend could be", [
        ("hook", "వీకెండ్‌లో మాల్‌కి కాకుండా, *ఇక్కడికి* వస్తే?", ["n070"]),
        ("context", "హైదరాబాద్ నుంచి 2 గంటల డ్రైవ్.", ["w029"]),
        ("main", "కామారెడ్డి దగ్గర 160 ఎకరాల *గేటెడ్* కమ్యూనిటీ.", ["w142"]),
        ("main", "పిల్లలు సైకిల్ తొక్కుతారు, దూడలకు మేత పెడతారు.", ["w056", "w217"]),
        ("main", "మధ్యాహ్నం భోజనం *ఇక్కడే* వండుతారు.", ["w051"]),
        ("main", "సాయంత్రం ఉయ్యాల, గడ్డి మీద కబుర్లు.", ["w199", "w191"]),
        ("proof", "మీరు లేనప్పుడు, ఫార్మ్ టీమ్ మీ 450 చెట్లకు నీళ్లు పోస్తుంది.", ["w054"]),
        ("payoff", "రిజిస్టర్డ్ ల్యాండ్, క్లియర్ టైటిల్. డాక్యుమెంట్లు *ముందే* చూపిస్తాం.", ["c013"]),
        ("cta", "మరిన్ని వివరాల కోసం, ఇప్పుడే మమ్మల్ని *సంప్రదించండి.*", ["w200"], CTA_TE)],
        "వీకెండ్‌లో మాల్‌కి కాకుండా, ఇక్కడికి వస్తే?\nహైదరాబాద్ నుంచి 2 గంటలు, కామారెడ్డి దగ్గర 160 ఎకరాల గేటెడ్ కమ్యూనిటీ.\n"
        "రిజిస్టర్డ్ ల్యాండ్, క్లియర్ టైటిల్."),
    ad("ఒక్క ఎస్టేట్‌లో 450 చెట్లు", "te", "maddy", "Bold number hook + honest trade-off", [
        ("hook", "ఒక్క ఎస్టేట్‌లో *450* చెట్లు.", ["w023"]),
        ("context", "ఎస్టేట్ సైజు 2,057 లేదా 3,630 చదరపు గజాలు.", ["v029_5"]),
        ("main", "చుట్టూ *25,000 ఎకరాల* రక్షిత అడవి.", ["v033_5"]),
        ("main", "ప్రతి ఎస్టేట్‌లో వాగులు, ఇంకుడు గుంత, స్వేల్స్.", ["v021_6"]),
        ("main", "ఫామ్‌హౌస్ కట్టుకోవడానికి *స్థలం* కూడా ఉంది.", ["w224"]),
        ("proof", "నిజమే, సిటీ నుంచి 2 గంటలు. ఆ దూరం వల్లే, అడవి ఇంకా *అడవిలానే* ఉంది.", ["w175", "w162"]),
        ("payoff", "మొత్తం 132 ఎస్టేట్లు, *ఒకే గేటు.*", ["w180"]),
        ("cta", "మరిన్ని వివరాల కోసం, ఇప్పుడే మమ్మల్ని *సంప్రదించండి.*", ["w052"], CTA_TE)],
        "ఒక్క ఎస్టేట్‌లో 450 చెట్లు.\nచుట్టూ 25,000 ఎకరాల రక్షిత అడవి, ఫామ్‌హౌస్‌కి స్థలం.\nమొత్తం 132 ఎస్టేట్లు, ఒకే గేటు."),
]
json.dump(P, open(Path(__file__).parent / "plans_1031.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(P), "plans")
