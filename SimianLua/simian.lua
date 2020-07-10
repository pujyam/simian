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
jit.opt.start(3, 'hotloop=3', 'hotexit=8', 'instunroll=10', 'loopunroll=10', 'callunroll=10', 'recunroll=10', 'tryside=30') --Optional JIT optimization flags: user adjustable

local eventQ = require "eventQ"
local hash = require "hash"
local Entity = require "entity"

local Simian = {
    Entity = Entity
}

function Simian.init(self, simName, startTime, endTime, minDelay, useMPI, opt)
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

    self.optimistic = opt or false

    self.gvt = 0
    self.optNumEvents = 0
    self.rollbacks = 0
    self.antimsgSent = 0

    self.color = "white"
    self.countRound = 0
    self.t_min = self.infTime -- Mimimum red msg time stamp
    self.whiteMsg = 0 -- Count white messages (msgs sent when sender is white)

    self.gvtThreshold = 50 -- For not scheduling a msg to much in to the future
    self.gvtMemReq = 50 -- To kickoff GVT computation. In terms of num elemens (float each)
    self.gvtCounter = 0
    self.gvtInterval = 500
    self.gvtCompute = 0


    if self.optimistic then
        if not self.useMPI or self.size == 1 then
            self.optimistic = false
        end
    end


    --One output file per rank
    if self.rank == 0 then self.out = io.open("data", "a+")
    else self.out = nil end

    --self.out = io.open(self.name .. "." .. self.rank .. ".out", "w")
    --self.out:setvbuf("no")
end

function Simian.exit(self)
    if self.useMPI then --Exit only when all engines are ready
        if self.rank == 0 then
            self.out:flush()
            self.out:close()
            self.out = nil
        end
        self.MPI:finalize()
    end
end

function Simian.run(self) --Run the simulation
    if self.rank == 0 then
        print("===========================================")
        print("----------SIMIAN JIT-PDES ENGINE-----------")
        print("===========================================")
        if self.jitStatus then print("JIT: ON")
        else print("JIT: OFF")
        end
        if self.useMPI then print("MPI: ON, Size: " .. self.size)
        else print("MPI: OFF") end
        if self.optimistic then print("Optimistic Mode")
        else print("Conservative Mode") end
    end

    local numEvents, totalEvents, nwEvents, totalNWEvents = 0, 0, 0, 0

    local infTime, startTime, endTime, minDelay, rank, size, eventQueue, min
        = self.infTime, self.startTime, self.endTime, self.minDelay, self.rank, self.size, self.eventQueue, math.min

    local MPI = self.MPI --Cache MPI locally
    MPI:barrier()
    local startClock = os.clock()
    self.running = true

    if self.optimistic then
        self.gvt = startTime

        while self.gvt < endTime do
            while MPI:iprobe() do
                local remoteEvent = MPI:recvAnySize()

                if remoteEvent.GVT then self:calcGVT(remoteEvent)
                else
                    if (not remoteEvent.antimessage) and (remoteEvent.color == "white") then
                        self.whiteMsg = self.whiteMsg - 1
                    end

                    eventQ.push(eventQueue, remoteEvent)
                end
            end

            if #eventQueue > 0 then self:processNextEvent() end

            if self.rank == 0 and self.color == "white" then
                if self.gvtCounter >= self.gvtInterval then 
                    self:kickoffGVT()
                    self.gvtCounter = 0
                else self.gvtCounter = self.gvtCounter + 1 end
            end
        end
    else
        local globalMinLeft = startTime
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
    local elapsedClock = os.clock() - startClock

    if self.optimistic then
        MPI:barrier()
        totalEvents = MPI:allreduce(self.optNumEvents, MPI.SUM)
        rollEvents = MPI:allreduce(self.rollbacks, MPI.SUM)
        antiEvents = MPI:allreduce(self.antimsgSent, MPI.SUM)
        totalNWEvents = MPI:allreduce(nwEvents, MPI.SUM)
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
        print("SIMULATION COMPLETED IN: " .. elapsedClock .. " SECONDS")
        print("SIMULATED EVENTS: " .. totalEvents)
        
        if self.optimistic then
            print ("    NUMBER OF EVENTS ROLLED BACK: " .. rollEvents)
            print ("    NUMBER OF ANTIMESSAGES SENT: " .. antiEvents)
            print ("    COMMITTED EVENTS: " .. (totalEvents - rollEvents))
            print ("    COMMITTED EVENT RATE: " .. ((totalEvents - rollEvents)/elapsedClock))
            print ("    Efficiency: " .. math.floor((totalEvents - rollEvents) * 100 / totalEvents) .. "%")
            print ("    # GVT Computations: " .. self.gvtCompute)
            print ("        GVT Interval: " .. self.gvtInterval)
            print ("        GVT Threshold: " .. self.gvtThreshold)
            print ("        GVT MemReq: " .. self.gvtMemReq)
            self.out:write((totalEvents - rollEvents)/elapsedClock .. "\n")
        else
            print("NETWORK EVENTS: " .. totalNWEvents)
            print("EVENT RATE: " .. totalEvents/elapsedClock)
            self.out:write(totalEvents/elapsedClock .. "\n")
        end
        print("===========================================")
    end
end

function Simian.kickoffGVT(self)
    self.countRound = 0
    self.color = "red" 
    local LPVT = self.infTime

    for k,entType in pairs(self.entities) do
        for _,ent in pairs(self.entities[k]) do
            local en = self.entities[k][_]

            if en.VT < LPVT then LPVT = en.VT end -- Smallest VT in an engine among its entities
        end
    end

    if #(self.eventQueue) > 0 then LPVT = math.min(LPVT, self.eventQueue[1].time) end -- And unprocessed events

    local e = {
                m_clock = LPVT, 
                m_send = self.infTime,
                count = self.whiteMsg,
                GVT = true,
                GVT_broadcast = -1,
                rank = self.rank,
            }
    
    --print(self.rank, e.m_clock, e.count)
    self.MPI:send(e, 1) -- Send to Rank 1 
    self.whiteMsg = 0    
end

function Simian.calcGVT(self, event)
    local LPVT = self.infTime

    if event.GVT_broadcast >= 0 then
        self.gvt = event.GVT_broadcast
        self.color = "white"
        self:fossilCollect(self.gvt)
        self.t_min = self.infTime

        --print(self.rank, " GVT Received, ", self.gvt)
        return
    else
        for k,entType in pairs(self.entities) do
            for _,ent in pairs(self.entities[k]) do
                local en = self.entities[k][_]

                if en.VT < LPVT then LPVT = en.VT end -- Smallest VT in an engine among its entities
            end
        end

        if #(self.eventQueue) > 0 then LPVT = math.min(LPVT, self.eventQueue[1].time) end -- And unprocessed events
    end

    if self.rank == 0 then
        event.count = event.count + self.whiteMsg

        if event.count == 0 and self.countRound > 0 then
            local red_ts = math.min(event.m_send, self.t_min)
            local min_ts = math.min(LPVT, red_ts)
            self.gvt = math.min(event.m_clock, min_ts)
            
            --print(self.rank, " GVT Found, ", self.gvt)
            for rank = self.size-1, 1, -1 do 
                --print("0 Send to ", rank, " - ", self.gvt)
                local e = {GVT = true, GVT_broadcast = self.gvt,} 
                self.MPI:send(e, rank)
            end

            self.gvtCompute = self.gvtCompute + 1
            self.whiteMsg = 0
            self.color = "white"
            self.t_min = self.infTime
            self:fossilCollect(self.gvt)
        else
            --print(self.rank, "GVT Not Found")
            self.countRound = self.countRound + 1

            event.m_clock = LPVT
            event.m_send = math.min(event.m_send, self.t_min)
            --print(self.rank, self.size)
            local recvRank = (self.rank + 1) % self.size 

            --print(self.rank, event.m_clock, event.m_send, event.count, recvRank)
            self.MPI:send(event, recvRank)
            self.whiteMsg = 0
        end
    else
        --print(self.rank, "GVT Not Found")
        if self.color == "white" then
            self.t_min = self.infTime
            self.color = "red"
        end

        local recvRank = (self.rank + 1) % self.size

        --print(event.m_clock, event.GVT)
        local e = {
                m_clock = math.min(event.m_clock, LPVT),
                m_send = math.min(event.m_send, self.t_min),
                count = (event.count + self.whiteMsg),
                GVT = true,
                GVT_broadcast = -1,
            }
    
        --print(self.rank, e.m_clock, e.m_send, e.count)
        self.MPI:send(e, recvRank) 
        self.whiteMsg = 0    
    end
end

function Simian.processNextEvent(self)
    local LP = self.entities[self.eventQueue[1].rx][self.eventQueue[1].rxId]

    if self.rank == 0 and #(LP.processedEvents) > self.gvtMemReq and self.color == "white" then
        --print(self.rank, "kickoff GVT - event f, ", self.gvt)
        self:kickoffGVT() 
    end

    local event = eventQ.pop(self.eventQueue) -- Next event

    --print(self.rank, " Cancel reverse msgs and return")
    -- event's inverse msg present in the queue. cancel each other and return true
    if self:cancelEvents(event) then return end
    
    if event.time > self.gvt + 5 * self.gvtThreshold then
        -- if too much in the future, do not process it
        --print(self.rank, " Too much in the future")
        eventQ.push(self.eventQueue, event)
        return
    end

    -- no inverse msg in the queue
    if event.antimessage then -- rollback
        --print(self.rank, " Rollback")
        --eventQ.push(self.eventQueue, event)
        self:rollback(event.time, LP)
    else
        if LP.VT > event.time then -- causality violated
            --print(self.rank, " Causality violated")
            eventQ.push(self.eventQueue, event)
            self:rollback(event.time, LP)
        else -- execute positive event
            --print(self.rank, " Execute event")
            local state = copy(LP.saveState(LP)) -- Model's responsibility
            LP.VT = event.time

            local service = LP[event.name]
            service(LP, event.data, event.tx, event.txId) -- generate() in model -> reqService() in entity
            self.optNumEvents = self.optNumEvents + 1

            local state = copy(LP.saveAntimessages(LP, state))
            local t = {e = event, s = state,}
            table.insert(LP.processedEvents, t)
        end
    end
end

function Simian.cancelEvents(self, event)
    local ret = false 
    local otherEvents = {}

    -- to look for event's inverse
    if event.antimessage then event.antimessage = false
    else event.antimessage = true end

    while #(self.eventQueue) > 0 and (self.eventQueue[1]).time <= event.time do
        poppedEvent = eventQ.pop(self.eventQueue) -- Next event
    
        if cmp(poppedEvent, event) then -- event's inverse is found
            ret = true
            break
        else
            table.insert(otherEvents, poppedEvent)
        end
    end

    -- fix the event
    if ret == false then
        if event.antimessage then event.antimessage = false
        else event.antimessage = true end
    end

    -- fix the eventQueue
    for k,v in pairs(otherEvents) do
        eventQ.push(self.eventQueue, v)
    end

    return ret
end

function Simian.rollback(self, time, LP)
    local backup = false
    if time < self.gvt then error("Rollback before GVT !!!") end

    if #(LP.processedEvents) > 0 then
        --print(self.rank, " Rolling ", #(LP.processedEvents), LP.processedEvents[#(LP.processedEvents)].e.time, time)
        while LP.processedEvents[#(LP.processedEvents)].e.time >= time do 
            --print(self.rank, " Roll ", LP.processedEvents[#(LP.processedEvents)].e.time, time)
            local t = table.remove(LP.processedEvents)  

            eventQ.push(self.eventQueue, copy(t.e))
            backup = copy(t.s)

            LP.recoverAntimessages(LP, t.s, time)
            self.rollbacks = self.rollbacks + 1

            if #(LP.processedEvents) == 0 then break end 
        end
    end

    if backup then 
        LP.recoverState(LP, backup)
        --print(self.rank, " Recover") 
    end

    LP.VT = time
end

function Simian.fossilCollect(self, time)
    for k,entType in pairs(self.entities) do
        for _,ent in pairs(self.entities[k]) do
            local en = self.entities[k][_]

            for key, v in pairs(en.processedEvents) do 
                if v.e.time < time then en.processedEvents[key] = nil end 
            end
        end
    end
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

            antimessage = false,
            GVT = false,
            color = "white",
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
        --self.out:write(name .. "[" .. num .. "]: Running on rank " .. computedRank .. "\n")

        entity[num] = entityClass(name, self.out, self, num, ...) --Entity is instantiated
    end
end

function cmp(t1, t2)
    for k1,v1 in pairs(t1) do
        local v2 = t2[k1]

        if v1 ~= v2 then return false end
    end
    return true
end

function copy(t)
    local t2 = {}
    for k,v in pairs(t) do 
        if type(v) == "table" then t2[k] = copy(v)
        else t2[k] = v end
    end
    return t2
end

return Simian
