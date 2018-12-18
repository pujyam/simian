jit.opt.start(3, 'hotloop=3', 'hotexit=8', 'instunroll=10', 'loopunroll=10', 'callunroll=10', 'recunroll=10', 'tryside=30') --Optional JIT optimization flags: user adjustable           

local eventQ = require "eventQ"

local eventQueue = {}

eventQ.push(eventQueue, event)

event = eventQ.pop(eventQueue)




-- test 1
for NUMBER=1,10 do

   for x=1,1000000 do
      local event = {
	 tx = 'a',
	 rx = 'b',
	 txID = 1,
	 rxID = 1,
	 name = "bob",
	 data = "none",
	 time = x,
      }
      eventQ.push(eventQueue,event)
   end
   
   for y=1,1000000 do
      event = eventQ.pop(eventQueue)
   end
   
end


--[[
-- test 2
local x,y
local NUMBER
local mat = math.random
for NUMBER=1,10 do

   for x=1,1000000 do
      local tt = mat(1000000)
      local event = {
	 tx = 'a',
	 rx = 'b',
	 txID = 1,
	 rxID = 1,
	 name = "bob",
	 data = "none",
	 time = tt,
      }
      eventQ.push(eventQueue,event)
   end
   
   for y=1,1000000 do
      event = eventQ.pop(eventQueue)
   end
   
end
]]

-- test 3
--[[
local x,y
local totalPushes = 0
local pushes = 0
local NUMBER
local mat = math.random
for NUMBER=1,10 do
   totalPushes = 0
   pushes = 0
   while totalPushes < 1000000 do
      for x=1,mat(100) do --1000000 do
	 pushes = pushes + 1
	 totalPushes = totalPushes + 1
	 local tt = mat(1000000)
	 local event = {
	    tx = 'a',
	    rx = 'b',
	    txID = 1,
	    rxID = 1,
	    name = "bob",
	    data = "none",
	    time = tt,
	 }
	 eventQ.push(eventQueue,event)
      end
      
      for y=1,mat(100) do --1000000 do
	 if pushes <= 0 then
	    break
	 end
	 pushes = pushes - 1
	 event = eventQ.pop(eventQueue)
	 
	 
      end
   end

end
]]
