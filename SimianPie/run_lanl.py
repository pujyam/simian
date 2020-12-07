import subprocess
import sys

threads = ["8", "16", "32", "64", "128", "256"]
#n_ent = ["8", "16", "32", "64", "128", "256"] 
n_ent = ["40", "80", "160", "320", "640", "1280"] 

#n_ent = ["10", "80", "160", "320", "640", "1280", "2560"] 
#n_ent = ["20", "160", "320", "640", "1280", "2560", "5120"] 
#n_ent = ["50", "400", "800", "1600", "3200", "6400", "12800"] 
#n_ent = ["100", "800", "1600", "3200", "6400", "12800", "25600"] 
#n_ent = ["1000", "8000", "16000", "32000", "64000", "128000", "256000"] 

#threads = ["8", "16", "32", "64"]
#n_ent = ["40", "80", "160", "320"]
#n_ent = ["80", "160", "320", "640"] 

#threads = ["8"]
#n_ent = ["40"]

#threads = ["64"]
#n_ent = ["320"]

#threads = ["128", "256"]
#n_ent = ["640", "1280"]

#threads = ["256"]
#n_ent = ["1280"]

num_trials = int(sys.argv[1])
print  "\nthreads[]: ", threads 
print  "n_ent[]: ", n_ent 

q_avg = "1"
print "q_avg: ", q_avg 

ops_ent = ["1000"]
print "ops_ent[]: ", ops_ent

ops_sigma = "0"
cache_f = "0"
print "ops_sigma: ", ops_sigma
print "cache_f: ", cache_f

p_recv = "0.1"
print "p_recv: ", p_recv 

end_time = "4000"
print "end_time: ", end_time

#py = "python3.6"
py = "/home/aeker801/libraries/pypy2.7-v7.3.1-linux64/bin/pypy"
#py = "/home/aeker801/libraries/pypy3.6-v7.3.1-linux64/bin/pypy3"

for j in range(len(ops_ent)):
    for i in range(len(threads)):
	    args = ("mpirun", "-n", threads[i], py, "pdes_lanl_benchmarkV8-opt.py", n_ent[i], "100", q_avg, p_recv, "0", "false", "1000", "0", ops_ent[j], ops_sigma, cache_f, "1" , "10", end_time, "1", "true", "lanl")

	    for x in range(num_trials):
		    popen = subprocess.Popen(args)
		    popen.wait()

