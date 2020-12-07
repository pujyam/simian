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
--Author: Ali Eker 
--Date: September, 2020
--Copyright: Open source, must acknowledge original author
--Purpose: Epidemics Application for Hybrid-PDES SimianLua 
--]]

package.path = "Simian/?.lua;" .. package.path
local Simian = require "simian"

local res_count = tonumber(arg[1])
local bus_count = tonumber(arg[2])
local endTime = tonumber(arg[3])

local simName, startTime, minDelay, useMPI = "EPI", 0, 1, true
Simian:init(simName, startTime, endTime, minDelay, useMPI)

local Residential = Simian.Entity("Residential")
do
    function Residential:__init(...)
        self.num_agents = 4
        
        -- Parents go to job at 8 am
        for i = 0, 1 do
            local destJob = math.floor(math.random() * bus_count)        
            self:reqService(8, "arriveJob", nil, "Business", destJob) 
        end
    end

    function Residential:arriveHome()
        local destJob = math.floor(math.random() * bus_count)        
        self:reqService(16, "arriveJob", nil, "Business", destJob) 
    end

    function Residential:saveState()
        local state = {}
        return state
    end

    function Residential:recoverState(state)
    end
end

local Business = Simian.Entity("Business")
do
    function Business:__init(...)
        self.num_agents = 0
    end

    function Business:arriveJob()
        -- go back to home
        local destHome = math.floor(math.random() * res_count)        
        self:reqService(8, "arriveHome", nil, "Residential", destHome) 
    end

    function Business:saveState()
        local state = {}
        return state
    end

    function Business:recoverState(state)
    end
end

for i = 0, bus_count - 1 do
    Simian:addEntity("Business", Business, i)
end

for i = 0, res_count - 1 do
    Simian:addEntity("Residential", Residential, i)
end

Simian:run()
Simian:exit()
