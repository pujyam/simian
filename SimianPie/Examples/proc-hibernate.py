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
# Simple example simulation script for pHOLD type holdoff with application process
# Demonstrates explicit event driven wakeup from hibernation

from simian import Simian
import random, math

simName, startTime, endTime, minDelay, useMPI, mpiLib = "PROC-HIBERNATE", 0, 10000, 0.0001, True, "/opt/local/lib/mpich-mp/libmpich.dylib"
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI, mpiLib)

count = 10
lookahead = minDelay

def exponential(mean):
    return -math.log(random.random())/mean

#Example of a process on an entity
def appProcess(this, data1, data2): #Here arg(1) "this" is current process
    entity = this.entity
    entity.out.write("Process App started with data: " + str(data1) + ", " + str(data2) + "\n")
    while True:
        x = random.randrange(100)
        #Shows how to log outputs
        entity.out.write("Time " + str(entity.engine.now)
            + ": Process App is sleeping for " + str(x) + "\n")
        entity.reqService(x, "wakeMe", this.name) #Set an explicit alarm for waking from hibernation
        this.hibernate() #Shows how to hibernate indefinitely
        entity.out.write("Time " + str(entity.engine.now)
            + ": Waking up Process App\n")

class Node(simianEngine.Entity):
    def __init__(self, baseInfo, *args):
        super(Node, self).__init__(baseInfo)

        self.createProcess("App", appProcess) #Shows how to create "App"
        self.startProcess("App", 78783, {"two": 2}) #Shows how to start "App" process with arbitrary number of data

    def generate(self, *args):
        targetId = random.randrange(count)
        offset = exponential(1) + lookahead

        #Shows how to log outputs
        self.out.write("Time "
                + str(self.engine.now)
                + ": Waking " + str(targetId)
                + " at " + str(offset) + " from now\n")

        self.reqService(offset, "generate", None, "Node", targetId)

    def wakeMe(self, name, rx=None, rxId=None):
        #This example is just a simple wrapper around the generic wakeProcess, but it could be more elaborate
        self.out.write("Explicit wake-up from hibernation through an event")
        self.wakeProcess(name)

for i in range(count):
    simianEngine.addEntity("Node", Node, i)

for i in range(count):
    simianEngine.schedService(0, "generate", None, "Node", i)

simianEngine.run()
simianEngine.exit()
