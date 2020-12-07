--[[
Copyright (c) 2015, Los Alamos National Security, LLC
All rights reserved.

Copyright 2015. Los Alamos National Security, LLC. This software was produced under U.S. Government contract DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), which is operated by Los Alamos National Security, LLC for the U.S. Department of Energy. The U.S. Government has rights to use, reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is modified to produce derivative works, such modified software should be clearly marked, so as not to confuse it with the version available from LANL.

Additionally, redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. 
    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 
    Neither the name of Los Alamos National Security, LLC, Los Alamos National Laboratory, LANL, the U.S. Government, nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission. 
THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
--]]

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

function Simian.init(self, simName, startTime, endTime, minDelay, useMPI)
    self.name = simName
    self.startTime = startTime
    self.endTime = endTime or 1e100
    self.minDelay = minDelay or 1
    self.useMPI = useMPI and true or false
    self.now = 0

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

    self.numEvents = 0
    self.nwEvents = 0

    self.optimistic = false
    self.gvt = 0
    self.optNumEvents = 0
    self.rollbacks = 0
    self.antimsgSent = 0

    self.color = "white"
    self.countRound = 0
    self.t_min = self.infTime -- Mimimum red msg time stamp
    self.whiteMsg = 0 -- Count white messages (msgs sent when sender is white)

    self.gvtInterval = 50
    self.gvtCompute = 0
    self.gvtCounter = 0 
    
    --One output file per rank
    if self.rank == 0 then self.out_d = io.open("./Data/data", "a+") end
    self.out = io.open("./Data/out." .. tostring(self.rank), "w") 

    -- For Cons - Opt Switch: If std_dev less than T, switch to OPT
    -- For phold
    --[[
    if self.size == 128 then self.switchConsThres = 1 end
    if self.size == 64 then self.switchConsThres = 0.4 end
    if self.size == 32 then self.switchConsThres = 0.4 end
    if self.size == 16 then self.switchConsThres = 0.4 end
    if self.size == 8 then self.switchConsThres = 0.4 end
    if self.size == 2 then self.switchConsThres = 0.4 end
    ]]--
    -- For la-pdes 
    if self.size == 256 then self.switchConsThres = 2 end
    if self.size == 128 then self.switchConsThres = 2 end
    if self.size == 64 then self.switchConsThres = 2 end
    if self.size == 32 then self.switchConsThres = 1.25 end
    if self.size == 16 then self.switchConsThres = 1 end
    if self.size == 8 then self.switchConsThres = 1 end
    if self.size == 2 then self.switchConsThres = 1 end
    --self.switchConsThres = 0 

    self.switchCounter = 0 
    self.checkSwitch = 50  -- Interval to check switching conditions from CONS to OPT

    -- Counts annti messages in CONS and same VT messages
    self.anti = 0 
    self.same = 0 
    
    -- For Opt - Cons Switch 
    self.sends = 0 -- To ensure all messages are received before switching to CONS
    self.pos = 0 -- To compute eff
    self.neg = 0
    self.fel = 64 -- Forward execution limit 

    -- Computes eff: (pos - neg) / pos. If eff less than T, switch to CONS 
    -- For phold
    --[[
    if self.size == 128 then self.switchOptThres = 0.2 end
    if self.size == 64 then self.switchOptThres = 0.1 end
    if self.size == 32 then self.switchOptThres = 0.5 end
    if self.size == 16 then self.switchOptThres = 0.5 end
    if self.size == 8 then self.switchOptThres = 0.5 end
    if self.size == 2 then self.switchOptThres = 0.5 end
    ]]--
    -- For la-pdes 
    if self.size == 256 then self.switchOptThres = 0.1 end
    if self.size == 128 then self.switchOptThres = 0.1 end
    if self.size == 64 then self.switchOptThres = 0.1 end
    if self.size == 32 then self.switchOptThres = 0.2 end
    if self.size == 16 then self.switchOptThres = 0.2 end
    if self.size == 8 then self.switchOptThres = 0.2 end
    if self.size == 2 then self.switchOptThres = 0.2 end
    --self.switchOptThres = -100000
end

function Simian.exit(self)
    if self.useMPI then --Exit only when all engines are ready
        if self.rank == 0 then
            self.out_d:flush()
            self.out_d:close()
        end
        self.out:flush()
        self.out:close()
        self.MPI:finalize()
    end
end

function Simian.run(self) --Run the simulation
    if self.rank == 0 then
        print("===========================================")
        print("--------SIMIAN LUA JIT-PDES ENGINE---------")
        print("===========================================")
        if self.useMPI then 
            print("MPI: ON, Size: " .. self.size)
            if self.size > 1 then print("Conservative-Optimistic Hybrid Mode\n") end
        else print("MPI: OFF") end
    end

    local MPI, infTime, endTime, minDelay, eventQueue = self.MPI, self.infTime, self.endTime, self.minDelay, self.eventQueue
    local globalMinLeft = self.startTime
    self.running = true
    
    MPI:barrier()
    local startClock = os.clock()

    while globalMinLeft <= endTime do --Exit loop only when global-epoch is past endTime
        local epoch = globalMinLeft + minDelay
        
        while eventQueue[1] and eventQueue[1].time < epoch do
            local event = eventQ.pop(eventQueue) --Next event
            local entity = self.entities[event.rx][event.rxId]

            if event.antimessage then 
                --print ("Anti in Cons")
                self.anti = self.anti + 1
                self:rollback(event.time, entity)
                break
            end

            if entity.VT > event.time then -- Out-of-order msg 
                self.anti = self.anti + 1
                self:rollback(event.time, entity)
                break
            elseif entity.VT == event.time then
                self.same = self.same + 1
                --goto cont
            end

            --Simulate event
            entity.VT = event.time
            self.now = event.time

            local service = entity[event.name]
            service(entity, event.data, event.tx, event.txId) -- Model generate
            self.numEvents = self.numEvents + 1
            --::cont::
        end 

        if self.size > 1 then
            -- All_reduce the num elements sent to calc num elements to expect to receive
            local toRcvCount = MPI:alltoallSum() 
            local recv = toRcvCount
                
            --if self.rank == 0 then print ("0 CONS[" .. self.gvt .. "] - " .. tostring(recv)) end
            while toRcvCount > 0 do --Recieve all expected events in next epoch
                MPI:probe() 
                eventQ.push(eventQueue, MPI:recvAnySize())
                toRcvCount = toRcvCount - 1
            end
            --if self.rank == 0 then print ("1 CONS[" .. self.gvt .. "]") end

            if self.switchCounter == self.checkSwitch then
                self.switchCounter = 0 
                --if self.rank == 0 then print ("2 CONS[" .. self.gvt .. "]") end

                --local sigma = self.MPI:allgather(#eventQueue)
                local sigma = self.MPI:allgather(recv)

                if self.rank == 0 then print ("CONS[" .. self.gvt .. "] check for OPT " .. sigma) end
                if sigma <= self.switchConsThres then

                    if self.rank == 0 then print ("     Switch to OPT " .. self.gvt .. " " .. sigma) end

                    self.optimistic = true
                    self:optimisticEngine() 
                end
            else self.switchCounter = self.switchCounter + 1 end

            local minLeft = (#eventQueue > 0) and eventQueue[1].time or infTime
            globalMinLeft = MPI:allreduce(minLeft, MPI.MIN) --Synchronize minLeft
            self.gvt = globalMinLeft 
            self.nwEvents = self.nwEvents + 1
        
        else globalMinLeft = (#eventQueue > 0) and eventQueue[1].time or infTime end
    end

    MPI:barrier()
    local elapsedClock = os.clock() - startClock
    self.running = false
        
    if self.size > 1 then
        optEvents = MPI:allreduce(self.optNumEvents, MPI.SUM)
        rollEvents = MPI:allreduce(self.rollbacks, MPI.SUM)
        antiEvents = MPI:allreduce(self.antimsgSent, MPI.SUM)
        antiCons = MPI:allreduce(self.anti, MPI.SUM)
        sameTotal = MPI:allreduce(self.same, MPI.SUM)

        totalEvents = MPI:allreduce(self.numEvents, MPI.SUM)
        totalAllEvents = totalEvents + optEvents
    end

    if self.size > 1 and self.rank == 0 then
        print ("SIMULATION COMPLETED IN: " .. elapsedClock .. " SECONDS")
        print ("SIMULATED EVENTS: " .. totalAllEvents)
        print ("    Conservative Events: " .. totalEvents)
        print ("        Check Switch Interval: " .. self.checkSwitch)
        print ("        # Events Rolled Back: " .. antiCons)
        print ("        # All_reduce: " .. self.nwEvents)
        print ("    Optimisitc Events: " .. optEvents)
        print ("        Forward Execution Limit: " .. self.fel)
        print ("        GVT Interval: " .. self.gvtInterval)
        print ("        # Events Rolled Back: " .. rollEvents)
        print ("        # Antimessages Sent: " .. antiEvents)
        print ("        # Net Events: " .. (optEvents - rollEvents))
        print ("        # GVT Computations: " .. self.gvtCompute)
        print ("        Efficiency: " .. math.floor((optEvents - rollEvents) * 100 / optEvents) .. "%")
        print ("    # Same VT events: " .. sameTotal)
        print ("    Net Event Rate: " .. ((totalAllEvents - rollEvents) / elapsedClock))
        print("===========================================")
        self.out_d:write((totalAllEvents - rollEvents)/elapsedClock .. "\n")
    end

    if self.size == 1 then
        print ("SIMULATION COMPLETED IN: " .. elapsedClock .. " SECONDS")
        print ("SIMULATED EVENTS: " .. numEvents)
        print ("    Event Rate: " .. (numEvents / elapsedClock))
        self.out_d:write(numEvents / elapsedClock .. "\n")
    end
end

function Simian.optimisticEngine(self)
    local MPI, eventQueue = self.MPI, self.eventQueue

    while self.gvt < self.endTime do
        while MPI:iprobe() do
            local remoteEvent = MPI:recvAnySize()

            if remoteEvent.GVT then 
                self:calcGVT(remoteEvent)
                if self.optimistic == false then
                    local transit = MPI:allreduce(self.sends, MPI.SUM) 

                    while transit ~= 0 do
                        if MPI:iprobe() then
                            local e = MPI:recvAnySize()
                            self.sends = self.sends - 1
                            eventQ.push(eventQueue, e)
                        end
                        
                        transit = MPI:allreduce(self.sends, MPI.SUM)
                    end

                    self.sends = 0
                    if self.rank == 0 then print ("     Switch to CONS " .. self.gvt) end
                    return
                end
            else
                if (not remoteEvent.antimessage) and (remoteEvent.color == "white") then 
                    self.whiteMsg = self.whiteMsg - 1 
                end

                self.sends = self.sends - 1
                eventQ.push(eventQueue, remoteEvent)
            end
        end

        --if self.rank == 0 then print(#eventQueue) end
        for i = 1, self.fel, 1 do
            if eventQueue[1] then 
                self:processNextEvent()
            else break end
        end

        if self.rank == 0 and self.color == "white" then
            if self.gvtCounter == self.gvtInterval then 
                self:kickoffGVT()
                self.gvtCounter = 0
            else self.gvtCounter = self.gvtCounter + 1 end
        end
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
    if #self.eventQueue > 0 then LPVT = math.min(LPVT, self.eventQueue[1].time) end
    --if #self.eventQueue > 0 then LPVT = self.eventQueue[1].time end

    local t = {p = self.pos, n = self.neg}
    self.pos = 0
    self.neg = 0

    local e = {
                m_clock = LPVT, 
                m_send = self.infTime,
                count = self.whiteMsg,
                GVT = true,
                GVT_broadcast = -1,
                rank = self.rank,
                opt = t, 
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

        --print(self.rank, "GVT Found")
        --self.now = self.gvt 
        self.optimistic = event.opt
        return
    else
        for k,entType in pairs(self.entities) do
            for _,ent in pairs(self.entities[k]) do
                local en = self.entities[k][_]
                if en.VT < LPVT then LPVT = en.VT end -- Smallest VT in an engine among its entities
            end
        end
        if #self.eventQueue > 0 then LPVT = math.min(LPVT, self.eventQueue[1].time) end
        --if #self.eventQueue > 0 then LPVT = self.eventQueue[1].time end
    end

    if self.rank == 0 then
        event.count = event.count + self.whiteMsg

        if event.count == 0 and self.countRound > 0 then
            local min_lvt = math.min(event.m_clock, LPVT)
            local min_red = math.min(event.m_send, self.t_min)
            self.gvt = math.min(min_lvt, min_red) 

            local eff = (event.opt.p - event.opt.n) / event.opt.p
            if eff <= self.switchOptThres then self.optimistic = false end
            --print("OPT[" .. self.gvt .. "] check for CONS ", eff)

            --self.now = self.gvt 

            for rank = self.size-1, 1, -1 do 
                local e = {GVT = true, GVT_broadcast = self.gvt, opt = self.optimistic,} 
                self.MPI:send(e, rank)
            end

            self.gvtCompute = self.gvtCompute + 1
            self.whiteMsg = 0
            self.color = "white"
            self.t_min = self.infTime
            self:fossilCollect(self.gvt)
        else
            self.countRound = self.countRound + 1

            event.m_clock = LPVT
            event.m_send = math.min(event.m_send, self.t_min)
            local recvRank = (self.rank + 1) % self.size 

            local t = {p = self.pos, n = self.neg}
            event.opt = t
            self.pos = 0
            self.neg = 0

            --print(self.gvt, event.m_clock, event.m_send, event.count)
            self.MPI:send(event, recvRank)
            self.whiteMsg = 0
        end
    else
        event.opt.p = event.opt.p + self.pos
        event.opt.n = event.opt.n + self.neg
        self.pos = 0
        self.neg = 0

        if self.color == "white" then
            self.t_min = self.infTime
            self.color = "red"
        end

        local recvRank = (self.rank + 1) % self.size

        local e = {
                m_clock = math.min(event.m_clock, LPVT),
                m_send = math.min(event.m_send, self.t_min),
                count = (event.count + self.whiteMsg),
                GVT = true,
                GVT_broadcast = -1,
                opt = event.opt
            }
    
        --print(self.rank, e.m_clock, e.m_send, e.count)
        self.MPI:send(e, recvRank) 
        self.whiteMsg = 0    
    end
end

function Simian.processNextEvent(self)
    local LP = self.entities[self.eventQueue[1].rx][self.eventQueue[1].rxId]
    local event = eventQ.pop(self.eventQueue) -- Next event

    -- event's inverse msg present in the queue. cancel each other and return true
    if self:cancelEvents(event) then 
        --if self.rank == 0 then print("Cancel reverse msgs") end
        return 
    end

    self.pos = self.pos + 1

    if LP.VT == event.time then 
        self.same = self.same + 1
        --return 
    end

    -- no inverse msg in the queue
    if event.antimessage then -- rollback
        --if self.rank == 0 then print("Rollback") end

        --eventQ.push(self.eventQueue, event)
        self:rollback(event.time, LP)
    else
        if LP.VT > event.time then -- causality violated
            --if self.rank == 0 then print("Causality Violated") end

            eventQ.push(self.eventQueue, event)
            self:rollback(event.time, LP)
        else -- execute positive event
            --if self.rank == 0 then print("Execute") end
            
            --local state = copy(LP.saveState(LP)) -- Model's responsibility
            local state = LP.saveState(LP) -- Model's responsibility
            LP.VT = event.time

            local service = LP[event.name]
            service(LP, event.data, event.tx, event.txId) -- generate() in model -> reqService() in entity
            self.optNumEvents = self.optNumEvents + 1

            --local state = copy(LP.saveAntimessages(LP, state))
            local state = LP.saveAntimessages(LP, state)
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
    
        if cmp(self, poppedEvent, event) then -- event's inverse is found
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
    for i = 1, #otherEvents do eventQ.push(self.eventQueue, otherEvents[i]) end

    return ret
end

function Simian.rollback(self, time, LP)
    local backup = false
    if time < self.gvt then 
        error(self.rank .. " Rollback before GVT: T: " .. time .. ", GVT: " .. self.gvt) 
    end

    if #(LP.processedEvents) > 0 then
        --print(self.rank, " Rolling ", #(LP.processedEvents), LP.processedEvents[#(LP.processedEvents)].e.time, time)
        while LP.processedEvents[#(LP.processedEvents)].e.time >= time do 
            --print(self.rank, " Roll ", LP.processedEvents[#(LP.processedEvents)].e.time, time)
            local t = table.remove(LP.processedEvents)  

            --eventQ.push(self.eventQueue, copy(t.e))
            --backup = copy(t.s)
            eventQ.push(self.eventQueue, t.e)
            backup = t.s
            
            LP.sendAntimessages(LP, t.s, time)
            self.rollbacks = self.rollbacks + 1
            self.neg = self.neg + 1

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

function Simian.getBaseRank(self, name, num)
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

    self.baseRanks[name] = self:getBaseRank(name, num) --Register base-ranks
    local computedRank = self:getOffsetRank(name, num)

    if computedRank == self.rank then --This entity resides on this engine
        --Output log file for this Entity
        
        --print (name .. "[" .. num .. "]: Running on rank " .. computedRank .. "\n")
        --self.out:write(name .. "[" .. num .. "]: Running on rank " .. computedRank .. "\n")

        entity[num] = entityClass(name, self.out, self, num, ...) --Entity is instantiated
    end
end

function cmp(self, t1, t2)
    for k1,v1 in pairs(t1) do
        local v2 = t2[k1]

        --if self.rank == 0 then print (k1 .. " -> " .. tostring(v1) .. " " .. tostring(v2)) end
        if v1 ~= v2 then return false end
    end
    --if self.rank == 0 then print ("Same") end
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
