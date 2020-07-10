import subprocess

num_trials = 3
threads = ["1", "2", "4", "8", "16", "32", "64"]

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "10000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "false")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "10000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "true")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "100000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "false")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "100000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "true")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "1000000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "false")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()

for i in range(len(threads)):
	args = ("mpirun", "-n", threads[i], "luajit-2.1.0-beta3", "pdes_lanl_benchmarkV8-opt.lua", "64", "64", "1", "0", "0", "false", "1", "0", "1000000", "0", "0", "1" , "10", "10", "1", "true", "lanl", "true")

	for x in range(num_trials):
		popen = subprocess.Popen(args)
		popen.wait()


