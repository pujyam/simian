##############################################################################
# © Copyright 2015-. Triad National Security, LLC. All rights reserved.
#
# This program was produced under U.S. Government contract 89233218CNA000001 for Los Alamos National Laboratory (LANL), which is operated by Triad National Security, LLC for the U.S. Department of Energy/National Nuclear Security Administration.
#
# All rights in the program are reserved by Triad National Security, LLC, and the U.S. Department of Energy/National Nuclear Security Administration. The Government is granted for itself and others acting on its behalf a nonexclusive, paid-up, irrevocable worldwide license in this material to reproduce, prepare derivative works, distribute copies to the public, perform publicly and display publicly, and to permit others to do so.
#
# This is open source software; you can redistribute it and/or modify it under the terms of the BSD 3-clause License. If software is modified to produce derivative works, such modified software should be clearly marked, so as not to confuse it with the version available from LANL. Full text of the BSD 3-clause License can be found in the License file in the main development branch of the repository.
#
##############################################################################
# BSD 3-clause license:
# Copyright 2015- Triad National Security, LLC
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##############################################################################
# POC: Stephan Eidenbenz, eidenben@lanl.gov
# Date: March 25, 2015
# Copyright: Open source, must acknowledge original author
# Purpose: PDES Engine in CPython and PyPy, mirroring most of the original LuaJIT version of Simian JIT-PDES
# NOTE: If speed rivaling C/C++ PDES engines is desired, consider adopting the LuaJIT version of Simian JIT-PDES
#
##############################################################################
# Changelog:
#
# NOTE: 5/9/2020: Changes: Nandakishore Santhi
# Simian for Python 3.7
# Combined all Simian modules into a single standalone module file
# Updated LICENSE and COPYRIGHT notices
#
##############################################################################
#
# Comprehensive JIT-PDES benchmark simulation scipt Version for Python 3.7

"""
PDES LANL BENCHMARK is a benchmark to test parallel discrete event simulation performance
through a combination of communication loads, memory requirements, and computational loads

Overview
==========
Each entity A sends a "request computation" message to another entity B; upon message receipt,
B performs randomly weighted subset sum calculations on its local list data structure.
Each entity A also sends "timer" messages to itself with some delay before it sends another 
"request computation" message. The main parameters are as follows:

Communication Parameters
========================
n_ent:      Number of entities
s_ent:      Average number of send events per entity
            Individual entities determine how many events they need to send 
            based on p_send and their index and then adjust their local intersend_delay
            using an exponential distribution. 
endTime:    Duration of simulation. Note that minDelay = 1.0 always, so
            setting endTime to n_ent*s_ent will result in one event per minDelay 
            epoch when running in parallel mode 
q_avg:      Average number of events in the event queue per entity
            For individual entities this is made proportional 
            the number of total events that the entity needs to send.
            Default value is 1. Higher values will stress-test the event queue
            mechanism of the DES engine
p_receive: Parameter for geometric distribution of destination entities indexed by entity index.
            Entity i receives a fraction of p_receive*(1-p_receive)**(i-1) of all request messages
            Lower-indexed entities receive larger shares
            p_receive = 0: uniform distribution; p_receive = 1: only entity 1 receives messages
p_send:     Parameter for geometric distribution of source entities indexed by entity index
            See p_receive for more details
invert:     Flag to indicate whether receive and sent distribution should be inverted
            If set to True: highest-index entity sends most messages

Memory Parameters
==========================
m_ent:      Average memory footprint per entity, 
            modeled as the average linear list size (8 byte units).
            Each entity has a local list as a data structure that  uses up memory
p_list:     Parameter for geometric distribution of linear list sizes
            Set to 0 for uniform distribution
            Set to 1.0 to make entity 0 the only entity with a list

Computation Parameters
==========================
ops_ent:    Average operations per handler per entity.
            Computational cycle use is implemented as a weighted subset sum calculation
            of the first k elements of the list with randomly drawn weights (to eliminate 
            the possibility that the calculation gets optimized away).
            Each entity linearly scales down the number of operations based on its local
            list size as determined by p_list.
ops_sigma:  Variance of numer of operations per handler per entity, as a fraction of ops_ent

cache_friendliness:
            Determines how many different list elements are accessed during operations
            traded off with more operations per list element
            Set to p to access the first p fraction of list elements
            Set to 0.0 to access only first list element
            Set to 1.0 to access all list elements
            Set to 0.5 if no other value is known

PDES Parameters
========================
time_bins:  Purely for reporting purposes, this parameter gives the number of equal-size 
            time bins in which send events are sent
init_seed:  Initial seed value for random number generation. Built-in Python random number 
            generator is used. Seed values are passed along to entities upon creation and
            also as parameters for graph/matrix generation

Output statistics are written into the output file of entity 0.
Example: python pdes_lanl_benchmarkV8.py 10 1000 5 0 0 False 100 0 1000 0 0.5 1 10 100 .1 False BMLog.log


POC: Stephan Eidenbenz, eidenben@lanl.gov
Date: March 25, 2015
"""

import math
import random
import sys

from simian import Simian
mpiLib = "/opt/local/lib/mpich-mp/libmpich.dylib"

############ Variables ###########################
if len(sys.argv) != 18:
    print("Usage: python " + sys.argv[0] + " n_ent s_ent q_avg p_receive p_send invert m_ent p_list ops_ent ops_sigma cache_friendliness init_seed time_bins endTime minDelay useMPI logName")
    sys.exit()

n_ent = int(sys.argv[1])
s_ent = int(sys.argv[2])
q_avg = float(sys.argv[3])
p_receive = float(sys.argv[4])
p_send = float(sys.argv[5])
invert = (str(sys.argv[6]).lower() == "true")

m_ent = int(sys.argv[7])
p_list = float(sys.argv[8])
ops_ent = float(sys.argv[9])
ops_sigma = float(sys.argv[10])
cache_friendliness = float(sys.argv[11])
init_seed = int(sys.argv[12])
time_bins = int(sys.argv[13])

if str(sys.argv[14]).lower() == "compute":
    endTime = n_ent*s_ent
else:
    endTime = float(sys.argv[14])
minDelay = float(sys.argv[15])
useMPI = (str(sys.argv[16]).lower() == "true")

logName = sys.argv[17]

#print(n_ent, s_ent, q_avg, p_receive, p_send, invert, m_ent, p_list, ops_ent, ops_sigma, cache_friendliness, init_seed, time_bins, endTime, minDelay, useMPI, mpiLib, logName)

"""
n_ent = 10      # Number of entities 10
s_ent = 10000   # Average number of send events per entity 100
                # Individual entities determine how many events they need to send 
                # based on p_send and their index and then adjust their local intersend_delay
                # using an exponential distribution.    
#endTime = n_ent*s_ent      # Duration of simulation. Note that minDelay = 1.0 always, so
endTime = 5 # Duration of simulation. Note that minDelay = 1.0 always, so
                # setting endTime to n_ent*s_ent will result in one event per minDelay 
                # epoch when running in parallel mode
q_avg = 1       # Average number of events in the event queue per entity
                # For individual entities this is made proportional 
                # the number of total events that the entity needs to send.
                # Default value is 1. Higher values will stress-test the event queue
                # mechanism of the DES engine
                # try from 1(default), 0.2*s_ent, 0.5*s_ent, 0.8*s_ent,s_ent 
p_receive = 0   # Parameter to geometric distribution for choosing destination entities
                # Set to 0 for uniform distribution
                # Set to 1.0 to make entity 0 the only destination
                # Lower index entities receive more messages                
p_send = 0      # Parameter for geometric distribution of source entities

                # Set to 0 for uniform distribution
                # Set to 1.0 to make entity 0 the only source
invert = False  # Flag to indicate whether receive and sent distribution should be inverted
                # If True: entity n_ent sends most  messages    

m_ent = 1000    # Average memory footprint per entity, 
                # modeled as the average linear list size (8 byte units) 
p_list  = 0     # Parameter for geometric distribution of linear list sizes
                # Set to 0 for uniform distribution
                # Set to 1.0 to make entity 0 the only entity with a list 
ops_ent = 1000  # Average operations per handler per entity.
ops_sigma = 0   # Variance of numer of operations per handler per entity, as a fraction of ops_ent
                # drawn from a Gaussian
cache_friendliness = 0.5 
                # Determines how many different list elements are accessed during operations
                # traded off with more operations per list element 
                # Set to p to access the first p fraction of list elements
                # Set to 0.0 to access only first list element (cache-friendly)
                # Set to 1.0 to access all list elements (cache-unfriendly)
                # Set to 0.5 if no other value is known
            
init_seed = 1   # Initial random seed to be passed around
time_bins = 10  # Number of bins for time and event reporting (Stats only)
useMPI = True
"""


########################
#  Initialization stuff 

minDelay = 1.0  # Minimum Delay value for synchronization between MPI ranks (if applicable)
endTime = max(endTime, 2)

# Compute target number of send events
target_global_sends = n_ent * s_ent

# Compute the min value for geometric distribution function
r_min = (1 -  p_receive) ** n_ent
r_min0 = (1 - 0) ** n_ent
report = True

simName = "PDES_LANL_Benchmark_" + logName
startTime =  0.0
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI)
# Note little trick with endTime setting, as we need to collect statistics in the end

########################
class PDES_LANL_Node(simianEngine.Entity):
    def __init__(self, baseInfo, *args):
        super(PDES_LANL_Node, self).__init__(baseInfo)
        seed = self.num + init_seed # initialize random seed with own id
        # 1. Compute number of events that the entity will send out
        if p_send == 0: # uniform case
            prob =  1.0/float(n_ent)
        else:
            if invert:
                prob =  p_send*(1-p_send)**(n_ent - self.num) # Probability that an event gets generated on this entity
            else:
                prob =  p_send*(1-p_send)**(self.num)
        target_sends = int(prob * target_global_sends)
        if target_sends > 0:
            self.local_intersend_delay = float(endTime)/float(target_sends) 
        else:
            self.local_intersend_delay = 10*endTime 
            # if the entity sends zero events, we let it create one that will most likely be 
            # after the sim ends
        
        # 2. Allocate appropriate memory space through list size, and number of ops
        if p_list == 0: # uniform case
            prob =  1.0/float(n_ent)
        else:
            prob =  p_list*(1-p_list)**(self.num)
        self.list_size = int(prob * n_ent * m_ent)+1 # there are n_ent*m_ent list elements in total
        self.ops = int(prob * n_ent * ops_ent)+1 # there are n_ent*m_ent list elements in total
        self.active_elements = int(cache_friendliness * self.list_size) # only this many list elements will be accessed     
        self.list = []
        for i in range(self.list_size): # create a list of random elements of length list_size
            self.list.append(random.random()) 
            
        # 3. Set up queue size
        self.q_target = q_avg/float(s_ent) * target_sends
        self.q_size = 1 # number of send events scheduled ahead of time by this entity
        self.last_scheduled = simianEngine.now # time of last scheduled event
        
        
        # 4. Set up statistics
        self.send_count, self.receive_count =  0, 0 # for stats
        self.ops_max, self.ops_min, self.ops_mean = 0, float("inf"), 0.0 # for stats
        self.time_sends = [] # for time reporting
        for i in range(time_bins):
            self.time_sends.append(0)
        if self.num == 0: # only for the global statistics entity
            self.stats_received, self.gsend_count, self.greceive_count = 0, 0, 0
            self.gops_max, self.gops_min, self.gops_mean = 0, float("inf"), 0.0 
            self.gtime_sends = [] # for time reporting
            for i in range(time_bins):
                self.gtime_sends.append(0)
        
        # 5. Schedule FinishUp at end of time
        self.reqService(endTime - simianEngine.now, "FinishHandler", None)
        #print "Entity creation ", self.num, self.list_size, self.ops
        self.SendHandler(seed)

                
    def saveState(self):
        state = {"send_count" : self.send_count,
                "q_size" : self.q_size,
                #"time_sends" : self.time_sends[int(math.floor(simianEngine.now/float(endTime+0.0001)*time_bins))],
                "q_target" : self.q_target,
                "last_scheduled" : self.last_scheduled,
                "receive_count" : self.receive_count,
                "ops_max" : self.ops_max,
                "ops_min" : self.ops_min,
                "ops_mean" : self.ops_mean,}
        return dict(state)

    def recoverState(self, state):
        self.send_count = state["send_count"]
        self.q_size = state["q_size"]
        self.q_target = state["q_target"]
        self.last_scheduled = state["last_scheduled"]
        self.receive_count = state["receive_count"]
        self.ops_max = state["ops_max"]
        self.ops_min = state["ops_min"]
        self.ops_mean = state["ops_mean"]
        return

    def SendHandler(self, seed, *args): # args is artificial
        global r_min, r_min0, report, p_receive

        random.seed(seed)
        self.send_count += 1
        self.q_size -= 1
        #self.time_sends[int(math.floor(simianEngine.now/float(endTime+0.0001)*time_bins))] += 1

        # Generate next event for myself
        # Reschedule myself until q is full or time has run out
        #while (self.q_size < self.q_target) and not (self.last_scheduled > endTime):
        while (self.q_size < self.q_target):
            own_delay = random.expovariate(1.0 / self.local_intersend_delay)
            self.last_scheduled +=  own_delay
            #if self.last_scheduled < endTime:

            self.q_size += 1
            self.reqService(self.last_scheduled-simianEngine.now, "SendHandler", random.random())
            #print "entity", self.num, " Time ", simianEngine.now, " scheduled send event for time ", self.last_scheduled
       
        if self.engine.gvt > (endTime / 2) and report:
            p_receive = 0
            r_min = r_min0
            report = False

        # Generate computation request event to destination entity
        # If p is exactly 1.0, then the only entity 0 is only destination 
        if p_receive == 1.0: DestIndex = 0
        # by convention, p == 0 means we want uniform distribution 
        elif p_receive == 0: DestIndex = int(random.random() * n_ent)
        else:
            U = random.uniform(r_min, 1.0) # We computed r_min such that the we only get indices less than num_ent
            DestIndex = int(math.ceil(float(math.log(U)) / float(math.log(1.0 - p_receive)))) -1        
        new_seed = random.random()

        #print "SendHandler ", self.num, DestIndex
        # Send event to destination ReceiveHandler (only if not past reporting time)
        #if simianEngine.now+minDelay < endTime:
        self.reqService(minDelay, "ReceiveHandler", new_seed, "PDES_LANL_Node", DestIndex)


    def ReceiveHandler(self, seed, *args): # args is artificial
        random.seed(seed)
        r_ops = max(1, int(random.gauss(self.ops, self.ops*ops_sigma))) # number of operations
        r_active_elements = int(self.active_elements * (r_ops/float(self.ops))) # only this many list elements will be accessed
        r_active_elements = min(r_active_elements, self.list_size) # cannot be more than list size
        r_active_elements = max(1, r_active_elements) # cannot be less than 1
        r_ops_per_element = int(r_ops/float(r_active_elements))
        # Update stats
        self.receive_count += 1
        self.ops_max = max(self.ops_max, r_ops)
        self.ops_min = min(self.ops_min, r_ops)
        self.ops_mean = (self.ops_mean*(self.receive_count-1) +  r_ops)/self.receive_count 
        # Compute loop
        value = 0.0
        for i in range(r_active_elements):
            for j in range(r_ops_per_element):
                value += self.list[i] * random.random()
        return value

    def FinishHandler(self, *args): # args is artificial
        # Send stats to entity 0 for outputting of global stats
        msg = [self.num, self.send_count, self.receive_count, \
            self.ops_min, self.ops_mean, self.ops_max, self.time_sends]
        self.reqService(minDelay, "OutputHandler", msg, "PDES_LANL_Node", 0)

    def OutputHandler(self, msg, *args): # args is artificial
        # Write out Stats, only invoked on entity 0
        if self.stats_received == 0:
            # Only write header line a single time
            header = "{0:>8}{1:>10}{2:>10}{3:>10}{4:>7}{5:>10}    {6:<2}\n".format("EntityID", "#sends", "#receives", \
                 "Ops(min", "avg", "max)", "Time Bin Sends")
            #self.out.write(header)
        
        self.stats_received += 1
        #self.gops_mean = (msg[2]*msg[4] + self.gops_mean*self.greceive_count)/(self.greceive_count+msg[2])
        self.gsend_count += msg[1]
        self.greceive_count += msg[2]
        self.gops_min = min(self.gops_min, msg[3])
        self.gops_max = max(self.gops_max, msg[5])
        for i in range(time_bins):
            self.gtime_sends[i] += msg[6][i]
        
        str_out = str(msg[0])+"  "+str(msg[1])+"  "+str(msg[2])+"  "+str(msg[3])+"  "+str(msg[4])+"  "+str(msg[5])+"  "+str(msg[6])+"  "
        #self.out.write(str_out)

        if self.stats_received == n_ent: # We can write out global stats
            #self.out.write("===================== LANL PDES BENCHMARK  Collected Stats from All Ranks =======================\n")
            header = "#Entities, #sends, #receives Ops(min, avg, max), Time Bin Sends"          
            #self.out.write(header)
            str_out = "test"
            #self.out.write(str(n_ent)+"  "+str(self.gsend_count)+"  "+str(self.greceive_count))
            #self.out.write("=================================================================================================\n")
    

################################
# "MAIN"
################################


for i in range(n_ent):
    simianEngine.addEntity("PDES_LANL_Node", PDES_LANL_Node, i)

# 5. Run simx
simianEngine.run()
for i in range(n_ent):
    node = simianEngine.getEntity("PDES_LANL_Node", i)
    #print node.num
simianEngine.exit()
