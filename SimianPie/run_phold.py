import subprocess

num_trials = 1 

threads = ["1", "8", "16", "32", "64", "128", "256"]
#n_ent = ["1", "8", "16", "32", "64", "128", "256"] 
n_ent = ["10", "80", "160", "320", "640", "1280", "2560"] 
#n_ent = ["20", "160", "320", "640", "1280", "2560", "5120"] 
#n_ent = ["50", "400", "800", "1600", "3200", "6400", "12800"] 
#n_ent = ["100", "800", "1600", "3200", "6400", "12800", "25600"] 
#n_ent = ["1000", "8000", "16000", "32000", "64000", "128000", "256000"] 

end_time = "10"
print "end_time: ", end_time 
print "threads[]: ", threads
print "n_ent[]: ", n_ent 

for i in range(len(threads)):
    args = ("mpirun", "-n", threads[i], "python3.6", "phold-opt.py", n_ent[i], end_time)

    for x in range(num_trials):
        popen = subprocess.Popen(args)
        popen.wait()
