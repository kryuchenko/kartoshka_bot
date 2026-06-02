#!/usr/bin/env python3
"""Жребий: случайно выбирает 3 криптоселектархов из откликнувшихся."""
import json
import random
from datetime import datetime, timezone

from kartoshka import config

TEST_IDS = {8560022133}  # тестовый @kwiatkovsky
N_WINNERS = 3

cands = json.load(open("candidates.json", encoding="utf-8"))
pool = [
    c for c in cands
    if c["id"] not in TEST_IDS and c["id"] not in config.EDITOR_IDS
]

print("Кандидатов в пуле:", len(pool))
for c in pool:
    uname = "@" + c["username"] if c.get("username") else "(без username)"
    print("  {}  {}  {}".format(c["id"], uname, c.get("first_name", "")))

k = min(N_WINNERS, len(pool))
winners = random.sample(pool, k)

print("\n=== ПОБЕДИТЕЛИ ЖРЕБИЯ ===")
for w in winners:
    uname = "@" + w["username"] if w.get("username") else "(без username)"
    print("  🥔 {}  {}  {}".format(w["id"], uname, w.get("first_name", "")))

result = {
    "drawn_at": datetime.now(timezone.utc).isoformat(),
    "pool_size": len(pool),
    "winners": winners,
}
with open("draw_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\nРезультат сохранён в draw_result.json")
