# /*  Author Christopher Hannon
#  *  Date 12-30-17
#  *  Purpose interface to cffi heap
#  */

from _heap_i import ffi, lib

infTime = 0

# /* create heap */

def init():
    #global infTime
    #infTime = int(engine.infTime) + 1
    nn = 1000000#ffi.new("int")
    cheap = ffi.new("struct PQ *")
    lib.initQueue(cheap,ffi.cast("int",nn))
    return cheap

def push(arr, element):
    #hn = ffi.new("struct heapNode *")
    #value = element["time"]
    #hn.value = value

    #rx = ffi.new("char[]", element["rx"])
    #hn.data.rx = element["rx"]  
    #tx = ffi.new("char[]", element["tx"])
    #hn.data.tx = element["tx"]
    #txID = ffi.new("int", element["txID"])
    #hn.data.txID = element["txID"]
    #rxID = ffi.new("int", element["rxID"])
    #hn.data.rxID = element["rxID"]
    #name = ffi.new("int", element["name"])
    #hn.data.name = element["name"]
    
    #hn.data.time = value

    #result = lib.enqueue(hn, arr) 
    result = lib.enqueue(element, arr) 
    
def pop(arr):
    hn = lib.dequeue(arr)
    
    element = {"time": hn.value,
               "rx" : hn.data.rx,
               "tx" : hn.data.tx,
               "rxID" : hn.data.rxID,
               "txID" : hn.data.txID,
               "name" : hn.data.name,
               "data" : hn.data.data,
               }
    
    return element

def annihilate(arr, event):
    pass

def peak(arr):
    hn = lib.peak(arr)
    element = {"time": hn.value,
               "rx" : hn.data.rx,
               "tx" : hn.data.tx,
               "rxID" : hn.data.rxID,
               "txID" : hn.data.txID,
               "name" : hn.data.name,
               "data" : hn.data.data,
               }
    return element


def isEvent(arr):
    if arr.size:
        return 1
    else:
        return None
    
def size(arr):
    return arr.size
