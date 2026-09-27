import sys
print("Starting...")
try:
    import pandas as pd
    print("pandas imported")
    import numpy as np
    print("numpy imported")
    import joblib
    print("joblib imported")
    from sklearn.ensemble import RandomForestClassifier
    print("sklearn imported")
except Exception as e:
    print(f"Error: {e}")
print("Done.")
