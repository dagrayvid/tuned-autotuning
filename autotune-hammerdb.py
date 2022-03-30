import sys, os, subprocess
import statistics
import optuna
import yaml
import random
import pathlib
from datetime import datetime

from nto_templating import template_from_tunable_dict

def get_all_tunables(tunables_file):
    with open(tunables_file, "r") as stream:
        try:
            tunables_yaml = yaml.safe_load(stream)
            print("--- READING TUNABLES FILE: {} ---".format(tunables_file))
            print("App: {}".format(tunables_yaml["application_name"]))
            for tunable in tunables_yaml["tunables"]:
                print("Tunable: {}, type: {}, min: {}, max: {}, step_size: {}".format(tunable["name"], tunable["value_type"], tunable["lower_bound"], tunable["upper_bound"], tunable["step"]))
            return tunables_yaml["tunables"]
        except yaml.YAMLError as exc:
            print(exc)

def get_fixed_trials(tunables):
    fixed_trials={}
    # Create initial sparse dict of dicts
    for tunable in tunables:
        for set_value in tunable["set_values"]:
            if set_value["name"] not in fixed_trials:
                fixed_trials[set_value["name"]] = {}
            fixed_trials[set_value["name"]][tunable["name"]] = set_value["value"]

    # Set values to default if not set in a given trial
    #TODO useful error message if no default set in YAML
    for trial_name in fixed_trials.keys():
        for tunable in tunables:
            if tunable["name"] not in fixed_trials[trial_name]:
                fixed_trials[trial_name][tunable["name"]] = fixed_trials["default"][tunable["name"]]

    return fixed_trials

def run_hammerdb_with_tunables(tunables, output_dir):
    tuned_yaml="{}/tuned.yaml".format(output_dir)
    # Create tuned profile
    template_from_tunable_dict(tunables, "tuned.yaml.j2", tuned_yaml)
    
    # run hammerdb and get result
    # call bash script passing in tuned.yaml filename
    process_result = subprocess.run(["bash", "benchmark-scripts/run_hammerdb_with_profile.sh", tuned_yaml, output_dir], stdout=subprocess.PIPE)
    if process_result.returncode != 0:
        print("ERROR in experiment, will be pruned")
        return "Nan", "prune"
    else:
        # Save script logs to a logfile
        output=process_result.stdout.decode('utf-8')
        with open("{}/script-logs.txt".format(output_dir), "w") as script_output:
            script_output.write(output)
        
        # read from output from script itself
        benchmark_result=""
        with open("{}/benchmark-result.csv".format(output_dir)) as f:
            benchmark_result = f.readline()

        results = [float(result) for result in benchmark_result.split(',')]
        mean = statistics.mean(results)
        stddev = statistics.stdev(results)
        print("RESULT -- mean: {}, std. dev: {}".format(mean, stddev))
        return mean, "success"


class Objective(object):
    """
    A class used to define search space and return the actual slo value.

    Parameters:
        tunables (list): A list containing the details of each tunable in a dictionary format.
    """

    def __init__(self, tunables, output_dir):
        self.tunables = tunables
        self.output_dir = output_dir
    
    def __call__(self, trial):
        experiment_tunables = {}
         # Define search space
        for tunable in self.tunables:
            if tunable["value_type"].lower() == "float":
                tunable_value = trial.suggest_float(
                    tunable["name"], tunable["lower_bound"], tunable["upper_bound"], tunable["step"]
                )
            elif tunable["value_type"].lower() == "int":
                tunable_value = trial.suggest_int(
                    tunable["name"], tunable["lower_bound"], tunable["upper_bound"], tunable["step"]
                )
            elif tunable["value_type"].lower() == "categorical":
                tunable_value = trial.suggest_categorical(tunable["name"], tunable["choices"])

            experiment_tunables[tunable["name"]] = tunable_value

        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        trial_output_dir = "{}/trial-{}-{}".format(self.output_dir, trial.number, timestamp)
        pathlib.Path(trial_output_dir).mkdir(parents=True, exist_ok=True) 
        result, status = run_hammerdb_with_tunables(experiment_tunables, trial_output_dir)

        if status == "prune":
            raise optuna.TrialPruned()
        
        return result

timestamp = datetime.now().strftime("%y%m%d%H%M")
#TODO make this a command line option with default
run_output_path="results/experiment-{}".format(timestamp)
pathlib.Path(run_output_path).mkdir(parents=True, exist_ok=True) 

#TODO make this a command line option with default
tunables_conf_file = "setup/tunables.yaml"
tunables_list = get_all_tunables(tunables_conf_file)
fixed_trials = get_fixed_trials(tunables_list)

#TODO make direction a command line option
study = optuna.create_study(direction="minimize")

# Fixed trials for any defaults or suggestions found in tunables_list
#TODO make this a command line option
for known_config in fixed_trials.keys():
    print("SKIPPING FIXED TRIAL  {}".format(known_config))
    print(fixed_trials[known_config])
    #study.enqueue_trial(fixed_trials[known_config])

study.optimize(Objective(tunables_list, run_output_path), n_trials=100)

study.best_params
