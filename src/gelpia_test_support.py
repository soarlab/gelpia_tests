

def get_result(output, DREAL):
  output = "".join([line for line in output.splitlines()
                    if not line.startswith("Parsing")
                    and not line.startswith("Solver")])
  retoutput = output.replace("Stopping early...","")

  try:
    lst = eval(retoutput, {'inf' : float('inf')})
  except:
    return float('nan'), float('nan')

  l, h = float(lst[0][0]), float(lst[0][1])
  if l > h:
    print(" |   |   |   |               |   |   |   |")
    print(" |   |   |   |               |   |   |   |")
    print(" V   V   V   V  UPSIDE DOWN  V   V   V   V")
  return l, h
