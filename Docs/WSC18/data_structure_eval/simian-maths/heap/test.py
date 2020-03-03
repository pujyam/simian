import heapq
import random

queue = []
heapq.heapify(queue)

for i in range(1000):
    heapq.heappush(queue,random.random())

for i in range(1000):
    heapq.heappop(queue)



