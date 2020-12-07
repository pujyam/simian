import subprocess

#threads = ["16"]
#n_ent = ["320"] 

#threads = ["32"]
#n_ent = ["640"] 

#threads = ["128"]
#n_ent = ["2560"] 

#threads = ["256"]
#n_ent = ["5120"] 

#threads = ["128", "256"]
#n_ent = ["2560", "5120"] 

#threads = ["64", "128", "256"]
#n_ent = ["1280", "2560", "5120"] 

#threads = ["32", "64", "128", "256"]
#n_ent = ["320", "640", "1280", "2560"] 
#n_ent = ["640", "1280", "2560", "5120"] 

#threads = ["8", "16", "32", "64", "128", "256"]
#n_ent = ["8", "16", "32", "64", "128", "256"] 
#n_ent = ["80", "160", "320", "640", "1280", "2560"] 
#n_ent = ["160", "320", "640", "1280", "2560", "5120"] 
#n_ent = ["400", "800", "1600", "3200", "6400", "12800"] 
#n_ent = ["800", "1600", "3200", "6400", "12800", "25600"] 

threads = ["64"]
n_ent = ["1280"] 

#threads = ["4"]
#n_ent = ["80"] 

p_loc = "0"  # 0: All messages are remote
end_time = "400"
num_trials = 1 
print "end_time: ", end_time, "\np_loc: ", p_loc, "\nn_ent: ", n_ent

p_recv = "0.05" 
print "\n******* p_recv: ", p_recv, " ********\n"

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "phold-basic.lua", n_ent[i], p_loc, p_recv, end_time)

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

