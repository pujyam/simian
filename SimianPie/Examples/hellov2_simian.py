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
# Simple example simulation scipt

from simian import Simian
import random, math

simName, startTime, endTime, minDelay, useMPI, mpiLib = "HELLO", 0, 1000000.1, 1, False, "/opt/local/lib/mpich-mp/libmpich.dylib"
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI, mpiLib)

num_entities = 32

random.seed(0)

class HelloMessage:
    def __init__(self, reply_to_id):
        self.reply_to_id = reply_to_id
    
   # def __str__(self):
   #      return "HelloMessage(%s %s)" %(self.source_id, self.dest_id)


class ReplyMessage:
    pass
    #def __str__(self):
    #    return "ReplyMessage(%s %s)" %(self.source_id, self.dest_id)


class Person(simianEngine.Entity):
    def __init__(self, baseInfo, *args):
        super(Person, self).__init__(baseInfo)
        self.id_ = args[0]
        #print "person ",self.id_," being created"
        
    def recv_hello(self, data, tx, txId):
        #print "person ",self.id_,"received hello from ",data.reply_to_id, " at time ", self.engine.now
        self.reqService(minDelay,"recv_reply",ReplyMessage(), "Person", data.reply_to_id)


    def recv_reply(self,data, tx, txId):
        #print "person ", self.id_," received reply from ",txId, " at time", self.engine.now
        pass




def MessageGenProcess(this):
    this.sleep(1)
    entity = this.entity
    for evt_time in xrange(1, int(endTime/2-1)):
        hello_rcvr = random.choice(xrange(num_entities))
        reply_rcvr = random.choice(xrange(num_entities))
        #print evt_time,hello_rcvr,reply_rcvr
        entity.reqService(evt_time,"recv_hello",
                          HelloMessage(reply_rcvr),
                          "Person", hello_rcvr)

        if (evt_time % 10 == 0):
            #raw_input()
            this.sleep(evt_time - this.entity.engine.now)
            
        
        
class dummyNode(simianEngine.Entity):
    def __init__(self, baseInfo, *args):
        super(dummyNode, self).__init__(baseInfo)
        self.createProcess("MessageGen",MessageGenProcess)
        self.startProcess("MessageGen")

            
for i in xrange(num_entities):
    simianEngine.addEntity("Person",Person,i,i)

simianEngine.addEntity("dummyNode",dummyNode,0)

simianEngine.run()
simianEngine.exit()
