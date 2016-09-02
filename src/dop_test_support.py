import re

def get_result(output, _):
  match = re.findall(r'min_\d+ += +\[([^,]+), +[^\]]+\]', output)
  if match != []:
    res = sum([float(m) for m in match])
    return res, res
  else:
    print(output)
    return float('nan'), float('nan')
