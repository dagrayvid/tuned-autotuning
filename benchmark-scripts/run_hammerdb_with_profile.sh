#! /bin/bash

set -eu

profile_yaml=$1
results_dir=$2
database_yaml="benchmark-scripts/yaml/postgres-db.yaml"
benchmark_yaml="benchmark-scripts/yaml/benchmark-cr.yaml"
postgres_load_from_backup="benchmark-scripts/yaml/postgres-load-from-backup.yaml"
timestamp=$(date +%y%m%d%H%M%S)
poll_interval=10


cleanup() {
  oc delete -f $profile_yaml 2>&1 || true
  oc delete -f $postgres_load_from_backup  2>&1 || true
  oc delete -f $database_yaml 2>&1 || true
  oc delete -f $benchmark_yaml  2>&1 || true
}
trap cleanup EXIT

# Create profile
oc apply -f $profile_yaml

#TODO Should probably add some logic to this script to pick the node... 
# or need some configuration script to setup the cluster
profile_applied=""
total_wait_time=0
max_wait_time=600
until [[ $profile_applied = "True" ]]
do
  if (( total_wait_time > max_wait_time )); then
    oc get profile/$profile -n openshift-cluster-node-tuning-operator -o json >> $results_dir/$timestamp-profile-ERROR.json
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  profile=$(oc get profile -n openshift-cluster-node-tuning-operator | grep openshift-hammerdb | awk '{print $1}')
  profile_applied=$(oc get profile/$profile -n openshift-cluster-node-tuning-operator -o json | jq '.status.conditions[] | select(.type == "Applied") | .status' | tr -d '"')
done

oc delete -f $database_yaml 2>&1 || true
sleep 30 #Make sure database has time to delete

oc apply -f $postgres_load_from_backup
# Wait for Pod to be Completed
db_reset_status=$(oc get po -n postgres-db | grep db-reset | awk '{print $3}')
total_wait_time=0
max_wait_time=600
until [[ $db_reset_status = "Completed" ]]
do
  if (( total_wait_time > max_wait_time )); then
    echo "database reinit took longer than $max_wait_time seconds, exiting"
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  db_reset_status=$(oc get po -n postgres-db | grep db-reset | awk '{print $3}')
done

oc apply -f $database_yaml
db_pod_status=$(oc get po -n postgres-db | grep postgres-deployment-* | awk '{print $3}')
total_wait_time=0
max_wait_time=600
until [[ $db_pod_status = "Running" ]]
do
  if (( total_wait_time > max_wait_time )); then
    echo "db pod took longer than $max_wait_time seconds to start running"
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  db_pod_status=$(oc get po -n postgres-db | grep postgres-deployment-* | awk '{print $3}')
done

#TODO Check the database autogenerated config
#TODO Need some intelligence around when / if we need to initialize the database
oc apply -f $benchmark_yaml
# Wait for Pod to be Completed
benchmark_pod_status=$(oc get po -n benchmark-operator | grep hammerdb-benchmark-workload-* | awk '{print $3}')
total_wait_time=0
max_wait_time=7200
until [[ $benchmark_pod_status = "Completed" ]]
do
  if (( total_wait_time > max_wait_time )); then
    echo "benchmark run took longer than $max_wait_time seconds, exiting"
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  benchmark_pod_status=$(oc get po -n benchmark-operator | grep hammerdb-benchmark-workload-* | awk '{print $3}')
done

benchmark_pod=$(oc get pods -n benchmark-operator | grep "hammerdb-benchmark-workload" | awk '{print $1}')

# Save results of benchmark
oc logs -n benchmark-operator pod/$benchmark_pod >> $results_dir/$timestamp-hammerdb.log

# Send result to stdout as a comma separated list of the NOPM numbers
oc logs -n benchmark-operator pod/$benchmark_pod | grep "NOPM:" | awk '{print $2}' | paste -sd, | tee $results_dir/benchmark-result.csv

