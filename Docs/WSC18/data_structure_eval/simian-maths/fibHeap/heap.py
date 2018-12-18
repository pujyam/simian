import fibonacci_heap_mod

def init(engine):
    return fibonacci_heap_mod.Fibonacci_heap()

def peak(arr):
    return arr.min().m_elem
    
def push(arr, item):
    arr.enqueue(item,item[0])
    return

def pop(arr):
    return arr.dequeue_min().m_elem

def size(arr):
    return len(arr)

def annihilate(arr, event):
    ret = False
    otherEvents = []
    if event["antimessage"]:
        event["antimessage"] = False
    else:
        event["antimessage"] = True
    while isEvent(arr) and peak(arr)[0] <= event["time"] :
        poppedEvent = pop(arr)
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
        push(arr, x)
    return ret

def isEvent(arr):
    try:
        return arr.min()
    except IndexError:
        return False
