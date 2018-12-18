import heapq

# each LP has a Binary Heap (heapq) and each
#  Rank (Simian Engine) has a heap of each LP

tierDict = {}
infTime = 0

class tier2():
    def __init__(self,key,lst):
        self.key = key
        self.arr = lst
        
    def push(self, item):
        heapq.heappush(self.arr, item)
        self.key = self.arr[0][0]
        
    def pop(self):
        e = heapq.heappop(self.arr)
        if len(self.arr):
            self.key = self.arr[0][0] # update key
        else:
            self.key = infTime
        return e
    
    def peak(self):
        if len(self.arr):
            return self.arr[0]
        else:
            return False

    def size(self):
        return len(self.arr)

    def annihilate(self, event):
        ret = False
        otherEvents = []
        if event["antimessage"]:
            event["antimessage"] = False
        else:
            event["antimessage"] = True
        while len(self.arr) and self.arr[0][0] <= event["time"] :
            poppedEvent = heapq.heappop(self.arr)
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
            heapq.heappush(self.arr, x)
        return ret
    
    def isEvent(self):
        return len(self.arr)

    def __cmp__(self, o):
        return cmp(self.key, o.key)
        
def init(engine):
    tier1 = []
    global infTime
    infTime = int(engine.infTime) + 1
    #for e in engine.entities:
    #    for x in engine.entities[e]:
    #        tierDict[(e,x)]=tier2(infTime,[])
    #        heapq.heappush(tier1,tierDict[(e,x)])        
    #heapq.heapify(tier1) # unneeded
    return tier1

def peak(arr):
    return arr[0].peak()

def push(arr, element):
    try :
        t = tierDict[(element[1]['rx'],element[1]['rxId'])] # time,q
    except KeyError:
        tierDict[(element[1]['rx'],element[1]['rxId'])]=tier2(infTime,[])
        heapq.heappush(arr,tierDict[(element[1]['rx'],element[1]['rxId'])])
        t = tierDict[(element[1]['rx'],element[1]['rxId'])] # time,q
    t.push(element)
    heapq.heapify(arr)
    
def pop(arr):
    tier = arr[0]
    e = tier.pop()
    heapq.heapify(arr)
    return e

def annihilate(arr, event):
    t = tierDict[(event['rx'],event['rxId'])] # time,q
    ret = t.annihilate(event)
    heapq.heapify(arr)
    return ret

def isEvent(arr):
    if len(arr):
        return arr[0].isEvent()
    else:
        return None
    
def size(arr):
    numEvents = 0
    for heap in arr:
        numEvents += heap.size()
    return numEvents
