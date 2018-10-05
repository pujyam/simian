#Copyright (c) 2015, Los Alamos National Security, LLC
#All rights reserved.
#
#Copyright 2015. Los Alamos National Security, LLC. This software was produced under U.S. Government contract DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), which is operated by Los Alamos National Security, LLC for the U.S. Department of Energy. The U.S. Government has rights to use, reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is modified to produce derivative works, such modified software should be clearly marked, so as not to confuse it with the version available from LANL.
#
#Additionally, redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#	Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. 
#	Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 
#	Neither the name of Los Alamos National Security, LLC, Los Alamos National Laboratory, LANL, the U.S. Government, nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission. 
#THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#Author: Christopher Hannon
#Date: 24 May 2017
#Copyright: Open source, must acknowledge original author
#Purpose: PDES Engine in Python, mirroring a subset of the Simian JIT-PDES
#  Simple example simulation script
from context import simian
#import random, math
Simian=simian.Simian

import time

simName, startTime, endTime, minDelay, useMPI = "Chris_test", 0, 100, 0.0001, True
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI, optimistic = True, optimisticGVTThreshold = 50)

count = 30
lookahead = minDelay


class Node(simianEngine.Entity):

    def __init__(self, baseInfo, *args):
        self.targetId = 0
        self.even = 0
        super(Node, self).__init__(baseInfo)

        self.offset = 0#self.num / 100000.0
        
    def generate(self, *args):
        self.even += 1
        self.offset = lookahead + 1.1
        
        if self.even % 2: # odd
            self.targetId += 1
            if self.targetId == count:
                self.targetId = 0
            self.reqService(self.offset, "generate", None, "Node", self.targetId) # send to next target
        else: 
            self.reqService(self.offset, "generate", None, "Node", None) # send to self

    def saveState(self):

        state = {"targetId" : self.targetId,
                 "offset"   : self.offset,
                 "even"     : self.even,
                 }
        return dict(state)
        #return None
    
    def recoverState(self,state):
        self.targetId = state["targetId"]
        self.offset   = state["offset"]
        self.even     = state["even"]
        return
    
for i in xrange(count):
    simianEngine.addEntity("Node", Node, i)

for i in xrange(count):
    simianEngine.schedService(0, "generate", None, "Node", i)
for i in xrange(count):
    simianEngine.schedService(100, "generate", None, "Node", i)

simianEngine.run()
simianEngine.exit()
