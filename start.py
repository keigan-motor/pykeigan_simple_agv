import subprocess

subprocess.Popen(['python3', '/home/pi/Desktop/pykeigan_simple_agv/picam_line_tracer_hsv.py'], 
                        stdout=subprocess.PIPE,)
proc1 = subprocess.Popen(['python3', '/home/pi/Desktop/pykeigan_simple_agv/shutdown.py'], 
                        stdout=subprocess.PIPE,)

#stdout_value = proc1.communicate()[0]
#print ('\tstdout:', repr(stdout_value))
                       
stdout_value = proc1.communicate()[0]
print ('\tstdout:', repr(stdout_value))