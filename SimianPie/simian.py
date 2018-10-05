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
#Author: Christopher Hannon
#Date: 5 October, 2018
#Copyright: Open source, must acknowledge original author
#Purpose: PDES Engine in Python, mirroring a subset of the Simian JIT-PDES
#  Main simumation engine class

#NOTE: There are some user-transparent differences in SimianPie
#Unlike Simian, in SimianPie:
#   1. heapq API is different from heap.lua API
#       We push tuples (time, event) to the heapq heap for easy sorting.
#       This means events do not need a "time" attribute; however it is
#       still present for compatibility with Simian JIT.
#   2. hashlib API is diferent from hash.lua API
MPI = None
import hashlib, heapq

import time as timeLib

from utils import SimianError
from entity import Entity

import os
defaultMpichLibName = os.path.join(os.path.dirname(__file__), "..", "libmpich.dylib")
#print defaultMpichLibName

class Simian(object):
    def __init__(self, simName, startTime, endTime, minDelay=1, useMPI=False, mpiLibName=defaultMpichLibName, optimistic = False, optimisticGVTThreshold = 10):
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

        #Events are stored in a priority-queue or heap, in increasing
        #order of time field. Heap top can be accessed using self.eventQueue[0]
        #event = {time, name, data, tx, txId, rx, rxId}.
        self.eventQueue = []

        #Stores the minimum time of any event sent by this process,
        #which is used in the global reduce to ensure global time is set to
        #the correct minimum.
        self.infTime = endTime + 2*minDelay
        self.minSent = self.infTime

        #[[Base rank is an integer hash of entity's name]]
        self.baseRanks = {}

        #Make things work correctly with and without MPI
        if useMPI:
            #Initialize MPI
            try:
                global MPI
                from MPILib import MPI
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
                # need > 1 rank for optimistic
                self.optimistic = False

        self.optimisticGVT = 0
        self.optimisticNumAntimessagesSent = 0
        self.optimisticNumEventsRolledBack = 0
        self.optimisticNumEvents = 0

        self.optimisticCountRound = 0
        self.optimistic_t_min = self.infTime
        self.optimisticWhite = 0
        self.optimisticColor = "white"
        self.optimisticGVTThreshold = optimisticGVTThreshold
        self.optimisticGVTMemReq = 10
            
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

        ################################################################## 
        if self.optimistic: # Run in Optimistic Mode

            self.optimisticZeroQ()
            self.running = True
            self.optimisticGVT = self.startTime

            while self.optimisticGVT < self.endTime:
                while self.MPI.iprobe(): # True means event in queue
                    remoteEvent = self.MPI.recvAnySize()
                    if remoteEvent["GVT"]: # if message is a GVT calculation
                        self.optimisticCalcGVT(remoteEvent)
                    else: # event or anti-event
                        if not remoteEvent["antimessage"] and remoteEvent["color"] == "white":
                            self.optimisticWhite -= 1
                        heapq.heappush(self.eventQueue, (remoteEvent["time"], remoteEvent))
                if len(self.eventQueue):
                    print self.optimisticGVT
                    self.optimisticProcessNextEvent()
                else:
                    if self.rank == 0:
                        if self.optimisticColor == "white":
                            self.optimisticKickoffGVT()
        ################################################################## 

        ################################################################## 
        else: # Run in Conservative Mode
        
            self.running = True
            globalMinLeft = self.startTime
            while globalMinLeft < self.endTime:
                epoch = globalMinLeft + self.minDelay
                
                self.minSent = self.infTime
                while len(self.eventQueue) > 0 and self.eventQueue[0][0] < epoch:
                    (time, event) = heapq.heappop(self.eventQueue) #Next event
                    if self.now > time:
                        raise SimianError("Out of order event: now=%f, evt=%f" % self.now, time)
                    
                    self.now = time #Advance time

                    #Simulate event
                    entity = self.entities[event["rx"]][event["rxId"]]
                    service = getattr(entity, event["name"])
                    service(event["data"], event["tx"], event["txId"]) #Receive

                    numEvents = numEvents + 1

                if self.size > 1:
                    toRcvCount = self.MPI.alltoallSum()
                    while toRcvCount > 0:
                        self.MPI.probe()
                        remoteEvent = self.MPI.recvAnySize()
                        heapq.heappush(self.eventQueue, (remoteEvent["time"], remoteEvent))
                        toRcvCount -= 1
                        
                    minLeft = self.infTime
                    if len(self.eventQueue) > 0: minLeft = self.eventQueue[0][0]
                    globalMinLeft = self.MPI.allreduce(minLeft, self.MPI.MIN) #Synchronize m\inLeft
                else:
                    globalMinLeft = self.infTime
                    if len(self.eventQueue) > 0: globalMinLeft = self.eventQueue[0][0]
                            
        ################################################################## 

        self.running = False
        elapsedTime = timeLib.clock() - startTime
        
        # Gather and print stats        
        if self.optimistic:
            self.MPI.barrier()
            totalEvents = self.MPI.allreduce(self.optimisticNumEvents, self.MPI.SUM)
            self.MPI.barrier()
            rollEvents = self.MPI.allreduce(self.optimisticNumEventsRolledBack,self.MPI.SUM)
            self.MPI.barrier()
            antiEvents = self.MPI.allreduce(self.optimisticNumAntimessagesSent, self.MPI.SUM)
        else:
            if self.size > 1:
                self.MPI.barrier()
                totalEvents = self.MPI.allreduce(numEvents, self.MPI.SUM)
            else:
                totalEvents = numEvents

        if self.rank == 0:
            print "SIMULATION COMPLETED IN: " + str(elapsedTime) + " SECONDS"
            print "SIMULATED EVENTS: " + str(totalEvents)
            if self.optimistic:
                print ("NUMBER OF EVENTS ROLLED BACK %s " % (rollEvents))
                print ("NUMBER OF ANTIMESSAGES SENT %s " % (antiEvents))
                print ("ADJUSTED SIMULATED EVENTS: %s " % (totalEvents - rollEvents))
            if elapsedTime > 10.0**(-9):
                print "EVENTS PER SECOND: " + str(totalEvents/elapsedTime)
                if self.optimistic:
                    print ("ADJUSTED EVENTS PER SECOND: %s"
                           % ((totalEvents - rollEvents)/elapsedTime))
            else:
                print "EVENTS PER SECOND: Inf"
            print "==========================================="

    def optimisticZeroQ(self):
        for entType in self.entities:
            for ent in self.entities[entType]:
                en = self.entities[entType][ent]
                en.sentEvents =[]

    def optimisticProcessNextEvent(self):
        LP = self.getEntity(self.eventQueue[0][1]["rx"],self.eventQueue[0][1]["rxId"])
        if self.rank == 0 and ((len(LP.processedEvents) > self.optimisticGVTMemReq)
                               and self.optimisticColor == 'white'):
            self.optimisticKickoffGVT()
        (time, event) = heapq.heappop(self.eventQueue)
        if self.optimisticRemove(event): # event and counterpart are present in queue
            return
        # TODO: see if heuristic improves perfomance
        elif time > self.optimisticGVT + 5*self.optimisticGVTThreshold:
            heapq.heappush(self.eventQueue, (time, event))
            return
        else: # no inverse message in queue
            if event["antimessage"]: #rollback
                heapq.heappush(self.eventQueue, (time, event))
                self.optimisticRollback(time,LP)
            else:  # normal message
                if LP.VT > time: # causality violated
                    heapq.heappush(self.eventQueue, (time, event))
                    self.optimisticRollback(time,LP)
                else: # execute event
                    state = LP.saveState()
                    LP.VT = time
                    #entity = self.entities[event["rx"]][event["rxId"]]
                    entity = LP
                    service = getattr(entity, event["name"])
                    service(event["data"], event["tx"], event["txId"])
                    self.optimisticNumEvents += 1
                    LP.processedEvents.append((event,dict(LP.saveAntimessages(dict(LP.saveRandomState(state))))))
                        
    def optimisticRemove(self, event):
        ret = False
        otherEvents = []
        if event["antimessage"]:
            event["antimessage"] = False
        else:
            event["antimessage"] = True
        while len(self.eventQueue) and self.eventQueue[0][0] <= event["time"] :
            poppedEvent = heapq.heappop(self.eventQueue)
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
            heapq.heappush(self.eventQueue, x)
        return ret

    def optimisticRollback(self, time, LP):
        backup = False
        if time < self.optimisticGVT:
            raise SimianError("rollback before GVT!!!! GVT: %s , Event Queue Dump : %s"
                              % (self.optimisticGVT,self.eventQueue))
        if len(LP.processedEvents):
            while LP.processedEvents[len(LP.processedEvents)-1][0]["time"] >= time:
                (event,state) = LP.processedEvents.pop(-1)
                heapq.heappush(self.eventQueue, (event["time"], dict(event)))
                backup = dict(state)
                LP.recoverRandoms(state)
                LP.recoverAntimessages(state,time)
                self.optimisticNumEventsRolledBack += 1
                if not len(LP.processedEvents): break
        if backup:
            LP.recoverState(backup)
        LP.VT = time

    def optimisticKickoffGVT(self):
        self.optimisticCountRound = 0
        self.optimisticColor = 'red'
        LPVT = self.infTime
        for entType in self.entities:
            for ent in self.entities[entType]:
                en = self.entities[entType][ent]
                if en.VT < LPVT: LPVT = en.VT   # LPVT = min time
        if len(self.eventQueue): LPVT = min(LPVT,self.eventQueue[0][0])
        
        self.MPI.send({"m_clock" : LPVT,
                       "m_send"  : self.infTime,
                       "count"   : self.optimisticWhite,
                       "GVT"     : True,
                       "GVT_broadcast" : 0,
                       "rank"    : self.rank,
        },1) # send to rank 1
        self.optimisticWhite = 0
                
    
    def optimisticCalcGVT(self, event): # Based off Mattern 1993 ( with added broadcast )
        if event["GVT_broadcast"]:
            self.optimisticGVT = event["GVT_broadcast"]
            self.optimisticColor = 'white'
            self.optimisticFossilCollect(self.optimisticGVT)
            self.optimistic_t_min = self.infTime
            return
        else:
            LPVT = self.infTime # min LP's clock
            for entType in self.entities:
                for ent in self.entities[entType]:
                    en = self.entities[entType][ent]
                    if en.VT < LPVT:
                        LPVT = en.VT

            if len(self.eventQueue): LPVT = min(LPVT,self.eventQueue[0][0])

        if self.rank == 0: # initializer
            event["count"] += self.optimisticWhite
            if event["count"] == 0 and self.optimisticCountRound > 0:
                # finished calculating ( make sure it goes around at least once
                self.optimisticGVT = min(event["m_clock"],min(LPVT,min(event["m_send"],self.optimistic_t_min)))
                #self.optimisticGVT = min(event["m_clock"],LPVT)-1#,event["m_send"])
                if not self.optimisticGVT:
                    self.optimisticGVT = -0.000000001
                # broadcast new GVT
                self.optimisticWhite = 0
                for rank in xrange(self.size):
                    if not rank == self.rank:
                        self.MPI.send({"GVT" : True,
                                       "GVT_broadcast" : self.optimisticGVT,
                        } , rank)
                   
                #print ("GVT: %s" % self.optimisticGVT)
                self.optimisticColor = 'white'
                self.optimistic_t_min = self.infTime
                self.optimisticFossilCollect(self.optimisticGVT)
                
            else: # send around again
                self.optimisticCountRound += 1

                event["m_clock"] = LPVT
                event["m_send"]  = min(event["m_send"],self.optimistic_t_min)
                recvRank = self.rank + 1
                if recvRank == self.size : recvRank = 0
                self.MPI.send(event,recvRank)
                self.optimisticWhite = 0
                
        else: # not origionator
            if self.optimisticColor == 'white':
                self.optimistic_t_min = self.infTime
                self.optimisticColor = 'red'
                
            recvRank = self.rank + 1
            if recvRank == self.size : recvRank = 0
            
            msg = {"m_clock" : min(event["m_clock"], LPVT),
                   "m_send"  : min(event["m_send"] , self.optimistic_t_min),
                   "count"   : int(event["count"]) + self.optimisticWhite,
                   "GVT"     : True,
                   "GVT_broadcast" : 0,
            }
            self.MPI.send(msg,recvRank)
            self.optimisticWhite = 0

    def optimisticFossilCollect(self,time):
        for entityType in self.entities:
            for entity in self.entities[entityType]:
                e = self.entities[entityType][entity]
                for x,y in e.processedEvents:
                    if x["time"] < time:
                        e.processedEvents.remove((x,y))
                    else:
                        break
                                                                                                            
            
    def schedService(self, time, eventName, data, rx, rxId):
        #Purpose: Add an event to the event-queue.
        #For kicking off simulation and waking processes after a timeout
        if time > self.endTime: #No need to push this event
            return
        if self.partfct:
            recvRank = self.partfct(rx, rxID, self.size, self.partarg)
        else:
            recvRank = self.getOffsetRank(rx, rxId)

        if recvRank == self.rank:
            e = {
                "tx": None, #String (Implictly self.name)
                "txId": None, #Number (Implictly self.num)
                "rx": rx, #String
                "rxId": rxId, #Number
                "name": eventName, #String
                "data": data, #Object
                "time": time, #Number
                "antimessage": False,
                "GVT" : False,               
            }

            heapq.heappush(self.eventQueue, (time, e))

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
