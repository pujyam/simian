import subprocess
import sys

#threads = ["8", "16", "32", "64", "128", "256"]
#n_ent = ["80", "160", "320", "640", "1280", "2560"] 
#n_ent = ["40", "80", "160", "320", "640", "1280"] 
#n_ent = ["160", "320", "640", "1280", "2560"] 

#threads = ["8"]
#n_ent = ["80"] 

#threads = ["16"]
#n_ent = ["160"] 

threads = ["32"]
n_ent = ["320"] 

#threads = ["64"]
#n_ent = ["640"] 

#threads = ["128"]
#n_ent = ["1280"] 

#threads = ["256"]
#n_ent = ["2560"] 

num_trials = int(sys.argv[1])
print  "\nn_ent[]: ", n_ent 

q_avg = "1"
print "q_avg: ", q_avg 

ops_ent = ["1"]
print "ops_ent[]: ", ops_ent

ops_sigma = "0"
cache_f = "0"
print "ops_sigma: ", ops_sigma, "cache_f: ", cache_f

p_recv = "0.1"
print "p_recv: ", p_recv 

end_time = "4000"
print "end_time: ", end_time
print ""

for j in range(len(ops_ent)):
    for i in range(len(threads)):
	    args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", n_ent[i], "100", q_avg, p_recv, "0", "false", "1000", "0", ops_ent[j], ops_sigma, cache_f, "1" , "10", end_time, "1", "true", "lanl")

	    for x in range(num_trials):
		    popen = subprocess.Popen(args)
		    popen.wait()

