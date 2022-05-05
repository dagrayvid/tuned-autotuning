#! /bin/bash

set -eu

profile_yaml=$1
results_dir=$2
benchmark_yaml="benchmarks/iperf3/yaml/pod.yaml"
pod_name="pts-1cpu"

timestamp=$(date +%y%m%d%H%M%S)
poll_interval=10

cleanup() {
  oc delete -f $profile_yaml 2>&1 || true
  oc delete -f $benchmark_yaml  2>&1 || true
}
trap cleanup EXIT

# Create profile
oc apply -f $profile_yaml

#TODO Should probably add some logic to this script to pick the node...
# or need some configuration script to setup the cluster
profile_applied=""
total_wait_time=0
max_wait_time=300
until [[ $profile_applied = "True" ]]
do
  if (( total_wait_time > max_wait_time )); then
    oc get profile/$profile -n openshift-cluster-node-tuning-operator -o json >> $results_dir/$timestamp-profile-ERROR.json
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  profile=$(oc get profile -n openshift-cluster-node-tuning-operator | grep iperf3 | awk '{print $1}')
  profile_applied=$(oc get profile/$profile -n openshift-cluster-node-tuning-operator -o json | jq '.status.conditions[] | select(.type == "Applied") | .status' | tr -d '"')
done

#TODO check whether tunables are set
node_name=$(oc get nodes --selector='iperf3-sut' | tail -n1 | awk '{print $1}')
tuned_pod_name=$(oc get po -n openshift-cluster-node-tuning-operator -o wide | grep $node_name | awk '{print $1}')

cat $profile_yaml | sed -n -e 's/^\s*\(.*\)=/\1 /p' | tail -n +2 > $results_dir/tunables-list.txt
while read line;
do
	tunable=$(echo $line | awk '{print $1}')
	real_value=$(oc exec $tuned_pod_name -n openshift-cluster-node-tuning-operator -- sysctl -a |  grep $tunable | sed -n 's/.*=//p')
	echo "$line, real: $real_value" >> $results_dir/tunables-validation.txt
done < $results_dir/tunables-list.txt

oc apply -f $benchmark_yaml
# Wait for Pod to be Completed
benchmark_pod_status=$(oc get po | grep $pod_name | awk '{print $3}')
total_wait_time=0
poll_interval=5
max_wait_time=180
until [[ $benchmark_pod_status = "Completed" ]]
do
  if (( total_wait_time > max_wait_time )); then
    echo "benchmark run took longer than $max_wait_time seconds, exiting"
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + poll_interval))
  benchmark_pod_status=$(oc get pods | grep $pod_name | awk '{print $3}')
  echo "$total_wait_time, $benchmark_pod_status"
done

logfile=$results_dir/$timestamp-iperf3-logs.txt
xmlfile=$results_dir/result.xml
# Save results of benchmark
oc logs pod/$pod_name >> $logfile

cat $logfile | sed -n '/<?xml/,$p' > $xmlfile

cat $xmlfile | grep -o -P '(?<=\<RawString\>).*(?=\</RawString\>)' | sed 's/:/,/g' >> $results_dir/result.csv


