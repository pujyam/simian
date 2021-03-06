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
# Author: Nandakishore Santhi
# Date: 23 November, 2014
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
# Simple example simulation script for many application processes

from simian import Simian
import random

#Initialize Simian
simName, startTime, endTime, minDelay, useMPI, mpiLib = "GREEN", 0, 500, 0.01, True, "/opt/local/lib/mpich-mp/libmpich.dylib"
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI, mpiLib)

count = int(10)
maxSleep = 100

#Example of a process on an entity
def appProcess(this): #Here arg(1) "this" is current process
    entity = this.entity
    entity.out.write("Process App started\n")
    while True:
        x = random.randrange(0, maxSleep)
        entity.out.write("Time " + str(entity.engine.now) \
            + ": Process " + this.name + " is sleeping for " + str(x) + "\n")
        this.sleep(x)
        entity.out.write("Time " + str(entity.engine.now) \
            + ": Waking up Process " + this.name + "\n")

class Node(simianEngine.Entity):
    def __init__(self, baseInfo, *args):
        super(Node, self).__init__(baseInfo)
        for i in range(count):
            appName = "App" + str(i)
            self.createProcess(appName, appProcess) #Create "App[i]"
            self.startProcess(appName) #Start "App[i]" process

simianEngine.addEntity("Node", Node, 1)

simianEngine.run()
simianEngine.exit()
