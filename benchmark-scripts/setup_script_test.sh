#! /bin/bash
set -eu


# This script assumes you have labeled the system under test with the node label hammerdb-sut=database
# and that you have set the pin node settings in the files ./yaml/benchmark-setup.yaml and ./yaml/benchmark-cr.yaml

volumes_yaml="benchmark-scripts/yaml/postgres-volumes.yaml"
database_yaml="benchmark-scripts/yaml/postgres-db.yaml"
db_build_yaml="benchmark-scripts/yaml/benchmark-setup.yaml"
postgres_backup_yaml="benchmark-scripts/yaml/postgres-backup.yaml"
poll_interval=10



# Copy database to backup
oc apply -f $postgres_backup_yaml

# Wait up to 15 minutes for copy to complete
db_backup_status=$(oc get po -n postgres-db | grep db-backup | awk '{print $3}')
total_wait_time=0
max_wait_time=7200
until [[ $db_backup_status = "Completed" ]]
do
  if (( total_wait_time > max_wait_time )); then
    echo "benchmark run took longer than $max_wait_time seconds, exiting"
    exit 1
  fi
  sleep $poll_interval
  total_wait_time=$((total_wait_time + $poll_interval))
  db_backup_status=$(oc get po -n postgres-db | grep db-backup | awk '{print $3}')
done
