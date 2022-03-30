
import sys, os, subprocess
import statistics
import optuna
import yaml
import random
import pathlib
from datetime import datetime

# read from output from script itself
output_dir="results/experiment-2203281359/trial-0-220328135911"

benchmark_result=""
with open("{}/benchmark-result.csv".format(output_dir)) as f:
    benchmark_result = f.readline()

results = [float(result) for result in benchmark_result.split(',')]
mean = statistics.mean(results)
stddev = statistics.stdev(results)
print("RESULT -- mean: {}, std. dev: {}".format(mean, stddev))
