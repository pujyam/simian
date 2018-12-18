#Copyright (c) 2015, Los Alamos National Security, LLC
#All rights reserved.
#
#Copyright 2015. Los Alamos National Security, LLC. This software was produced under U.S. Government contract DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), which is operated by Los Alamos National Security, LLC for the U.S. Department of Energy. The U.S. Government has rights to use, reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is modified to produce derivative works, such modified software should be clearly marked, so as not to confuse it with the version available from LANL.
#
#Additionally, redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#	Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. 
#	Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 
#	Neither the name of Los Alamos National Security, LLC, Los Alamos National Laboratory, LANL, the U.S. Government, nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission. 
#THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#Author: Nandakishore Santhi
#Date: 23 November, 2014
#Copyright: Open source, must acknowledge original author
#Purpose: PDES Engine in Python, mirroring a subset of the Simian JIT-PDES
#  Main simumation engine class

#Author: Christopher Hannon
#

#NOTE: There are some user-transparent differences in SimianPie
#Unlike Simian, in SimianPie:
#   1. heapq API is different from heap.lua API
#       We push tuples (time, event) to the heapq heap for easy sorting.
#       This means events do not need a "time" attribute; however it is
#       still present for compatibility with Simian JIT.
#   2. hashlib API is diferent from hash.lua API

MPI = None

import hashlib

import time as timeLib

from utils import SimianError
from entity import Entity

from functools import wraps
from math import sqrt, floor, ceil

import os, sys

#defaultMpichLibName = os.path.join(os.path.dirname(__file__), "..", "libmpich.dylib")
#defaultMpichLibName = '/Users/channon/macports/lib/mpich-mp/libmpich.dylib'
#defaultMpichLibName = '/users/channon/software/mpich/lib/libmpich.so'
defaultMpichLibName = '/opt/local/lib/mpich-mp/libmpich.dylib'#mpicc-mpich-mp'

print defaultMpichLibName

global heap

def median(lst):
    lst_cnt = len(lst)
    mid_idx = int(lst_cnt / 2)
    if lst_cnt % 2 != 0:
        return lst[mid_idx]
    return (lst[mid_idx-1] + lst[mid_idx]) / 2
                      
def avg(lst):
    return float(sum(lst)/float(len(lst)))

def stddev(lst):
    mean = float(sum(lst)) / len(lst)
    return sqrt(float(reduce(lambda x, y: x + y, map(lambda x: (x - mean) ** 2, lst))) / len(lst))

def quartiles(lst):
    lst.sort()
    firstQ = median(lst[0:floor(len(lst)/2)])
    secondQ = median(lst)
    thirdQ = median(lst[ceil(len(lst)/2):])
    return (firstQ,secondQ,thirdQ)


class Simian(object):
    def __init__(self, simName, startTime, endTime, minDelay=1, useMPI=False, mpiLibName=defaultMpichLibName, optimistic = False, optimistic_GVT_Threshold = 1, customHeap = 'heap'):
        self.Entity = Entity #Include in the top Simian namespace

        self.name = simName
        self.startTime = startTime
        self.endTime = endTime
        self.minDelay = minDelay
        self.now = startTime
        
        #If simulation is running
        self.running = False

        #Stores the entities available on this LP
        self.entities = {}
          
        #Stores the minimum time of any event sent by this process,
        #which is used in the global reduce to ensure global time is set to
        #the correct minimum.
        self.infTime = endTime + 2 * minDelay
        self.minSent = self.infTime

        #[[Base rank is an integer hash of entity's name]]
        self.baseRanks = {}

        #Events are stored in a priority-queue or heap, in increasing
        #order of time field. Heap top can be accessed using self.eventQueue[0]
        #event = {time, name, data, tx, txId, rx, rxId}.
        #self.eventQueue = []
        
        self.heap = customHeap
        assert self.heap in ['heap', '2tHeapBin', '2tHeapFib', '2tHeapBinFib', '2tHeapFibBin', 'pyheap', 'fibHeap', 'calendarQ']#, '2tLadderQ', '3tHeap', 'ladderQ', 'splay']   

        try:
            global heap
            heap = getattr(__import__('%s.heap' % self.heap), 'heap')
            #heap = __import__('%s.heap' % self.heap) #, 'heap')
            self.heap = heap
            self.eventQueue = heap.init(self)
        except:
            raise SimianError("Can not find heap library: %s.heap" % self.heap)
        
        #Make things work correctly with and without MPI
        if useMPI:
            #Initialize MPI
            try:
                global MPI
                from MPILib import MPI
            except:
                raise("here")
            try:
                self.useMPI = True
                self.MPI = MPI(mpiLibName)
                self.rank = self.MPI.rank()
                self.size = self.MPI.size()
            except:
                raise SimianError("Please ensure libmpich is available to ctypes before using Simian for MPI based simulations.\nTry passing absolute path to libmpich.[dylib/so/dll] to Simian.")
        else:
            self.useMPI = False
            self.MPI = None
            self.rank = 0
            self.size = 1

        self.optimistic = optimistic

        if self.optimistic:
            if not self.useMPI or self.size == 1:
                self.optimistic = False # switch to conservative we need MPI and ranks > 1
        
        if self.rank == 0:
            print('using heap: %s' % self.heap)
            
        self.optimistic_GVT = 0
        self.optimisticNumAntimessagesSent = 0
        self.optimisticNumEventsRolledBack = 0
        self.optimisticNumEvents = 0

        self.optimistic_count_round = 0
        self.optimistic_t_min = self.infTime
        self.optimistic_white = 0
        self.optimistic_color = "white"
        self.optimistic_GVT_Threshold = optimistic_GVT_Threshold
        self.optimistic_GVT_mem_req = 10
        self.optimisticGVTNumTimesCalcd = 0
        self.optimisticGVTNumTimesCalc = (endTime-startTime)/300 # every 0.3%

        # statistic collection #
        self.statistics = 0
        
        if self.statistics:
            self.statsQSize = []
            self.statsAvgQSize = 0
            self.statsStdQSize = 0
            
            self.GVTCalcNum = 0
            
            #self.rollbackLength = []
            #self.avgRollbackLength = 0
            #self.stdRollbackLength = 0

            self.statsOpsLen = []
            self.statsAvgOpsLen = 0
            self.statsStdOpsLen = 0
            self.statsFirstQOpsLen,self.statsSecondQOpsLen,self.statsThirdQOpsLen = 0,0,0
            
            self.statsNumEnt = 0

            self.statsRecvEventsPerEnt = [] # reciever
            self.statsAvgRecvEventsPerEnt = 0
            self.ststsStdRecvEventsPerEnt = 0
            self.statsSendEventsPerEnt = [] # sender
            self.statsAvgSendEventsPerEnt = 0
            self.ststsStdSendEventsPerEnt = 0
            ## TODO USE quantiles???
            
        ## end statistics ##    
        
        #One output file per rank
        self.out = open(self.name + "." + str(self.rank) + ".out", "w")

        #Write some header information for each output file
        self.out.write("===========================================\n")
        self.out.write("----------SIMIAN-PIE PDES ENGINE-----------\n")
        self.out.write("===========================================\n")
        if self.useMPI:
            self.out.write("MPI: ON\n\n")
        else:
            self.out.write("MPI: OFF\n\n")

    def exit(self):
        sys.stdout.flush()
        self.out.close()
        del self.out

    def run(self): #Run the simulation
        startTime = timeLib.clock()
        
        if self.rank == 0:
            print("===========================================")
            print("----------SIMIAN-PIE PDES ENGINE-----------")
            print("===========================================")
            if self.useMPI:
                print("MPI: ON")
            else:
                print("MPI: OFF")
            if self.optimistic:
                print("Optimistic Mode Enabled")
            else:
                print("Conservative Mode Enabled")
        numEvents = 0

        if self.optimistic:
            # zero out sent event queues so that we dont annhialate accidentily the final message
            # print self.eventQueue
            self.optimistic_zero_q()
            self.running = True
            self.optimistic_GVT = self.startTime
            while self.optimistic_GVT < self.endTime:
                while self.MPI.iprobe(): # true means event in queue
                    remoteEvent = self.MPI.recvAnySize()
                    if remoteEvent["GVT"]: # if msg is a GVT calculation
                        #print 'gvt calc msg'
                        self.optimisticCalcGVT(remoteEvent)
                    else:  # event or anti-event
                        if not remoteEvent["antimessage"] and remoteEvent["color"] == "white" :
                            self.optimistic_white -= 1
                        heap.push(self.eventQueue, (remoteEvent["time"], remoteEvent))
                    
                if self.statistics:
                    self.statsQSize.append(heap.size(self.eventQueue))

                if heap.isEvent(self.eventQueue):
                    #print heap.size(self.eventQueue)
                    self.optimisticProcessNextEvent()
                else:
                    if self.rank == 0 :
                        if self.optimistic_color == 'white':
                            self.optimisticKickoffGVT()
                            
            self.running = False
            if self.rank == 0:
                elapsedTime = timeLib.clock() - startTime
        
        else: # conservative
            self.running = True
            globalMinLeft = self.startTime
            while globalMinLeft <= self.endTime:
                epoch = globalMinLeft + self.minDelay

                self.minSent = self.infTime

                if self.statistics:
                    self.statsQSize.append(heap.size(self.eventQueue))
                    
                while heap.isEvent(self.eventQueue) and heap.peak(self.eventQueue)[0] < epoch:
                    (time, event) = heap.pop(self.eventQueue) #Next event
                    if self.now > time:
                        raise SimianError("Out of order event: now=%f, evt=%f, eventQueue=%s" % (self.now, time, self.eventQueue))#heap.printCalinfo(self.eventQueue)))
                    self.now = time #Advance time
                    
                    #Simulate event
                    entity = self.entities[event["rx"]][event["rxId"]]
                    service = getattr(entity, event["name"])
                    service(event["data"], event["tx"], event["txId"]) #Receive
                    
                    numEvents = numEvents + 1

                if self.size > 1:
                    if self.statistics:
                        self.GVTCalcNum += 1
                    toRcvCount = self.MPI.alltoallSum()
                    while toRcvCount > 0:
                        self.MPI.probe()
                        remoteEvent = self.MPI.recvAnySize()
                        heap.push(self.eventQueue, (remoteEvent["time"], remoteEvent))
                        toRcvCount -= 1

                    minLeft = self.infTime
                    if heap.isEvent(self.eventQueue): minLeft = heap.peak(self.eventQueue)[0]
                    globalMinLeft = self.MPI.allreduce(minLeft, self.MPI.MIN) #Synchronize minLeft
                else:
                    globalMinLeft = self.infTime
                    if heap.isEvent(self.eventQueue): globalMinLeft = heap.peak(self.eventQueue)[0]
            self.running = False
            if self.rank == 0:
                elapsedTime = timeLib.clock() - startTime
            
        if self.optimistic: # get stats
            self.MPI.barrier()
            totalEvents = self.MPI.allreduce(self.optimisticNumEvents, self.MPI.SUM)
            self.MPI.barrier()
            rollEvents = self.MPI.allreduce(self.optimisticNumEventsRolledBack, self.MPI.SUM)
            self.MPI.barrier()
            antiEvents = self.MPI.allreduce(self.optimisticNumAntimessagesSent, self.MPI.SUM)
            
        else:
            if self.size > 1:
                self.MPI.barrier()
                totalEvents = self.MPI.allreduce(numEvents, self.MPI.SUM)
            else:
                totalEvents = numEvents   

        if self.statistics:
             self.getStats()                            
                
        if self.rank == 0:
            #elapsedTime = timeLib.clock() - startTime
            print "SIMULATION COMPLETED IN: " + str(elapsedTime) + " SECONDS"
            print "SIMULATED EVENTS: " + str(totalEvents)
            if self.optimistic:
                print ("NUMBER OF EVENTS ROLLED BACK %s " % (rollEvents))
                print ("NUMBER OF ANTIMESSAGES SENT %s " % (antiEvents))
                print ("ADJUSTED SIMULATED EVENTS: %s " % (totalEvents - rollEvents))
                
            if elapsedTime > 10.0**(-12):
                print "EVENTS PER SECOND: " + str(totalEvents/elapsedTime)
                if self.optimistic:
                    print ("ADJUSTED EVENTS PER SECOND: %s"
                           % ((totalEvents - rollEvents)/elapsedTime))
            else:
                print "EVENTS PER SECOND: Inf"
            print "==========================================="
            print '\n'
        if self.useMPI:
            self.MPI.barrier()

    def getStats(self):
        self.MPI.barrier()
            #if self.size > 1: # get rid of any pending events
            #    while self.MPI.iprobe():
            #        self.MPI.recvAnySize()
           
        if self.rank == 0:
                print("\n\nSTATISTICS FOR RUN\n")
            
        self.statsAvgQSize = avg(self.statsQSize)
        self.statsStdQSize = stddev(self.statsQSize)
            
        if self.optimistic:
            self.avgRollbackLength = avg(self.rollbackLength)
            self.stdRollbackLength = stddev(self.rollbackLength)

        self.statsAvgOpsLen = avg(self.statsOpsLen)
        self.statsStdOpsLen = stddev(self.statsOpsLen)
        self.statsFirstQOpsLen,self.statsSecondQOpsLen,self.statsThirdQOpsLen = quartiles(self.statsOpsLen)

        
        self.statsAvgRecvEventsPerEnt = avg(self.statsRecvEventsPerEnt)
        self.statsStdRecvEventsPerEnt = stddev(self.statsRecvEventsPerEnt)
        self.statsAvgSendEventsPerEnt = avg(self.statsSendEventsPerEnt)
        self.statsStdSendEventsPerEnt = stddev(self.statsSendEventsPerEnt)
           
        

        
        '''
        if self.size > 1:        
            if self.rank == 0:
                self.MPI.barrier()
                for x in range(self.size-1):
                    heapInfo = (self.MPI.recvAnySize())
                    print heapInfo
                    print('HEAP STATISTICS: \t RANK: %s \t AVG HEAP SIZE: %s \t STD HEAP SIZE: %s' % (heapInfo['rank'], heapInfo['avg'], heapInfo['std']))
                    if self.optimistic:
                        print("ROLLBACK STATISTICS: \t RANK %s \t AVG ROLLBACK DISTANCE: %s \t STD ROLLBACK DISTANCE: %s" % (heapInfo['rank'], heapInfo['ravg'], heapInfo['rstd']))

                
            else: # not rank 0
                if self.optimistic:
                    self.MPI.send({'avg': self.avgHeapSize,
                                   'std': self.stdHeapSize,
                                   'rank': self.rank,
                                   'ravg': self.avgRollbackLength,
                                   'rstd': self.stdRollbackLength},0)
                else:
                    self.MPI.send({'avg': self.avgHeapSize,
                                   'std': self.stdHeapSize,
                                   'rank': self.rank},0)
                self.MPI.barrier()
        
        if self.rank == 0:
            print('HEAP STATISTICS: \t RANK: %s \t AVG HEAP SIZE: %s \t STD HEAP SIZE: %s' % (0,self.avgHeapSize,self.stdHeapSize))
            if self.optimistic:
                print("ROLLBACK STATISTICS: \t RANK %s \t AVG ROLLBACK DISTANCE: %s \t STD ROLLBACK DISTANCE: %s" % (0,self.avgRollbackLength, self.stdRollbackLength))
            if self.size > 1:
                print('GVT STATS: \t TIMES COMPUTED: %s' % (self.GVTCalcNum))
        '''
        if self.rank == 0:
            print('HEAP STATISTICS:')
            sys.stdout.flush()
        self.MPI.barrier()
        for r in range(self.size):
            if self.rank == r:
                print('RANK: %s \t AVG HEAP SIZE: %.2f \t STDDEV HEAP SIZE: %.2f' % (self.rank,self.statsAvgQSize,self.statsStdQSize))
                sys.stdout.flush()
            self.MPI.barrier()

        if self.optimistic:
            if self.rank == 0:
                print('ROLLBACK STATISTICS:')
            self.MPI.barrier()
            for r in range(self.size):
                if self.rank == r:
                    print("RANK: %s \t TOTAL NUMBER OF ROLLBACKS %s \t AVG ROLLBACK DISTANCE: %.2f \t STDDEV ROLLBACK DISTANCE: %.2f" % (self.rank,self.optimisticNumEventsRolledBack,self.avgRollbackLength, self.stdRollbackLength))
                    sys.stdout.flush()
                self.MPI.barrier()
                
            if self.rank == 0:
                print('OPTIMISTIC STATISTICS:')
            self.MPI.barrier()
        for r in range(self.size):
            if self.rank == r:
                print('OVERHEAD FOR RANK %s' % self.rank)
                if self.optimistic:
                    for name in self.entities:
                        for num in self.entities[name]:
                            LP=self.entities[name][num]
                            print("LP: %s:%s \t AVG NUM SAVED STATES: %.2f \t STDDEV NUM SAVED STATES: %.2f" % (LP.name, LP.num, avg(LP.statisticsProcessedEvents), stddev(LP.statisticsProcessedEvents)))
                            sys.stdout.flush()
                    for name in self.entities:
                        for num in self.entities[name]:
                            LP=self.entities[name][num]
                            print("LP: %s:%s \t NUMBER OF FOSSILIZED EVENTS: %s \t AVG FOSSILIZATIONS PER COLLECTION: %.2f\t STDDEV FPC: %.2f"
                                  % (LP.name, LP.num, LP.statisticsFossilized, avg(LP.statisticsFPC), stddev(LP.statisticsFPC)))
                            sys.stdout.flush()
                    for name in self.entities:
                        for num in self.entities[name]:
                            LP=self.entities[name][num]
                            #print("LP: %s:%s \t LPS SENT TO: %s \t RANKS SENT TO: %s"
                            #      % (LP.name, LP.num, LP.statisticsWhoSendLP, LP.statisticsWhoSendRank))
                            print("LP: %s:%s \t NUM EVENTS SENT TO RANKS: %s \t NUM EVENTS WITHDRAWN %s" %(LP.name,LP.num, LP.statisticsWhoSendRank, LP.statisticsWhoAntiRank))
                            sys.stdout.flush()
                else:
                    for name in self.entities:
                        for num in self.entities[name]:
                            LP=self.entities[name][num]
                            #print("LP: %s:%s \t LPS SENT TO: %s \t RANKS SENT TO: %s"
                            #      % (LP.name, LP.num, LP.statisticsWhoSendLP, LP.statisticsWhoSendRank))
                            print("LP: %s:%s \t NUM EVENTS SENT TO RANKS: %s " %(LP.name,LP.num, LP.statisticsWhoSendRank))
                            sys.stdout.flush()
            self.MPI.barrier()
                
        if self.size > 1 and self.rank == 0:
            print('\nGVT STATS: \t TIMES COMPUTED: %s' % (self.GVTCalcNum))
            sys.stdout.flush()
            
    def optimistic_zero_q(self):
        for entType in self.entities:
            for ent in self.entities[entType]:
                en = self.entities[entType][ent]
                en.sentEvents =[]
                    
    def optimisticProcessNextEvent(self):
        LP = self.getEntity(heap.peak(self.eventQueue)[1]["rx"],heap.peak(self.eventQueue)[1]["rxId"])
        #print LP.VT
        #print float(self.calcLPVTMin())
        if self.rank == 0 and self.optimistic_color == 'white' :
            if self.calcLPVTMin() >= self.optimisticGVTNumTimesCalcd*(self.endTime/self.optimisticGVTNumTimesCalc):
                self.optimisticGVTNumTimesCalcd += 1
                self.optimisticKickoffGVT()
        (time, event) = heap.pop(self.eventQueue)
        if heap.annihilate(self.eventQueue , event): # event and counterpart are present in queue
            return
        # TODO: see if heuristic improves perfomance
        #elif time > self.endTime/50.0 + 1 + self.optimistic_GVT: #+ self.optimistic_GVT_Threshold: # TODO
        #    heap.push(self.eventQueue, (time, event))
        #    return
        else: # no inverse message in queue 
            if event["antimessage"]: #rollback
                heap.push(self.eventQueue, (time, event))
                self.optimisticRollback(time,LP)
            else:  # normal message
                if LP.VT > time: # causality violated
                    heap.push(self.eventQueue, (time, event))
                    self.optimisticRollback(time,LP)
                else: # execute event
                    if self.statistics:
                        eventStartTime = timeLib.time()
                    state = LP.saveState()
                    LP.VT = time
                    #entity = self.entities[event["rx"]][event["rxId"]]
                    entity = LP
                    service = getattr(entity, event["name"])
                    service(event["data"], event["tx"], event["txId"])
                    self.optimisticNumEvents += 1
                    LP.processedEvents.append((event,dict(LP.saveAntimessages(dict(LP.saveRandomState(state))))))
                    if self.statistics:
                        self.statsOpsLen.append(timeLib.time() - eventStartTime)
                        # mark recipient
                        # mark sender
                        LP.statisticsProcessedEvents.append(len(LP.processedEvents))
                        
    def optimisticRollback(self, time, LP):
        backup = False
        numRolls = 0
        if time < self.optimistic_GVT:
            raise SimianError("rollback before GVT!!!! GVT: %s , Event Queue Dump : %s"
                              % (self.optimistic_GVT,self.eventQueue))
        if len(LP.processedEvents):
            while LP.processedEvents[len(LP.processedEvents)-1][0]["time"] >= time:
                if self.statistics:
                    numRolls += 1
                (event,state) = LP.processedEvents.pop(-1)
                heap.push(self.eventQueue, (event["time"], dict(event)))
                backup = dict(state)
                LP.recoverRandoms(state)
                LP.recoverAntimessages(state,time)
                self.optimisticNumEventsRolledBack += 1
                if not len(LP.processedEvents): break

        if self.statistics:
            self.rollbackLength.append(numRolls)
                
        if backup:
            LP.recoverState(backup)
        LP.VT = time

    def calcLPVTMin(self):
        LPVT = self.infTime
        for entType in self.entities:
            for ent in self.entities[entType]:
                en = self.entities[entType][ent]
                #print en.VT
                if en.VT < LPVT: LPVT = en.VT
        #if heap.isEvent(self.eventQueue): LPVT = min(LPVT,heap.peak(self.eventQueue)[0])
        return LPVT
    
    def optimisticKickoffGVT(self):
        if self.statistics:
            self.GVTCalcNum += 1
            
        self.optimistic_count_round = 0
        self.optimistic_color = 'red'
        LPVT = self.infTime
        for entType in self.entities:
            for ent in self.entities[entType]:
                en = self.entities[entType][ent]
                if en.VT < LPVT: LPVT = en.VT   # LPVT = min time
        if heap.isEvent(self.eventQueue): LPVT = min(LPVT,heap.peak(self.eventQueue)[0])

        self.MPI.send({"m_clock" : LPVT,
                       "m_send"  : self.infTime,
                       "count"   : self.optimistic_white,
                       "GVT"     : True,
                       "GVT_broadcast" : 0,
                       "rank"    : self.rank,
        },1) # send to rank 1
        self.optimistic_white = 0
        
    def optimisticCalcGVT(self, event): # Based off Mattern 1993 ( with added broadcast )
        if event["GVT_broadcast"]:
            self.optimistic_GVT = event["GVT_broadcast"]
            self.optimistic_color = 'white'
            self.optimisticFossilCollect(self.optimistic_GVT)
            self.optimistic_t_min = self.infTime
            return
        else:
            LPVT = self.infTime # min LP's clock
            for entType in self.entities:
                for ent in self.entities[entType]:
                    en = self.entities[entType][ent]
                    #print 'en.VT: %s ' % en.VT
                    if en.VT < LPVT:
                        LPVT = en.VT
                        
            #if LPVT == 0: print self.eventQueue
                    
            if heap.isEvent(self.eventQueue): LPVT = min(LPVT,heap.peak(self.eventQueue)[0])

        if self.rank == 0: # initializer
            event["count"] += self.optimistic_white
            if event["count"] == 0 and self.optimistic_count_round > 0:# finished calculating ( make sure it goes around at least once
                self.optimistic_GVT = min(event["m_clock"],min(LPVT,min(event["m_send"],self.optimistic_t_min)))
                #self.optimistic_GVT = min(event["m_clock"],LPVT)-1#,event["m_send"])
                if not self.optimistic_GVT:
                    self.optimistic_GVT = -0.000000001
                # broadcast new GVT
                self.optimistic_white = 0
                for rank in xrange(1,self.size):
                    if not rank == self.rank:
                        self.MPI.send({"GVT" : True,
                                       "GVT_broadcast" : self.optimistic_GVT,
                        } , rank)
                print ("GVT: %.2f" % self.optimistic_GVT)
                self.optimistic_color = 'white'
                self.optimistic_t_min = self.infTime
                self.optimisticFossilCollect(self.optimistic_GVT)
                
            else: # send around again
                self.optimistic_count_round += 1

                event["m_clock"] = LPVT
                event["m_send"]  = min(event["m_send"],self.optimistic_t_min)
                recvRank = self.rank + 1
                if recvRank == self.size : recvRank = 0
                self.MPI.send(event,recvRank)
                self.optimistic_white = 0

        else: # not origionator
            if self.optimistic_color == 'white': 
                self.optimistic_t_min = self.infTime
                self.optimistic_color = 'red'

            recvRank = self.rank + 1
            if recvRank == self.size : recvRank = 0

            msg = {"m_clock" : min(event["m_clock"], LPVT),
                   "m_send"  : min(event["m_send"] , self.optimistic_t_min),
                   "count"   : int(event["count"]) + self.optimistic_white,
                   "GVT"     : True,
                   "GVT_broadcast" : 0,
            }
            #print 'm_clock: %s ' % msg['m_clock']
            #print 'm_send: %s ' % msg['m_send']
            #if msg['m_clock'] == 0: print self.eventQueue
            self.MPI.send(msg,recvRank)
            self.optimistic_white = 0  
    
    def optimisticFossilCollect(self, time):
        for entityType in self.entities:
            for entity in self.entities[entityType]:
                e = self.entities[entityType][entity]
                FPC = 0
                for x,y in e.processedEvents:
                    if x["time"] < time:
                        e.processedEvents.remove((x,y))
                        if self.statistics:
                            FPC += 1
                            e.statisticsFossilized += 1
                    else:
                        break
                if self.statistics:
                    e.statisticsFPC.append(FPC)
    
    def schedService(self, time, eventName, data, rx, rxId):
        #Purpose: Add an event to the event-queue.
        #For kicking off simulation and waking processes after a timeout
        if time > self.endTime: #No need to push this event
            return

        if self.partfct:
            recvRank = self.partfct(rx, rxId, self.size, self.partarg)
        else:
            recvRank = self.getOffsetRank(rx, rxId)

        if recvRank == self.rank:
            e = {
                "tx": rx,#self.name, #String (Implictly self.name)
                "txId": rxId,#self.num, #Number (Implictly self.num)
                "rx": rx, #String
                "rxId": rxId, #Number
                "name": eventName, #String
                "data": data, #Object
                "time": time, #Number
                "antimessage" : False,
                "GVT" : False,
                }
                
            heap.push(self.eventQueue, (time, e))

    def getBaseRank(self, name):
        #Can be overridden for more complex Entity placement on ranks
        return int(hashlib.md5(name).hexdigest(), 16) % self.size

    def getOffsetRank(self, name, num):
        #Can be overridden for more complex Entity placement on ranks
        val = (self.baseRanks[name] + num) % self.size
        return (self.baseRanks[name] + num) % self.size

    def getEntity(self, name, num):
        #Returns a reference to a named entity of given serial number
        if name in self.entities:
            entity = self.entities[name]
            if num in entity:
                return entity[num]

    def attachService(self, klass, name, fun):
        #Attaches a service at runtime to an entity klass type
        setattr(klass, name, fun)

    def addEntity(self, name, entityClass, num, *args, **kargs):
        #Purpose: Add an entity to the entity-list if Simian is idle
        #This function takes a pointer to a class from which the entities can
        #be constructed, a name, and a number for the instance.
        if self.statistics:
            self.statsNumEnt += 1 # statistic collection
            
        if self.running: raise SimianError("Adding entity when Simian is running!")

        if not (name in self.entities):
            self.entities[name] = {} #To hold entities of this "name"
        entity = self.entities[name]

        if 'partition' in kargs:
            self.partfct = kargs['partition']
            self.partarg = kargs.get('partition_arg')
        else:
            self.partfct = None
            self.partarg = None
            self.baseRanks[name] = self.getBaseRank(name) #Register base-ranks

        if self.partfct:
            computedRank = self.partfct(name, num, self.size, self.partarg)
        else:
            computedRank = self.getOffsetRank(name, num)
        if computedRank == self.rank: #This entity resides on this engine
            #Output log file for this Entity
            self.out.write(name + "[" + str(num) + "]: Running on rank " + str(computedRank) + "\n")

            entity[num] = entityClass({
                "name": name,
                "out": self.out,
                "engine": self,
                "num": num,
                }, *args) #Entity is instantiated
