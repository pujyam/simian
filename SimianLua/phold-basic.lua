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

local count = tonumber(arg[1])
local p_loc = tonumber(arg[2])
local p_receive = tonumber(arg[3])
local p_receive_upt = p_receive

local endTime = tonumber(arg[4])

local r_min = (1 - p_receive) ^ count 

local function exponential(lambda)
    return -ln(random())/lambda
end

local simName, startTime, minDelay, useMPI = "PHOLD", 0, 1, true
local Node = Simian.Entity("Node")

local report2 = true
local report3 = true
local report4 = true

function Node:generate(...)

	if self.engine.gvt > endTime / 4 and report2 then
        p_receive = 0
        report2 = false
    end

	if self.engine.gvt > 2 * (endTime / 4) and report3 then
        p_receive = p_receive_upt
        report3 = false
    end

    if self.engine.gvt > 3 * (endTime / 4) and report4 then
        p_receive = 0
        report4 = false
    end

	local offset = random()	+ minDelay
	self:reqService(offset, "localGen", "Node") 

	if random() < p_loc then self:reqService(offset, "generate", nil)
	else 
	    local DestIndex

        if p_receive == 1.0 then DestIndex = 0
        elseif p_receive == 0 then DestIndex = math.floor(random() * count) -- Uniform
        else
            local U = (1.0 - r_min) * random() + r_min 
            DestIndex = math.floor(math.ceil(math.log(U) / math.log(1.0 - p_receive))) - 1 
        end
 	
		--if self.num == 0 then print ("Remote", offset, self.VT) end
		self:reqService(offset, "generate", nil, "Node", DestIndex) 
	end
end

function Node:localGen(...)
	--if self.num == 0 then print ("Local", self.VT) end

end

function Node:saveState()
    local state = {}
    return state
end

function Node:recoverState(state)
end

--Initialize Simian
Simian:init(simName, startTime, endTime, minDelay, useMPI)

for i=0,count-1 do
    Simian:addEntity("Node", Node, i)
end

for i=0,count-1 do
    Simian:schedService(1, "generate", nil, "Node", i)
end

Simian:run()
Simian:exit()
