

function lcg_r()
   local sum = 0
   for i=0, 1000000 do
      sum =sum+ math.random(2^31)
   end
end

function twist_r()
   local sum = 0
   for j=0, 1000000 do
      sum =sum+ math.lrandom(2^31)
   end
end


lcg_r()
--twist_r()
