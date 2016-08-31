import re

def get_result(output):
  match = re.findall(r'min_\d+ += +\[([^,]+), +[^\]]+\]', output)
  if match != []:
    return sum([float(m) for m in match])
  else:
    print(output)
    return float('nan')
