def calculateMaxSatisfaction(N, satisfaction):
    a = sorted(satisfaction, reverse=True)
    s = 0
    t = 0
    for v in a:
        if v + s > 0:
            t += v + s
            s += v
    return t

n = int(input())
satisfaction = list(map(int, input().split()))
print(calculateMaxSatisfaction(n, satisfaction))