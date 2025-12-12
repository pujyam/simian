##############################################################################
# (c) Copyright 2015-. Triad National Security, LLC. All rights reserved.
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
# Author: Timon Wattenhofer, Nandakishore Santhi
# Date: 23 November, 2025
# Copyright: Open source, must acknowledge original author
##############################################################################
from simian import Simian
import math


simName, startTime, endTime, minDelay, useMPI, mpiLib = "PowerSimian", 0, 1000, 0.0001, True, "/projects/opt/centos8/x86_64/mpich/3.3.2-gcc_9.4.0/lib/libmpich.so"
simianEngine = Simian(simName, startTime, endTime, minDelay, useMPI, mpiLib)

count = 4
node_count = {"nonLLM" : count, "llmNode": count}
entity_services = {"power" : "nonLLM", "sqrt": "nonLLM", "expound": "nonLLM"}

class llmNode(simianEngine.LLMEntity):
    def __init__(self, baseInfo, *args):
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": "power",
                    "description": "Compute a**b (exponentiation).",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number", "description": "Base to raise to a power."},
                            "b": {"type": "number", "description": "Exponent."}
                        },
                        "required": ["a", "b"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "sqrt",
                    "description": "Compute the non-negative square root of x.",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "minimum": 0,
                                "description": "Value whose square root to compute (must be ≥ 0)."
                            }
                        },
                        "required": ["x"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "expound",
                    "description": "Expounds on what has happened so far. Takes no input",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False
                    }
                }
            }
        ]
        self.node_count = node_count
        self.entity_services = entity_services
        super(llmNode, self).__init__(baseInfo)


class nonLLM(simianEngine.Entity):
    def __init__(self, initInfo):
        super(nonLLM, self).__init__(initInfo)
        self.entity_services = entity_services
        self.node_count = node_count

    def power (self, a, b):
        return a**b

    def sqrt (self, x):
        return math.sqrt(x)

    def expound(self):
        return "Please explain what the LLM has done so far."



for i in range(count):
    #model : name of model on huggingface, 
    #gguf : llamacpp needs a gguf file, so you need to specify the file name inside the huggingface files, 
    #n_ctx : ctx len for model
    #parser : the parser you want to use to parse your tool calls (Check slgang documentation for availabe tool call parsers https://docs.sglang.ai/advanced_features/tool_parser.html) !!!IMPORTANT: GPT-OSS parser doesn't work right now
    #msg_n_ctx : how many messages that have been passed to the model simian should pass on
    simianEngine.addEntity("llmNode", llmNode, i, model="Qwen/Qwen3-0.6B-GGUF", gguf="Qwen3-0.6B-Q8_0.gguf", n_ctx=2048, parser="qwen25", msg_n_ctx = 10)
    simianEngine.addEntity("nonLLM", nonLLM, i)

for i in range(count):
    simianEngine.schedService(0,"process_query",[{'role': 'user', 'content':"Please calculate accurately: 23^80 as well as 46^32. Then take the sqrt of 9 and expound upon everything done so far."}], "llmNode", i)

simianEngine.run()
simianEngine.exit()
