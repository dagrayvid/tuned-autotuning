#!/usr/bin/python3

import sys
import csv
import yaml

csvdict= {}

with open('input.csv', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    tunables = []
    for row in reader:
        sec = row[0]
        tunable = row[1]
        tunable_dict = {}
        tunable_dict["name"] = tunable
        tunable_dict["value_type"] = row[2]
        tunable_dict["lower_bound"] = int(row[3])
        tunable_dict["upper_bound"] = int(row[4])
        tunable_dict["step"] = int(row[5])
        tunable_dict["set_values"] = []
        profiles_start = 6
        for i, val in enumerate(row[profiles_start:len(row)]):
            if val != "":
                print("adding set value for tunable {}, profile {}: {}".format(tunable, header[profiles_start + i], val))
                set_value_dict = {}
                set_value_dict["name"] = header[profiles_start + i]
                set_value_dict["value"] = int(val)
                tunable_dict["set_values"].append(set_value_dict)
        tunables.append(tunable_dict)
    full_tunables_yaml = {"tunables": tunables}

out = open('tunables.yaml', 'w+')
yaml.dump(full_tunables_yaml, out,  default_flow_style=False)
