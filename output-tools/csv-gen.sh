search_dir=$1

#header:
echo "trial name, tunable, results1, results2, results3,  min, pressure, max"

for f in $search_dir/*
do
    trial_name=$(basename $f | cut -d '-' -f2,3 | sed 's/-/,/g')
    tunables=$(cat "$f/tuned.yaml" | grep -o '\S*=[0-9].*$' | sed 's/=/,/;s/   /,/g' | sed -z 's/\n/,/g;s/,$/\n/')
    results=$(cat $f/result.csv)
    echo "$trial_name,$results,$tunables"
done
