import heapq
from copy import copy

# each LP has a Binary Heap (heapq) and each
#  Rank (Simian Engine) has a heap of each LP

tier2 = {}
infTime = 0

def init(engine):
    tier1 = []
    global infTime
    infTime = int(engine.infTime) + 1
    for e in engine.entities:
        for x in engine.entities[e]:
            tier2[(e,x)]=[infTime,[]]
            heapq.heappush(tier1,tier2[(e,x)])        
    #heapq.heapify(tier1) # unneeded
    return tier1

def peak(arr):
    if arr[0][0] < infTime:
        return arr[0][1][0]
    else:
        return False

def push(arr, element):
    t = tier2[(element[1]['rx'],element[1]['rxId'])] # time,q
    heapq.heappush( t[1], element )

    if t[0] > element[0]:
        t[0] = element[0]
    heapq.heapify(arr)
    
def pop(arr):
    tier = heapq.heappop(arr)
    element =  heapq.heappop(tier[1])
    if len(tier[1]):
        tier[0] = tier[1][0][0]
    else:
        tier[0] = infTime
    if not len(tier[1]):
        heapq.heappush( arr, [infTime, []])
    else:
        heapq.heappush( arr,tier)# [tier[1][0][0], tier[1]] )
    heapq.heapify(arr)
    return element

def annihilate(arr, event):
    t = tier2[(event['rx'],event['rxId'])][1] # time,q
    ret = False
    otherEvents = []
    if event["antimessage"]:
        event["antimessage"] = False
    else:
        event["antimessage"] = True
    while len(t) and t[0][0] <= event["time"] :
        poppedEvent = heapq.heappop(t)
        if poppedEvent[1] == event:
            ret = True
            break
        else:
            otherEvents.append(poppedEvent)
    if ret == False:
        if event["antimessage"]:
            event["antimessage"] = False
        else:
            event["antimessage"] = True
    for x in otherEvents:
        heapq.heappush(t, x)
    
    if len(t):
        tier2[(event['rx'],event['rxId'])][0] = t[0][0]# time,q
    else:
        tier2[(event['rx'],event['rxId'])][0] = infTime#t[0][0]# time,q
    heapq.heapify(arr)
    return ret


def isEvent(arr):
    if arr[0][0] < infTime:    
        return True
    else:
        return False
