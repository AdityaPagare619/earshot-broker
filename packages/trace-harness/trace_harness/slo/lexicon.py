"""FIXTURE multilingual lexicon for the SLO lab.

Every string in this file is a synthetic fixture, NOT a linguistic claim.
The lab's architectural claim (language-blind decisions) is carried by the
token-substitution test in tests/test_slo.py, never by the quality of these
strings. If you add a language, you add data here — zero code changes
elsewhere (that is the Household-Pack point).
"""
from __future__ import annotations

LANGS = ("en", "hi", "hi-Latn")

# Roles used across households.
OWNER, PARTNER, CHILD, ELDER, GUEST = "owner", "partner", "child", "elder", "guest"

# ---------------------------------------------------------------------------
# Secrets. Each has a topic, per-language text, per-language *secret-specific*
# keywords (words that must never appear in a generalized rendition), the roles
# it is kept from, a sensitivity, and per-role cleared depths.
# ---------------------------------------------------------------------------
SECRETS = (
    {
        "id": "sec-health",
        "topic": "health",
        "sensitivity": 0.95,
        "non_audience_roles": (ELDER, CHILD, GUEST),
        "clearance": {OWNER: 4, PARTNER: 4, ELDER: 3, CHILD: 1, GUEST: 0},
        "text": {
            "en": "Prenatal checkup at Cloudnine with Dr. Mehta, 3:40 pm",
            "hi": "डॉ. मेहता के साथ क्लाउडनाइन में प्रीनेटल जांच, दोपहर 3:40",
            "hi-Latn": "Dr. Mehta ke saath Cloudnine mein prenatal janch, dopahar 3:40",
        },
        "keywords": {
            "en": ("prenatal", "cloudnine", "mehta", "ob-gyn"),
            "hi": ("प्रीनेटल", "क्लाउडनाइन", "मेहता"),
            "hi-Latn": ("prenatal", "cloudnine", "mehta"),
        },
    },
    {
        "id": "sec-gift",
        "topic": "gift",
        "sensitivity": 0.7,
        "non_audience_roles": (CHILD, GUEST),
        "clearance": {OWNER: 4, PARTNER: 4, ELDER: 2, CHILD: 0, GUEST: 0},
        "text": {
            "en": "Instax camera ordered for Maya's birthday, arrives Thursday",
            "hi": "माया के जन्मदिन के लिए इंस्टैक्स कैमरा मंगवाया, गुरुवार को आएगा",
            "hi-Latn": "Maya ke janmdin ke liye Instax camera mangwaya, guruvaar ko aayega",
        },
        "keywords": {
            "en": ("instax", "birthday surprise", "maya's birthday"),
            "hi": ("इंस्टैक्स", "जन्मदिन"),
            "hi-Latn": ("instax", "janmdin"),
        },
    },
    {
        "id": "sec-finance",
        "topic": "finance",
        "sensitivity": 0.8,
        "non_audience_roles": (CHILD, GUEST),
        "clearance": {OWNER: 4, PARTNER: 3, ELDER: 1, CHILD: 0, GUEST: 0},
        "text": {
            "en": "Credit card bill overdue: Rs 18,400, pay before Friday",
            "hi": "क्रेडिट कार्ड बिल बकाया: 18,400 रुपये, शुक्रवार से पहले भरें",
            "hi-Latn": "Credit card bill bakaya: Rs 18,400, shukravaar se pehle bharein",
        },
        "keywords": {
            "en": ("overdue", "18,400", "credit card bill"),
            "hi": ("बकाया", "18,400"),
            "hi-Latn": ("bakaya", "18,400"),
        },
    },
    {
        "id": "sec-work",
        "topic": "work",
        "sensitivity": 0.85,
        "non_audience_roles": (PARTNER, CHILD, GUEST),
        "clearance": {OWNER: 4, PARTNER: 1, ELDER: 1, CHILD: 0, GUEST: 0},
        "text": {
            "en": "Job interview with Zepto, Friday 11 am, third round",
            "hi": "ज़ेप्टो के साथ नौकरी का इंटरव्यू, शुक्रवार सुबह 11 बजे",
            "hi-Latn": "Zepto ke saath naukri ka interview, shukravaar subah 11 baje",
        },
        "keywords": {
            "en": ("zepto", "job interview", "third round"),
            "hi": ("ज़ेप्टो", "इंटरव्यू"),
            "hi-Latn": ("zepto", "interview"),
        },
    },
)

TOPICS = tuple(s["topic"] for s in SECRETS)

# ---------------------------------------------------------------------------
# Public items (never secret). Seeded per day independently of secrets.
# ---------------------------------------------------------------------------
PUBLIC_ITEMS = (
    {"id": "pub-weather", "text": {
        "en": "Rain is forecast this evening.",
        "hi": "आज शाम बारिश का अनुमान है।",
        "hi-Latn": "Aaj shaam baarish ka anumaan hai."}},
    {"id": "pub-news", "text": {
        "en": "Markets closed flat today.",
        "hi": "आज बाज़ार सपाट बंद हुआ।",
        "hi-Latn": "Aaj bazaar sapaat band hua."}},
    {"id": "pub-standup", "text": {
        "en": "Team standup at ten in the morning.",
        "hi": "सुबह दस बजे टीम स्टैंडअप।",
        "hi-Latn": "Subah das baje team standup."}},
    {"id": "pub-groceries", "text": {
        "en": "Pick up groceries after five.",
        "hi": "पांच बजे के बाद किराना ले आना।",
        "hi-Latn": "Paanch baje ke baad kiraana le aana."}},
    {"id": "pub-dentist", "text": {
        "en": "Dental cleaning at ten, routine visit.",
        "hi": "सुबह दस बजे दांतों की सफाई, नियमित जांच।",
        "hi-Latn": "Subah das baje daanton ki safai, niyamit jaanch."}},
    {"id": "pub-school", "text": {
        "en": "Maya's school bus arrives at four.",
        "hi": "माया की स्कूल बस चार बजे आएगी।",
        "hi-Latn": "Maya ki school bus chaar baje aayegi."}},
)

# ---------------------------------------------------------------------------
# Generalization templates per depth per language. d4 = full text (the item's
# own text). These are the "boring templates" — a generalized rendition must
# never contain a secret-specific keyword (asserted in tests).
# ---------------------------------------------------------------------------
GENERALIZE = {
    "en": {
        3: "a doctor's appointment at {time}",
        2: "an appointment at {time}",
        1: "something on your calendar this afternoon",
    },
    "hi": {
        3: "{time} बजे डॉक्टर की अपॉइंटमेंट",
        2: "{time} बजे एक अपॉइंटमेंट",
        1: "आज दोपहर आपके कैलेंडर पर कुछ है",
    },
    "hi-Latn": {
        3: "{time} baje doctor ki appointment",
        2: "{time} baje ek appointment",
        1: "aaj dopahar aapke calendar par kuch hai",
    },
}

# The constant-shape fixed suffix, per language. Appended in cover mode even
# when nothing was withheld — that constancy is the mechanism.
FIXED_SUFFIX = {
    "en": "The rest of your day is on your phone.",
    "hi": "आपके दिन का बाकी हिस्सा आपके फ़ोन पर है।",
    "hi-Latn": "Aapke din ka baaki hissa aapke phone par hai.",
}

# v1-lattice EXISTENCE tell (the leak, fixture) and keyword-policy redaction.
V1_EXISTENCE_TELL = {
    "en": "One private item, sent to your phone.",
    "hi": "एक निजी आइटम, आपके फ़ोन पर भेजा गया।",
    "hi-Latn": "Ek niji item, aapke phone par bheja gaya.",
}
KEYWORD_REDACT = {
    "en": "I can't share details about that.",
    "hi": "मैं इसके बारे में जानकारी नहीं दे सकता।",
    "hi-Latn": "Main iske baare mein jaankaari nahin de sakta.",
}

# Deny-lists for the keyword baseline (per language). Deliberately leaky as a
# baseline should be: partial coverage, no morphology, no transliteration.
DENY_LISTS = {
    "en": ("prenatal", "cloudnine", "mehta", "instax", "overdue", "zepto",
           "interview", "credit card", "birthday"),
    "hi": ("प्रीनेटल", "क्लाउडनाइन", "मेहता", "इंस्टैक्स", "बकाया", "ज़ेप्टो",
           "इंटरव्यू", "जन्मदिन"),
    "hi-Latn": ("prenatal", "cloudnine", "mehta", "instax", "bakaya", "zepto",
                "interview", "janmdin"),
}

# Tell phrases the adversarial listener scores (v1 + keyword tells only — the
# sealed fixed suffix is constant by design and carries no signal).
TELL_PHRASES = {
    "en": ("private item", "can't share"),
    "hi": ("निजी आइटम", "जानकारी नहीं"),
    "hi-Latn": ("niji item", "jaankaari nahin"),
}


def secret_keywords(lang: str) -> tuple:
    """All secret-specific keywords for a language (listener vocabulary)."""
    out = []
    for s in SECRETS:
        out.extend(s["keywords"][lang])
    return tuple(out)


def topic_keywords(topic: str, lang: str) -> tuple:
    for s in SECRETS:
        if s["topic"] == topic:
            return s["keywords"][lang]
    raise KeyError(topic)
