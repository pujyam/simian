--[[
Copyright (c) 2015, Los Alamos National Security, LLC
All rights reserved.

Copyright 2015. Los Alamos National Security, LLC. This software was produced under U.S. Government contract DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), which is operated by Los Alamos National Security, LLC for the U.S. Department of Energy. The U.S. Government has rights to use, reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is modified to produce derivative works, such modified software should be clearly marked, so as not to confuse it with the version available from LANL.

Additionally, redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
	Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. 
	Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 
	Neither the name of Los Alamos National Security, LLC, Los Alamos National Laboratory, LANL, the U.S. Government, nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission. 
THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
]]

--[[
--Author: Nandakishore Santhi
--Date: 23 November, 2014
--Copyright: Open source, must acknowledge original author
--Purpose: JITed PDES Engine in LuaJIT
--  Main engine script
--]]
--[[
--Author: Christopher Hannon
--Date: 23 November, 2017
--Copyright: Open source, must acknowledge original authors
--Purpose: JITed PDES Engine in LuaJIT - Optimistic mode
--  Main engine script
--]]
jit.opt.start(3, 'hotloop=3', 'hotexit=8', 'instunroll=10', 'loopunroll=10', 'callunroll=10', 'recunroll=10', 'tryside=30') --Optional JIT optimization flags: user adjustable

local eventQ = require "eventQ"
local hash = require "hash"
local Entity = require "entity"

local Simian = {
    Entity = Entity
}

function Simian.init(self, simName, startTime, endTime, minDelay, useMPI)
    self.name = simName
    self.startTime = startTime
    self.endTime = endTime or 1e100
    self.minDelay = minDelay or 1
    self.useMPI = useMPI and true or false

    self.now = startTime

    --Status of JITing
    self.jitStatus = jit and jit.status() or false

    --If simulation is running
    self.running = false

    --Stores the entities available on this LP
    self.entities = {}

    --[[Events are stored in a priority-queue or heap, in increasing
    order of time field. Heap top can be accessed using self.eventQueue[1]
    event = {time, name, data, tx, txId, rx, rxId}.]]
    self.eventQueue = {}

    --[[Stores the minimum time of any event sent by this process,
    which is used in the global reduce to ensure global time is set to
    the correct minimum.]]
    self.infTime = endTime + 2*minDelay

    --Base rank is an integer hash of entity's name
    self.baseRanks = {}

    --Make things work correctly with and without MPI
    if self.useMPI then
        --Initialize MPI
        self.MPI = require "MPI"
        self.MPI:init()
        self.rank = self.MPI:rank()
        self.size = self.MPI:size()
    else
        self.rank = 0
        self.size = 1
    end

    --One output file per rank
    self.out = io.open(self.name .. "." .. self.rank .. ".out", "w")
    self.out:setvbuf("no")

    self.optimistic = 0
    self.optimisticGVT = 0
    self.optimisticLocalTime = 0

    self.optimisticCountRound = 0
    self.optimisticTMin = self.infTime
    self.optimisticWhite = 0
    self.optimisticColor = 1
    self.optimisticGVTNumTimesCalcd = 0
    self.optimisticGVTNumTimesCalc = (endTime-startTime)/10
    
end

function Simian.exit(self)
    if self.useMPI then --Exit only when all engines are ready
        self.out:flush()
        self.out:close()
        self.out = nil
        self.MPI:finalize()
    end
end

function Simian.run(self) --Run the simulation
    local startClock = os.clock()
    if self.rank == 0 then
        print("===========================================")
        print("----------SIMIAN JIT-PDES ENGINE-----------")
        print("===========================================")
        if self.jitStatus then
            print("JIT: ON")
        else
            print("JIT: OFF")
        end
        if self.useMPI then
            print("MPI: ON")
        else
            print("MPI: OFF")
        end
    end
    local numEvents, totalEvents, nwEvents, totalNWEvents = 0, 0, 0, 0

    local infTime, startTime, endTime, minDelay, rank, size, eventQueue, min
        = self.infTime, self.startTime, self.endTime, self.minDelay, self.rank, self.size, self.eventQueue, math.min

    self.running = true
    local MPI = self.MPI --Cache MPI locally
    local globalMinLeft = startTime
    if (self.optimistic) then
       while self.optimisticGVT < self.endTime do
	  while MPI:iprobe() do
	     local remoteEvent = MPI:recvAnySize()
	     if remoteEvent.GVT then
		self:optimisticGVT(remoteEvent)
	     else
                if not remoteEvent.antimessage and remoteEvent.color == 1 then
		self.optimisticWhite = self.optimisticWhite - 1
                end
                eventQ.push(eventQueue, remoteEvent)
	     end
	  end
	  if eventQueue[1] then
	     self:OptimisticProcessNextEvent()
	  else
	     if self.rank == 0 and self.optimisticColor then
		self:optimisticKickoffGVT()
	     end
	  end
       end
    else 
       while globalMinLeft <= endTime do --Exit loop only when global-epoch is past endTime
	  local epoch = globalMinLeft + minDelay

	  self.minSent = infTime --self.minSent is moded when entity.reqService is called
	  while eventQueue[1] and eventQueue[1].time < epoch do
	     event = eventQ.pop(eventQueue) --Next event
	     if self.now > event.time then --TODO: Out-of-order check: not needed in production code
                error("Out of order event: " .. self.now .. ", " .. event.time)
	     end
	     self.now = event.time --Advance time

	     --Simulate event
	     local entity = self.entities[event.rx][event.rxId]
	     --print(entity, self.entities[event.rx], event.rx, event.rxId)
	     local service = entity[event.name]
	     service(entity, event.data, event.tx, event.txId) --Receive
	     
	     numEvents = numEvents + 1
	  end
	  
	  if self.size > 1 then
	     local toRcvCount = MPI:alltoallSum()
	     while toRcvCount > 0 do --Recieve all expected events in next epoch
                MPI:probe()
                eventQ.push(eventQueue, MPI:recvAnySize())
                toRcvCount = toRcvCount - 1
	     end
	     local minLeft = (#eventQueue > 0) and eventQueue[1].time or infTime
	     globalMinLeft = MPI:allreduce(minLeft, MPI.MIN) --Synchronize minLeft
	     nwEvents = nwEvents + 2
	  else
	     globalMinLeft = (#eventQueue > 0) and eventQueue[1].time or infTime
	  end
       end
    end
    self.running = false
    if self.optimistic then
       MPI:barrier() --Forcibly synchronize all ranks before counting total events   
       totalEvents = MPI:allreduce(self.optimisticNumEvents, MPI.SUM)
       MPI:barrier() --Forcibly synchronize all ranks before counting total events   
       totalNWEvents = MPI:allreduce(nwEvents, MPI.SUM)
       MPI:barrier() --Forcibly synchronize all ranks before counting total events   
       totalREvents = MPI:allreduce(self.optimisticNumEventsRolledBack, MPI.SUM)
       --totalAntiEvents = MPI:allreduce(nwEvents, MPI.SUM)                          
       nwEvents = nwEvents + 3
    else   
       if self.size > 1 then
	  MPI:barrier() --Forcibly synchronize all ranks before counting total events
	  totalEvents = MPI:allreduce(numEvents, MPI.SUM)
	  totalNWEvents = MPI:allreduce(nwEvents, MPI.SUM)
	  nwEvents = nwEvents + 3
       else
	  totalEvents = numEvents
       end
    end
    if rank == 0 then
        local elapsedClock = os.clock() - startClock
        print("SIMULATION COMPLETED IN: " .. elapsedClock .. " SECONDS")
        print("SIMULATED EVENTS: " .. totalEvents)
        print("NETWORK EVENTS: " .. totalNWEvents)
        print("MODEL EVENTS PER SECOND: " .. totalEvents/elapsedClock)
        print("NET EVENTS PER SECOND: " .. (totalEvents+totalNWEvents)/elapsedClock)
	if self.optimistic then
	   print("EVENTS ROLLED BACK: " .. totalREvents)
	   print("ADJUSTED EVENTS: " .. totalEvents-totalREvents)
	   print("ADJUSTED EVENTS PER SECOND: " .. (totalEvents-totalREvents)/elapsedClock)
	   end
	print("===========================================")
    end
end

function Simian.optimisticSetup(self)
   --setup the entities initial saved state
   
end

function Simian.optimisticProcessNextEvent(self)
   --main function for executing next optimistic event
   local debug = 0
   local ent = self:getEntity(self.eventQueue[1].rx,self.eventQueue[1].rxId)

   if self.rank == 0 and self.optimisticColor and self.optimisticLocalTime >= self.optimisticGVTNumTimesCalcd*(self.endTime/self.optimisticGVTNumTimesCalc) then
      self.optimisticGVTNumTimesCalcd = self.optimisticGVTNumTimesCalcd + 1
      self:optimisticKickoffGVT()
   end
   
   local event = eventQ.pop(self.eventQueue)
   
   if self:optimisticRemove(event) then
      return
   else
      if event.antimessage then
	 --eventQ.push(self.eventQueue, event)
	 self:optimisticRollback(time)
	 if self:optimisticRemove(event) then
	    return
	 else
	    error("Annihilation / Rollback Error")
	 end
      else -- normal message
	 if self.optimisticLocalTime > time then
	    -- causality violated
	    --eventQ.push(self.eventQueue, event)
	    self:optimisticRollback(time)
	 end
	 state = ent:saveState()
	 self.optimisticLocalTime = time
	 local service = ent[event.name]
	 service(ent, event.data, event.tx, event.txId)

	 self.optimisticNumEvents = self.optimisticNumEvents + 1
	 ent.savedStates[#LP.savedStates + 1] = {event = event,
						 state = LP:saveAntimessages(state)
	 }
      end
   end
end

function Simian.optimisticRemove(self, event)
   local ret = false
   local otherEvents = {} -- events at the same time but not equivilent

   while #self.eventQueue > 0 do
      if self.eventQueue[1].time <= event.time then
	 poppedEvent = eventQ.pop(self.eventQueue)
	 if poppedEvent.tx == event.tx
	    and poppedEvent.txId == event.txId 
	    and poppedEvent.rx == event.rx
	    and poppedEvent.rxId == event.rxId
	    and poppedEvent.data == event.data
	    and poppedEvent.name == event.name
	    and poppedEvent.time == event.time
	 then
	    ret = true
            break
	 else
	    otherEvents[#otherEvents+1] = poppedEvent
	 end
      else
	 break
      end
   end
   for _,x in pairs(otherEvents) do
      eventQ.push(self.eventQueue, x)
   end
   return ret
end

function Simian.optimisticRollback(self, time)
   --return simulation state back to the time before causality error
   
end

function Simian.optimisticCalcGVT(self, event)
   --calculate GVT --
   local MPI = self.MPI

   if event.GVT_broadcast then
      self.optimisticGVT = event.GVT_broadcast
      self.optimisticColor = true
      --self:optimisticFossilCollect(event.GVT_broadcast)
      self.optimisticTMin = self.infTime
      return
   end
   if self.rank == 0 then -- root
      event.count = event.count + self.optimisticWhite
      if event.count == 0 and self.optimisticGVTRound > 0 then
	 self.optimisticGVT = math.min(event.m_clock,self.optimisticLocalTime,
				       event.m_send,self.optimisticTMin)
	 self.optimisticWhite=0
	 local rank = 1
	 while rank < self.size do
	    MPI:send({GVT=true,
		      GVT_broadcast = self.optimisticGVT,
		     },rank)
	 end
	 print("NEW GVT: ",self.optimisticGVT)
	 self.optimisticColor = true
	 self.optimisticTMin = self.infTime
	 --self.optimnisticFossil()
      
      else -- root but need to go around again
	 self.optimisticCountRound = 1
	 event.m_clock = self.optimisticLocalTime
	 event.m_send = math.min(event.m_send, self.optimisticTMin)
	 MPI:send(event,1)
	 self.optimisticWhite=0
      end
   else -- not origionator
      if self.optimisticColor then -- this means that the first time around
	 self.optimisticTMin = self.infTime
	 self.optimisticColor = false
      end
      local recvRank = self.rank + 1
      if recvRank == self.size then recvRank = 0; end
      MPI:send({m_clock = math.min(event.m_clock, self.optimisticLocalTime),
		m_send  = math.min(event.m_send, self.optimisticTMin),
		count   = event.count + self.optimisticWhite,
		GVT     = true,
		GVT_broadcast = nil,
	       },recvRank)
      self.optimisticWhite = 0
   end
end

function Simian.optimisticKickoffGVT(self)
   --start the non-blocking checkpoint algorithm
   self.optimisticGVTRound = 0
   self.optimisticColor = false

   local event = {m_clock = self.optimisticLocalTime,
		  m_send  = self.infTime,
		  count   = self.optimisticWhite,
		  GVT     = true,
		  GVT_broadcast = false,
   }
   self.MPI:send(event,1)
   self.optimisticWhite = 0
end

function Simian.optimisticFossilCollect(self)
   --remove fossilized saved states and memory
   -- not implemented --
   -- this should be its own thread in theory --
end
   
function Simian.schedService(self, time, eventName, data, rx, rxId)
    --[[Purpose: Add an event to the event-queue.
    --For kicking off simulation and waking processes after a timeout]]
    if time > self.endTime then --No need to push this event
        return
    end

    local recvRank = self:getOffsetRank(rx, rxId)

    if recvRank == self.rank then
        local e = {
            tx = nil, --String (Implictly self.name)
            txId = nil, --Number (Implictly self.num)
            rx = rx, --String
            rxId = rxId, --Number
            name = eventName, --String
            data = data, --Object
            time = time, --Number
	    GVT = false,
	    antimessage = false,
	}

        eventQ.push(self.eventQueue, e)
    end
end

function Simian.getBaseRank(self, name)
    --Can be overridden for more complex Entity placement on ranks
    return hash(name) % self.size
end

function Simian.getOffsetRank(self, name, num)
    --Can be overridden for more complex Entity placement on ranks
    return (self.baseRanks[name] + num) % self.size
end

function Simian.getEntity(self, name, num)
    --Returns a reference to a named entity of given serial number
    if self.entities[name] then
        local entity = self.entities[name]
        return entity[num]
    end
end

function Simian.attachService(self, klass, name, fun)
    --Attaches a service at runtime to an entity klass type
    rawset(klass, name, fun)
end

function Simian.addEntity(self, name, entityClass, num, ...)
    --[[Purpose: Add an entity to the entity-list if Simian is idle
    This function takes a pointer to a class from which the entities can
    be constructed, a name, and a number for the instance.]]
    if self.running then
        error("Adding entity when Simian is running!")
    end

    if not self.entities[name] then
        self.entities[name] = {} --To hold entities of this "name"
    end
    local entity = self.entities[name]

    self.baseRanks[name] = self:getBaseRank(name) --Register base-ranks
    local computedRank = self:getOffsetRank(name, num)

    if computedRank == self.rank then --This entity resides on this engine
        --Output log file for this Entity
        self.out:write(name .. "[" .. num .. "]: Running on rank " .. computedRank .. "\n")

        entity[num] = entityClass(name, self.out, self, num, ...) --Entity is instantiated
    end
end

return Simian
