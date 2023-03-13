# Online Python compiler (interpreter) to run Python online.
# Write Python 3 code in this online editor and run it.
import random

NUMSIMS = 10000

def sim_match(odds):
    return random.randint(0, 1000) < odds * 10

def get_odds(matches):
    # matches = [54.1, 100-65.3, 100-50.4, 59.8, 78.0, 76.5, 53.3, 53.1, 100-62.1, 56.1, 54.4]
    res = []
    for i in range(NUMSIMS):
        tournament = []
        for match in matches:
            tournament.append(sim_match(match))
        res.append(tournament)

    counts = [0 for i in range(len(matches) + 1)]
    for tournament in res:
        counts[tournament.count(True)] += 1
    odds = [count / NUMSIMS * 100 for count in counts]

    sum = 0
    total = 0
    for num, odd in enumerate(odds):
        sum += num * odd
        total += odd

    # print(f"{sum / total:.2f} average wins")
    return sum / total
