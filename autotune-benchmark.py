import sys, os, subprocess
import argparse
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

def run_benchmark_with_tunables(benchmark_script, tunables, output_dir):
    tuned_yaml="{}/tuned.yaml".format(output_dir)
    # Create tuned profile
    template_from_tunable_dict(tunables, "tuned.yaml.j2", tuned_yaml)
    
    # Call benchmark shell script, with created Tuned YAML file and expected output file as args.
    process_result = subprocess.run(["bash", benchmark_script, tuned_yaml, output_dir], stdout=subprocess.PIPE)
    # Save script logs to a logfile
    output=process_result.stdout.decode('utf-8')
    with open("{}/script-logs.txt".format(output_dir), "w") as script_output:
        script_output.write(output)

    if process_result.returncode != 0:
        print("ERROR in benchmark, will be pruned")
        return "Nan", "prune"
    else:
        # read from output from script itself
        benchmark_result=""
        with open("{}/result.csv".format(output_dir)) as f:
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

    def __init__(self, tunables, benchmark_script, output_dir):
        self.tunables = tunables
        self.benchmark_script = benchmark_script
        self.output_dir = output_dir
    
    def __call__(self, trial):
        study_tunables = {}
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
            elif tunable["value_type"].lower() == "int_min_mid_max":
                tunable_max = trial.suggest_int(
                        "{}_max".format(tunable["name"]), tunable["lower_bound"]+2*tunable["step"], tunable["upper_bound"], tunable["step"]
                )
                tunable_mid = trial.suggest_int(
                        "{}_mid".format(tunable["name"]), tunable["lower_bound"]+tunable["step"], tunable_max, tunable["step"]
                )
                tunable_min = trial.suggest_int(
                        "{}_min".format(tunable["name"]), tunable["lower_bound"], tunable_mid, tunable["step"]
                )
                tunable_value = "{}   {}   {}".format(tunable_min, tunable_mid, tunable_max)

            study_tunables[tunable["name"]] = tunable_value 

        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        trial_output_dir = "{}/trial-{}-{}".format(self.output_dir, str(trial.number).zfill(3), timestamp)
        pathlib.Path(trial_output_dir).mkdir(parents=True, exist_ok=True) 
        result, status = run_benchmark_with_tunables(self.benchmark_script, study_tunables, trial_output_dir)

        if status == "prune":
            raise optuna.TrialPruned()
        
        return result

def get_args(study_name):
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=str, default="results/{}".format(study_name), help="Output dir for all experiment results and logs. Default is results/study-<timestamp>. Will be created if it does not exist.")
    parser.add_argument('--tunables', type=str, default="setup/tunables.yaml", help="File name of tunables configuration file. See setup/tunables.yaml")
    parser.add_argument('--direction', type=str, required=True, help="Direction for objective function optimization. Must be minimize or maximize")
    parser.add_argument('--iterations', type=int, default=100, help="Number of trials to run.")
    parser.add_argument('--fixed-trials', action='store_true', help="A set of fixed trials / defaults may be set in the tunables YAML file (defined by --tunables), to be used as initial values for the optimizer to try if --fixed-trials is set.")
    parser.add_argument('--no-fixed-trials', action='store_false', help="Disable the fixed trials (this is the default.)")
    parser.set_defaults(fixed_trials=False)
    parser.add_argument('--benchmark-script', default="benchmarks/hammerdb-postgres/run_hammerdb_with_profile.sh", help="Bash script that runs benchmark. Expected to apply the Tuned YAML file supplied by $1, and output a single line of comma separated results from the  trials to the file in $2/result.csv.")

    return parser.parse_args()


timestamp = datetime.now().strftime("%y%m%d%H%M")
study_name="study-{}".format(timestamp)
args = get_args(study_name)

output_dir=args.output_dir
pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True) 

tunables_list = get_all_tunables(args.tunables)
fixed_trial_tunables = get_fixed_trials(tunables_list)

storage_name = "sqlite:///{}/{}.db".format(output_dir, study_name) # create a persistent sqlite DB saved in the output_dir for this study.
study = optuna.create_study(study_name=study_name, direction=args.direction, sampler=optuna.samplers.TPESampler(multivariate=True, n_startup_trials=8), storage=storage_name)

# Fixed trials for any defaults or suggestions found in tunables_list
if args.fixed_trials:
    print("Queuing fixed trials:")
    for known_config in fixed_trial_tunables.keys():
        print(fixed_trial_tunables[known_config])
        study.enqueue_trial(fixed_trial_tunables[known_config])

study.optimize(Objective(tunables_list, args.benchmark_script, output_dir), n_trials=args.iterations)

study.best_params
