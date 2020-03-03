import fibonacci_heap_mod
import heapq

# each LP has a Fibonacci Heap  and each
#  Rank (Simian Engine) has a Bin heap 

tierDict = {}
infTime = 0

class tier2():
    def __init__(self,key):
        self.key = key
        self.arr = fibonacci_heap_mod.Fibonacci_heap()
        
    def push(self, item):
        self.arr.enqueue(item,item[0])
        self.key = self.arr.min().m_priority
        
    def pop(self):
        e = self.arr.dequeue_min().m_elem
        if len(self.arr):
            self.key = self.arr.min().m_priority # update key
        else:
            self.key = infTime
        return e
    
    def peak(self):
        return self.arr.min().m_elem
    
    def size(self):
        return len(self.arr)

    def annihilate(self, event):
        ret = False
        otherEvents = []
        if event["antimessage"]:
            event["antimessage"] = False
        else:
            event["antimessage"] = True
        while self.isEvent() and self.peak()[0] <= event["time"] :
            poppedEvent = self.pop()
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
            self.push(x)
        return ret
    
    def isEvent(self):
        try:
            return self.arr.min()
        except IndexError:
            return False

    def __cmp__(self, o):
        return cmp(self.key, o.key)

## tier 1 
    
def init(engine):
    tier1 = []
    global infTime
    infTime = int(engine.infTime) + 1
    #for e in engine.entities:
    #    for x in engine.entities[e]:
    #        tierDict[(e,x)] = tier2(infTime)
    #        heapq.heappush(tier1,tierDict[(e,x)])
    return tier1

def push(arr, element):
    try:
        t = tierDict[(element[1]['rx'],element[1]['rxId'])] # tier2 obj
    except KeyError:
        tierDict[(element[1]['rx'],element[1]['rxId'])] = tier2(infTime)
        heapq.heappush(arr,tierDict[(element[1]['rx'],element[1]['rxId'])])
        t = tierDict[(element[1]['rx'],element[1]['rxId'])] # tier2 obj
        
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

def peak(arr):
    return arr[0].peak()

def isEvent(arr):
    if len(arr):
        return arr[0].isEvent()
    else:
        return None
    
def size(arr):
    ## TODO
    numEvents = 0
    for heap in arr:
        numEvents += heap.size()
    return numEvents
