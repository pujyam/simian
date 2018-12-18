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
#  Named entity class with inheritence and processes
Process = None

from utils import SimianError

import types #Used to bind Service at runtime to specific instances

#Making this pythonic - this is a base class that all derived Entity classes will inherit from
class Entity(object):
    def __init__(self, initInfo):
        #Constructor of derived entity to be called as <entityName>(name, out, engine, num, reqServiceProxy, <args>)
        #Here <args> are any additional arguments needed in the derived entity-class's __init__() method
        self.name = initInfo["name"]
        self.out = initInfo["out"] #Log file for this instance
        self.engine = initInfo["engine"] #Engine
        self.num = initInfo["num"] #Serial Number
        self._procList = {} #A separate process table for each instance
        self._category = {} #A map of sets for each kind of process
        
        
        ## for optimistic
        self.VT = 0 # the LP's virtual time
        self.processedEvents=[]
        self.savedStates = []
        self.sentEvents = []
        ## for rands:
        self.randoms = {}
        self.recoveredRandoms = {}
        # for debugging
        self.allrand = [0]

        self.statisticsProcessedEvents = []
        self.statisticsWhoSendLP = {}
        self.statisticsWhoAntiLP = {}
        self.statisticsWhoSendRank = {}
        self.statisticsWhoAntiRank = {}
        self.statisticsFossilized = 0
        self.statisticsFPC = []
        
    def __str__(self):
        return self.name + "(" + str(self.num) + ")"

    def reqService(self, offset, eventName, data, rx=None, rxId=None):
        #Purpose: Send an event if Simian is running.
        engine = self.engine #Get the engine for this entity
        if not engine.optimistic:
            if rx != None and offset < engine.minDelay:
                if not engine.running: raise SimianError("Sending event when Simian is idle!")
                #If sending to self, then do not check against min-delay
                raise SimianError(self.name + "[" + str(self.num) + "]"
                                  + " attempted to send with too little delay")

        time = engine.now + offset
        if engine.optimistic:
            if offset == 0 :
                offset = 0.000000001 # add 1 nano unit
                #event can not create an event for the same time ( this resolution is debatable)
            time = self.VT + offset
        #print time
        if time > engine.endTime: 
            return
        
        if engine.optimistic_color == 'white':
            color = 'white'
        else:
            color = 'red'
        if rx == None: rx = self.name
        if rxId == None: rxId = self.num
        e = {
            "tx": self.name, #String
            "txId": self.num, #Number
            "rx": rx, #String
            "rxId": rxId, #Number
            "name": eventName, #String
            "data": data, #Object
            "time": time, #Number
            "antimessage" : False,
            "GVT" : False,
            "color" : color,
        }
        
        if engine.optimistic:
            ae = {
                "tx": self.name, #String
                "txId": self.num, #Number
                "rx": rx, #String
                "rxId": rxId, #Number
                "name": eventName, #String
                "data": data, #Object
                "time": time, #Number
                "antimessage" : True,
                "GVT" : False,
                "color" : color,
            }
            self.sentEvents.append(ae)
            
        # this is a particular mechanism added by Jason Liu for
        # allowing different mappings from LPs to ranks
        if engine.partfct:
            recvRank = engine.partfct(rx, rxId, engine.size, engine.partarg)
        else:
            recvRank = engine.getOffsetRank(rx, rxId)

        if engine.statistics:
            try:
                self.statisticsWhoSendLP[(rx,rxId)] += 1
                self.statisticsWhoSendRank[recvRank] += 1
            except KeyError:
                self.statisticsWhoSendLP[(rx,rxId)] = 1
                self.statisticsWhoSendRank[recvRank] = 1
                
        if recvRank == engine.rank: #Send to self
            engine.heap.push(engine.eventQueue, (time, e))
        else:
            if engine.optimistic:
                if engine.optimistic_color == 'white':
                    engine.optimistic_white += 1 # GVT approx algo
                else:
                    engine.optimistic_t_min = min(engine.optimistic_t_min, time)
                engine.MPI.send(e, recvRank)
            else:
                engine.MPI.sendAndCount(e, recvRank)
            
    def attachService(self, name, fun):
        #Attaches a service at runtime to instance
        setattr(self, name, types.MethodType(fun, self))

    #Following code is to support coroutine processes on entities:
    #Entity methods to interact with processes
    def createProcess(self, name, fun, kind=None): #Creates a named process
        global Process
        if not Process:
            from process import Process
        if name == "*":
            raise SimianError("Reserved name to represent all child processes: " + name)
        proc = Process(name, fun, self, None) #No parent means, entity is parent
        if not proc:
            raise SimianError("Could not create a valid process named: " + name)
        self._procList[name] = proc
        if kind != None:
            self.categorizeProcess(kind, name) #Categorize

    def startProcess(self, name, *args): #Starts a named process
        if name in self._procList:
            proc = self._procList[name]
            if not proc.started:
                proc.started = True
                #When starting, pass process instance as first arg, which can be accessed inside the "fun"
                return proc.wake(proc, *args)
            else:
                raise SimianError("Starting an already started process: " + proc.name)

    def _wakeProcess(self, name, tx=None, txId=None): #Hidden: implicit wake a named process without arguments
        if name in self._procList:
            proc = self._procList[name]
            proc.wake()

    def wakeProcess(self, name, *args): #Wake a named process with arguments
        if not (name in self._procList):
            raise SimianError("Attempted to wake a non existant process: " + name)
        else: #If existing and not been killed asynchronously
            proc = self._procList[name]
            proc.wake(*args)

    def killProcess(self, name): #Kills named process or all entity-processes
        if name: #Kills named child-process
            proc = self._procList[name]
            proc.kill() #Kill itself and all subprocesses
        else: #Kills all subprocesses
            for _,proc in self._procList.items(): #So we can delete while iterating
                proc.kill() #Kill itself and all subprocesses
            self._procList = {} #A new process table

    def killProcessKind(self, kind): #Kills all @kind processes on entity
        if not (kind in self._category):
            raise SimianError("killProcessKind: No category of processes on this entity called " + str(kind))
        else:
            nameSet = self._category[kind]
            for name,_ in nameSet.items(): #So we can delete while iterating
                proc = self._procList[name]
                proc.kill() #Kill itself and all subprocesses

    def statusProcess(self, name):
        if not (name in self._procList):
            return "NonExistent"
        else:
            proc = self._procList[name]
            return proc.status()

    def categorizeProcess(self, kind, name): #Check for existing process and then categorize
        if name in self._procList:
            proc = self._procList[name]
            #Categorize both ways for easy lookup
            proc._kindSet[kind] = True #Indicate to proc that it is of this kind to its entity
            #Indicate to entity that proc is of this kind
            if not kind in self._category: self._category[kind] = {name: True} #New kind
            else: self._category[kind][name] = True #Existing kind
        else: raise SimianError("categorize: Expects a proper child to categorize")

    def unCategorizeProcess(self, kind, name):
        #Check for existing process and then unCategorize
        if name in self._procList:
            proc = self._procList[name]
            #unCategorize both ways for easy lookup
            proc._kindSet.pop(kind) #Indicate to proc that it is not of this kind to its entity
            #Indicate to entity that proc is not of this kind
            if kind in self._category:
                self._category[kind].pop(name) #Existing kind deleted
        else: raise SimianError("unCategorize: Expects a proper child to un-categorize")

    def isProcess(self, name, kind):
        if name in self._procList:
            proc = self._procList[name]
            return proc.is_a(kind)
        else:
            return False

    def getProcess(self, name):
        #A reference to a named process is returned if it exists
        #NOTE: User should delete it to free its small memory when no longer needed
        if name in self._procList:
            proc = self._procList[name]
            return proc
        else: return None

    def getCategoryNames(self):
        kindSet = {}
        n = 1
        for k in self._category:
            kindSet[n] = k
            n = n + 1
        return kindSet

    def getProcessNames(self):
        nameSet = {}
        n = 1
        for k in self._procList:
            nameSet[n] = k
            n = n + 1
        return nameSet

    def saveAntimessages(self,state):
        state['antimessages'] = list(self.sentEvents)
        self.sentEvents = []
        return dict(state)

    def recoverAntimessages(self, state, time):
        engine = self.engine
        if state['antimessages']:
            events = state['antimessages']
            #print events
            for event in events:
                if engine.partfct:
                    recvRank = engine.partfct(event["rx"], event["rxId"], engine.size, engine.partarg)
                else:
                    recvRank = engine.getOffsetRank(event["rx"], event["rxId"])
                if recvRank == engine.rank: #Send to self
                    engine.heap.push(engine.eventQueue, (event["time"], event))
                else:
                    engine.MPI.send(event, recvRank)
                    engine.optimisticNumAntimessagesSent += 1
                if engine.statistics:
                    try:
                        self.statisticsWhoAntiLP[(event['rx'],event['rxId'])] += 1
                        self.statisticsWhoAntiRank[recvRank] += 1
                    except KeyError:
                        self.statisticsWhoAntiLP[(event['rx'],event['rxId'])] = 1
                        self.statisticsWhoAntiRank[recvRank] = 1
        else:
            return
        
    def saveRandomState(self,state):
        state['randoms'] = dict(self.randoms) # add random numbers
        self.randoms={} # reset randoms for next time
        return dict(state)

    def recoverRandoms(self, state):
        if state['randoms']:
            randoms = dict(state['randoms'])
            for m in randoms:
                if m in self.recoveredRandoms:
                    tmp = self.recoveredRandoms[m]
                    tmp += reversed(randoms[m])
                    self.recoveredRandoms[m] = tmp
                else:
                    self.recoveredRandoms[m] = randoms[m]
        else:
            return
            
    def random(self, method, *params):
        # this function seems like it works
        # retrieve random number or generate new one
        if method.__name__ in self.recoveredRandoms:
            # get last random
            r = self.recoveredRandoms[method.__name__]
            result = r.pop(-1)
            if r:
                self.recoveredRandoms[method.__name__] = r
            else: # no more events
                self.recoveredRandoms.pop(method.__name__)
        else: # no random history
            result = method(*params)
        # add to state for rollbacks
        if method.__name__ in self.randoms:
            tmp = self.randoms[method.__name__] 
            tmp.append(result)
            self.randoms[method.__name__] = tmp
        else:
            self.randoms[method.__name__] = [result]
        return result
