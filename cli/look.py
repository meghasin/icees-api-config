import sys
from tabulate import tabulate
import pandas as pd

input_file_path = sys.argv[1]
df = pd.read_csv(input_file_path, dtype=str, na_filter=False)
print(tabulate(df.values.tolist(), tablefmt="grid", headers=list(df.columns)))
    
    


