import re

def get_result(output, DREAL):
  output = "".join([line for line in output.splitlines() if not line.startswith("Parsing") and not line.startswith("Solver")])
  output = output.replace("Stopping early...","")

  try:
    lst = eval(output, {'inf':float('inf')})
  except:
    #print(output)
    return float('nan'), float('nan')
  l, h = float(lst[0][0]), float(lst[0][1])
  if l > h:
    print("\n\n\n\n\nUPSIDE DOWN\n\n\n\n\n")
  return l, h

