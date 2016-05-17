import re

def get_result(output):
  match = re.search(r'\[([^,]+), \{', output)
  if match:
    return float(match.group(1))
  else:
    return float('nan')

  
