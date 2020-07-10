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
--  Simple example simulation script
--]]
package.path = "Simian/?.lua;" .. package.path

local Simian = require "simian"
local ln, random = math.log, math.random

local opt = (tostring(arg[1]):lower() == "true")
local simName, startTime, endTime, minDelay, useMPI = "PHOLD", 0, 100, 1, true

local count = 64 
local lookahead = minDelay

local function exponential(lambda)
    return -ln(random())/lambda
end

local Node = Simian.Entity("Node")
local targetId = 0
local offset = 0

function Node:generate(...)
    targetId = random(0, count-1)
    --targetId = (self.engine.rank + 1) % self.engine.size
    --targetId = self.engine.rank

    --offset = exponential(1) + lookahead
    offset = lookahead

    --self.out:write("Time "
    --            .. self.engine.now
    --            .. ": Waking " .. self.targetId
    --            .. " at " .. self.offset .. " from now\n")

    --print(self.engine.rank, " Execute event to ", targetId)
    self:reqService(offset, "generate", nil, "Node", targetId)
end

function Node:saveState()
    local state = {tid = targetId, off = offset,}
    return state
end

function Node:recoverState(state)
    targetId = state.tid
    offset = state.off
end

--Initialize Simian
Simian:init(simName, startTime, endTime, minDelay, useMPI, opt)

for i=0,count-1 do
    Simian:addEntity("Node", Node, i)
end

for i=0,count-1 do
    Simian:schedService(0, "generate", nil, "Node", i)
end

Simian:run()
Simian:exit()
