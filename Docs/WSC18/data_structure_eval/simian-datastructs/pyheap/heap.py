import pyheapq as heapq

def init(engine):
    return []

def size(arr):
    return len(arr)

def peak(arr):
    return arr[0]
    
def push(arr, item):
    heapq.heappush(arr,item)
    return

def pop(arr):
    return heapq.heappop(arr)
        
def annihilate(arr, event):
    ret = False
    otherEvents = []
    if event["antimessage"]:
        event["antimessage"] = False
    else:
        event["antimessage"] = True
    while len(arr) and arr[0][0] <= event["time"] :
        poppedEvent = heapq.heappop(arr)
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
        heapq.heappush(arr, x)
    return ret

def isEvent(arr):
    return len(arr)
