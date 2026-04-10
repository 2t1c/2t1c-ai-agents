"""
Planned exercises per session type.
Used to pre-populate the Notion workout page at session start.
"""

SESSION_PLANS = {
    "Push A": [
        {"name": "Barbell Bench Press", "sets": "3 (RPT)", "target": "40kg×5 / 36kg×6-8 / 32kg×8-10"},
        {"name": "Incline DB Press",    "sets": "3×8-12",  "target": "~16kg"},
        {"name": "Dips",                "sets": "3×max",   "target": "BW (aim 8-15)"},
        {"name": "Lateral Raises",      "sets": "3×12-15", "target": ""},
        {"name": "Tricep Pushdowns",    "sets": "2×12-15", "target": ""},
        {"name": "Ab Wheel Rollout",    "sets": "3×8-12",  "target": "kneeling"},
        {"name": "Hanging Leg Raise",   "sets": "3×10-15", "target": "slow & controlled"},
        {"name": "Pallof Press",        "sets": "3×10/side","target": ""},
    ],
    "Pull A": [
        {"name": "Pull-ups",            "sets": "3 (RPT)", "target": "max / -1 / -2 reps"},
        {"name": "Barbell Row",         "sets": "3 (RPT)", "target": "49kg×5 / 44kg×6-8 / 40kg×8-10"},
        {"name": "Face Pulls",          "sets": "3×15-20", "target": ""},
        {"name": "DB Curl",             "sets": "2×10-12", "target": ""},
        {"name": "Front Lever Tuck Hold","sets": "3×10-20s","target": ""},
        {"name": "Dragon Flag Negatives","sets": "3×5-8",  "target": "slow eccentric"},
        {"name": "Dead Bug",            "sets": "3×10/side","target": ""},
        {"name": "L-Sit Hold",          "sets": "3×10-20s","target": ""},
    ],
    "Push B": [
        {"name": "Overhead Press",      "sets": "3 (RPT)", "target": "start light, build"},
        {"name": "Cable Flyes",         "sets": "3×12-15", "target": "squeeze at top"},
        {"name": "Ring / Decline Push-ups","sets": "3×max","target": ""},
        {"name": "Lateral Raises",      "sets": "3×12-15", "target": ""},
        {"name": "Overhead Tricep Extension","sets": "2×12-15","target": ""},
        {"name": "Ab Wheel Rollout",    "sets": "3×8-12",  "target": ""},
        {"name": "Hanging Knee/Leg Raise","sets": "3×12-15","target": ""},
        {"name": "Cable Woodchops",     "sets": "3×10/side","target": ""},
    ],
    "Pull B": [
        {"name": "Weighted Pull-ups",   "sets": "3 (RPT)", "target": "BW+0 to BW+5kg"},
        {"name": "DB Row",              "sets": "3×8-12",  "target": "each arm"},
        {"name": "Lat Pulldown",        "sets": "3×10-12", "target": "wide grip"},
        {"name": "Rear Delt Fly",       "sets": "3×15",    "target": ""},
        {"name": "Hammer Curl",         "sets": "2×10-12", "target": ""},
        {"name": "Hanging Leg Raise",   "sets": "3×10-15", "target": ""},
        {"name": "Pallof Press",        "sets": "3×10/side","target": ""},
        {"name": "RKC Plank",           "sets": "3×30-45s","target": "max tension"},
    ],
    "Swimming": [
        {"name": "Warm-up", "sets": "200m easy", "target": "freestyle"},
        {"name": "Main set (Zone 2)", "sets": "1500-2000m", "target": "conversational pace"},
        {"name": "Intervals (if energy)", "sets": "8×50m", "target": "30s rest between"},
        {"name": "Cool-down", "sets": "200m", "target": "easy backstroke"},
    ],
    "Football": [
        {"name": "Football session", "sets": "full game / training", "target": "counts as HIIT"},
    ],
    "Active Recovery": [
        {"name": "Light swim or walk", "sets": "20-30 min", "target": "zone 1"},
        {"name": "Mobility / stretching", "sets": "15 min", "target": ""},
        {"name": "Hanging from bar", "sets": "3×30-60s", "target": "spinal decompression"},
    ],
}
