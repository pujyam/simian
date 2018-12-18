from ctypes import *

heaplib=CDLL('./libcheap.so')

n = c_int(1000000)
    

class heapData (Structure):
    _fields_ = [
        ("tx", c_char_p),
        ("txID", c_int),
        ("rx", c_char_p),
        ("rxID", c_int),
        ("name", c_char_p),
        ("data", c_char_p),
        ("time", c_float)]

class heapNode (Structure):
    _fields_ = [
        ("value", c_int),
        ("data", heapData )]
    
class PQ (Structure):
    _fields_ = [
        ("heap", (heapNode)*1000000),
        ("size", c_int)]



heaplib.enqueue.argtypes = [heapNode, POINTER(PQ)]
heaplib.dequeue.argtypes = [POINTER(PQ)]
heaplib.peak.argtypes = [POINTER(PQ)]
heaplib.initQueue.argtypes = [POINTER(PQ), c_int]

heaplib.enqueue.restype = None 
heaplib.dequeue.restype = heapNode
heaplib.peak.restype = heapNode
heaplib.initQueue.restype = None


def push(arr, element):
    hd = heapData()
    hd.tx = element[1]["tx"]
    hd.rx = element[1]["rx"]
    hd.txID = element[1]["txID"]
    hd.rxID = element[1]["rxID"]
    hd.name = element[1]["name"]
    hd.data = element[1]["data"]
    hd.time = element[0]#["time"]
    
    hn = heapNode()
    hn.value = element[0]
    hn.data = hd
    
    #heaplib.enqueue(byref(hn),arr)
    heaplib.enqueue(hn, byref(arr))

def pop(arr):
    print arr
    hn = heaplib.dequeue(byref(arr))
    '''#element = (hn.data.time,
               {
                   "tx" : hn.data.tx,
                   "rx" : hn.data.rx,
                   "rxID" : hn.data.rxID,
                   "txID" : hn.data.txID,
                   "name" : hn.data.name,
                   "data" : hn.data.data,
                   #"time" : hn.data.time,
               })
    return element
    '''
    
def init():
    pq = PQ()
    heaplib.initQueue(byref(pq) ,n)
    #print sizeof(pq)
    return pq
