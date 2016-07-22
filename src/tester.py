#!/usr/bin/env python3

from math import isnan, isinf

import argparse
import glob
import multiprocessing
import os.path as path
import multiprocessing.pool as pool
import re
import struct
import subprocess
import sys
import time


STATUS_FMT = {"FAILED"    : lambda t : red(bold(t)),
              "TIMEOUT"   : lambda t : cyan(t),
              "UNKNOWN"   : lambda t : yellow(t),
              "CLOSE"     : lambda t : green(t),
              "FAR"       : lambda t : green(bold(t)),
              "BAD_CLOSE" : lambda t : magenta(t),
              "BAD_FAR"   : lambda t : magenta(bold(t)),}

STATUS_COUNT = {"FAILED"    : 0,
                "TIMEOUT"   : 0,
                "UNKNOWN"   : 0,
                "CLOSE"     : 0,
                "FAR"       : 0,
                "BAD_CLOSE" : 0,
                "BAD_FAR"   : 0,}


if sys.stdout.isatty():
  do_fmt = True
else:
  do_fmt = False

def fmt(tag, text):
  if do_fmt:
    return tag+text+'\033[0m'
  else:
    return text

  
def bold(text):
  return fmt('\033[1m', text)


def color(color_code, text):
  return fmt('\033[0;3{}m'.format(color_code), text)
             

def red(text):
  return color(1, text)

def green(text):
  return color(2, text)

def yellow(text):
  return color(3, text)

def blue(text):
  return color(4, text)

def magenta(text):
  return color(5, text)

def cyan(text):
  return color(6, text)

  
def compare_result(expected, result, timeoutp):
  if isnan(result):
    if timeoutp:
      return "TIMEOUT"
    else:
      return "FAILED"

  if isnan(expected):
    return "UNKNOWN"
  
  res = "CLOSE" if are_close(expected, result) else "FAR"
  if not are_rigerous(expected, result):
    res = "BAD_"+res
  return res


def get_expected(filename):
  with open(filename, 'r') as f:
    data = f.read()
    
  ansmatch = re.search(r'\#[ \t]*answer:[ \y]*([^ \n]+)', data)
  maxmatch = re.search(r'\#[ \t]*maximum:[ \y]*([^ \n]+)', data)
  minmatch = re.search(r'\#[ \t]*minimum:[ \y]*([^ \n]+)', data)

  if DREAL:
    if minmatch:
      return float(minmatch.group(1) if minmatch.group(1)!="?" else 'nan')
    else:
      return float('nan')

  else:
    if ansmatch:
      return float(ansmatch.group(1) if ansmatch.group(1)!="?" else 'nan')
    elif maxmatch:
      return float(maxmatch.group(1) if maxmatch.group(1)!="?" else 'nan')
    else:
      return float('nan')



def to_ulps(x):
  n = struct.unpack('<q', struct.pack('<d', x))[0]
  return -(n + 2**63) if n < 0 else n


def ulps_between(x, y):
  return abs(to_ulps(x) - to_ulps(y))
  
    
def are_close(expected, result):
  if isinf(expected) and isinf(result):
    return (0, True)
  ulps_diff = ulps_between(expected, result)
  return ulps_diff < 2**(52-8)
  

def are_rigerous(expected, result):
  if isinf(expected) and isinf(result):
    return True

  if DREAL:
    return expected >= result
  else:
    return expected <= result


def process_test(cmd, test, expected):
  basename = path.basename(cmd[1])
  cmd = " ".join(cmd)
  

  t0 = time.time()
  p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err  = p.communicate()
  out = out.decode('utf-8')
  err = err.decode('utf-8')
  elapsed = time.time() - t0

  # get the test results
  result = support.get_result(out+err)
  state = compare_result(expected, result, elapsed>=TIMEOUT)

  printstate = STATUS_FMT[state](state)
  ulps = ulps_between(expected, result)
  expected = 'unknown' if isnan(expected) else expected
  result = 'no answer found' if isnan(result) else result

  
  if CSV:
    str_result = "{}, {}, {}, {}, {}, {}".format(basename,
                                                 expected,
                                                 result,
                                                 elapsed,
                                                 state,
                                                 ulps)
  else:
    str_result = "{}\n".format(cmd)
    str_result += "State:    {}\n".format(printstate)
    str_result += "Expected: {}\n".format(expected)
    str_result += "Result:   {}\n".format(result)
    str_result += "ULPs:     {}\n".format(int(ulps))
    str_result += "Time:     {}\n\n".format(elapsed)

  return str_result, state


def tally_result(tup):
  """
  Tallies the result of each worker. This will only be called by the main thread.
  """
  str_result, state = tup
  print(str_result, flush=True)
  STATUS_COUNT[state] += 1

support = None
def main():
  """
  Main entry point for the test suite.
  """
  global TIMEOUT, support, CSV, DREAL
  t0 = time.time()
  num_cpus = multiprocessing.cpu_count()//2

  # configure the CLI
  parser = argparse.ArgumentParser()
  parser.add_argument("--flags", nargs="+", help="Additional command line arguments for the tool under test", default=[])
  parser.add_argument("--threads", action="store", dest="n_threads", default=num_cpus, type=int,
                      help="execute regressions using the selected number of threads in parallel")
  parser.add_argument("--exe", type=str, help="What executable to run", default="gelpia")
  parser.add_argument("--timeout", type=int, help="How long each executable has, 0 for no timout", default=60)
  parser.add_argument("--dreal", action='store_const', const=True, default=False)
  parser.add_argument("--csv", action='store_const', const=True, default=False)
  parser.add_argument("benchmark_dir")
  args = parser.parse_args()

  TIMEOUT = args.timeout
  CSV = args.csv
  DREAL = args.dreal
  flags = args.flags
  
  # change mode
  if args.dreal:
    flags += ["--dreal"]
  else:
    flags += []

  exe = args.exe
  base = path.basename(args.exe)
  if base == "gelpia":
    exten = ".txt"
    pref = "@"
    import gelpia_test_support as support
  elif base == "dop_gelpia":
    exten = ".dop"
    pref = ""
    import gelpia_test_support as support
  elif base == "dOp_wrapper":
    exten = ".dop"
    pref = ""
    flags = []
    import dop_test_support as support
  else:
    print(yellow("WARNING") + ": assuming gelpia compatable executable")
    exten = ".txt"
    pref = "@"
    import gelpia_test_support as support
  
  try:
    # start the tests
    print("Running benchmarks...")

    # start processing the tests.
    results = []
    tests = sorted(glob.glob(path.join(args.benchmark_dir,"**"),
                             recursive=True))
    tests = [f for f in tests if f.endswith(exten)]
    total = len(tests)
    print("{} benchmarks to process".format(total))
    
    n_threads = min(total+1, args.n_threads)
    print("Creating Pool with '{}' Workers\n".format(n_threads), flush=True)
    p = multiprocessing.pool.ThreadPool(processes=n_threads)

    if CSV:
      print("File, Expected, Result, Time, Status, approximate ULPs between")
      
    for test in tests:
      # build up the subprocess command
      cmd = [exe,
             pref+test,
             "-t {}".format(args.timeout)] + flags
      expected = get_expected(test)

      if False:#"bad hack ian should remove":
        tally_result(process_test(cmd[:], test, expected))
      else:
        r = p.apply_async(process_test,
                          args=(cmd[:], test, expected),
                          callback=tally_result)
        results.append(r)

    # keep the main thread active while there are active workers
    for r in results:
      r.wait()

  except KeyboardInterrupt:
    print("\nCaught KeyboardInterrupt, terminating workers")
    p.terminate() # terminate any remaining workers
    p.join()
  else:
    print("\nQuitting normally")
    # close the pool. this prevents any more tasks from being submitted.
    p.close()
    p.join() # wait for all workers to finish their tasks

  # log the elapsed time
  elapsed_time = time.time() - t0
  print(' ELAPSED TIME [{}]'.format(round(elapsed_time, 2)))

  # log the test results
  statuses = sorted(STATUS_COUNT.keys())
  maxlabel = max([len(s) for s in statuses])
  fmtstr = "{{:{}}}".format(maxlabel)
  for status in statuses:
    label = fmtstr.format(status)
    print("{} : {}".format(STATUS_FMT[status](label), STATUS_COUNT[status]))

  if (total != sum(STATUS_COUNT.values())):
    print(red("\nERROR:")+"number of tests does not equal total, there is a bug in {}".format(sys.argv[0]))


if __name__=="__main__":
  main()

