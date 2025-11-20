import time
import pandas as pd

def measure_query_time(conn, query):
    """Measure execution time of a SQL query."""
    start = time.time()
    pd.read_sql_query(query, conn)
    end = time.time()
    return round(end - start, 4)
