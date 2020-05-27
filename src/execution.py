

import os
import shlex
import subprocess
import sys
import time



class Execution():
    def __init__(self, command):
        self.command = command
        self.elapsed = None
        self.retval = None
        self.stdout = None
        self.stderr = None
        self.has_run = False

    def run(self):
        try:
            start_time = time.time()
            p = subprocess.Popen(shlex.split(self.command),
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err  = p.communicate()
            end_time = time.time()
            self.elapsed = end_time - start_time
            self.stdout = out.decode('utf-8')
            self.stderr = err.decode('utf-8')
            self.retcode = p.returncode
            self.has_run = True

            if self.retcode != 0:
                pritn(self.command)
                print(stdout)
                print(stderr)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            err = ["ERROR: Unable to run command",
                   "command used:",
                   self.command,
                   "python exception:",
                   str(e),
                   str(exc_type),
                   str(fname),
                   str(exc_tb.tb_lineno)]
            try:
                err.extend(["command stdout:", "{}".format(self.stdout)])
            except:
                pass
            try:
                err.extend(["command stderr:", "{}".format(self.stderr)])
            except:
                pass

            print("\n".join(err), file=sys.stderr)
            sys.exit(1)
