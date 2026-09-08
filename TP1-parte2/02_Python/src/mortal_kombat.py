import random
import sys
import threading
import time
from collections import Counter


FIGHTERS = {
    "Liu Kang":    {"life": 100, "attack": 22, "defense": 10, "speed": 7,  "crit": 0.15, "block": 0.15},
    "Kung Lao":    {"life": 90,  "attack": 20, "defense": 8,  "speed": 9,  "crit": 0.20, "block": 0.10},
    "Johnny Cage": {"life": 95,  "attack": 24, "defense": 7,  "speed": 6,  "crit": 0.18, "block": 0.12},
    "Reptile":     {"life": 85,  "attack": 21, "defense": 9,  "speed": 8,  "crit": 0.15, "block": 0.15},
    "Sub-Zero":    {"life": 105, "attack": 19, "defense": 13, "speed": 5,  "crit": 0.10, "block": 0.20},
    "Shang Tsung": {"life": 90,  "attack": 23, "defense": 6,  "speed": 6,  "crit": 0.22, "block": 0.08},
    "Kitana":      {"life": 88,  "attack": 20, "defense": 8,  "speed": 10, "crit": 0.17, "block": 0.13},
    "Jax":         {"life": 120, "attack": 26, "defense": 12, "speed": 3,  "crit": 0.08, "block": 0.10},
    "Mileena":     {"life": 82,  "attack": 25, "defense": 5,  "speed": 9,  "crit": 0.25, "block": 0.05},
    "Baraka":      {"life": 110, "attack": 27, "defense": 11, "speed": 4,  "crit": 0.12, "block": 0.10},
    "Scorpion":    {"life": 100, "attack": 24, "defense": 9,  "speed": 7,  "crit": 0.20, "block": 0.12},
    "Raiden":      {"life": 92,  "attack": 22, "defense": 10, "speed": 8,  "crit": 0.16, "block": 0.18},
}

FIGHTER_NAMES = list(FIGHTERS.keys())
FIGHTERS_PER_TOURNAMENT = 8


def simulate_combat(name_a, name_b, rng):

    hp = {name_a: FIGHTERS[name_a]["life"], name_b: FIGHTERS[name_b]["life"]}

    speed_a = FIGHTERS[name_a]["speed"]
    speed_b = FIGHTERS[name_b]["speed"]
    if speed_a > speed_b:
        attacker, defender = name_a, name_b
    elif speed_b > speed_a:
        attacker, defender = name_b, name_a
    else:
        attacker, defender = (name_a, name_b) if rng.random() < 0.5 else (name_b, name_a)

    turns = 0
    while True:
        turns += 1
        def_stats = FIGHTERS[defender]
        atk_stats = FIGHTERS[attacker]

        if rng.random() < def_stats["block"]:
            damage = 0
        else:
            damage = max(1, atk_stats["attack"] - def_stats["defense"])
            if rng.random() < atk_stats["crit"]:
                damage *= 2

        hp[defender] -= damage
        if hp[defender] <= 0:
            return attacker, turns

        attacker, defender = defender, attacker


def simulate_tournament(rng):

    bracket = rng.sample(FIGHTER_NAMES, FIGHTERS_PER_TOURNAMENT)
    wins = Counter()
    total_turns = 0

    round_fighters = bracket
    while len(round_fighters) > 1:
        next_round = []
        for i in range(0, len(round_fighters), 2):
            winner, turns = simulate_combat(round_fighters[i], round_fighters[i + 1], rng)
            wins[winner] += 1
            total_turns += turns
            next_round.append(winner)
        round_fighters = next_round

    champion = round_fighters[0]
    return champion, total_turns, wins


def worker(seed, tournaments_to_run, result_slot):

    rng = random.Random(seed)
    total_turns = 0
    win_counts = Counter()
    championship_counts = Counter()

    for _ in range(tournaments_to_run):
        champion, turns, wins = simulate_tournament(rng)
        total_turns += turns
        win_counts.update(wins)
        championship_counts[champion] += 1

    result_slot["turns"] = total_turns
    result_slot["wins"] = win_counts
    result_slot["championships"] = championship_counts


def main():
    total_tournaments = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    num_threads = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    if total_tournaments <= 0 or num_threads <= 0:
        print("Tanto la cantidad de torneos como la de hilos deben ser enteros positivos.")
        sys.exit(1)

    base_share = total_tournaments // num_threads
    remainder = total_tournaments % num_threads
    shares = [base_share + (1 if i < remainder else 0) for i in range(num_threads)]

    seeding_rng = random.Random()
    seeds = [seeding_rng.random() for _ in range(num_threads)]

    results = [dict() for _ in range(num_threads)]
    threads = []

    start = time.perf_counter()

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(seeds[i], shares[i], results[i]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    elapsed = time.perf_counter() - start

    total_turns = sum(r["turns"] for r in results)
    total_wins = Counter()
    total_championships = Counter()
    for r in results:
        total_wins.update(r["wins"])
        total_championships.update(r["championships"])

    print(f"Torneos simulados: {total_tournaments}")
    print(f"Hilos usados: {num_threads}")
    print(f"Turnos de combate totales: {total_turns}")
    print("Victorias por luchador:")
    for name in FIGHTER_NAMES:
        print(f"  {name}: {total_wins.get(name, 0)}")
    print("Campeonatos por luchador:")
    for name in FIGHTER_NAMES:
        print(f"  {name}: {total_championships.get(name, 0)}")
    print(f"Tiempo total: {elapsed * 1000:.1f} ms")


if __name__ == "__main__":
    main()
