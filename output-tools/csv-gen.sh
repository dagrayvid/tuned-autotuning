search_dir=results/

#header:
echo "iteration1,iteration2,iteration3,iteration4,$(cat results/220319140844-tuned.yaml | grep '=[0-9]\+' | awk -F= 'NF--' | awk '{$1=$1};1' | paste -sd,)"

for f in $search_dir/*-hammerdb.log
do
    hammerdb_file=$(basename $f)
    tuned_yaml="${hammerdb_file:0:12}-tuned.yaml"
    tunable_vals=$(cat $search_dir/$tuned_yaml | grep -o '=[0-9]\+' | cut -c2-  | paste -sd,)
    hammerdb_results=$(cat $search_dir/$hammerdb_file | grep "NOPM:" | awk '{print $2}' | paste -sd,)
    echo "$hammerdb_results,$tunable_vals"
    #cat $f | grep "NOPM:" | awk '{print $2}' | paste -sd,
done
