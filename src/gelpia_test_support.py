import re

def get_result(output):
  output = "".join([line for line in output.splitlines() if not line.startswith("Parsing") and not line.startswith("Solver")])
  
  try:
    lst = eval(output, {'inf':float('inf')})
  except:
    print(output)
    return float('nan')

  if type(lst[0]) is list:
    return lst[0][1]
  else:
    return lst[0]

  
