#! /bin/bash

# To be used to test the autotuning framework, will always return random results

sleep 5
echo $((1 + $RANDOM % 1000)),$((1 + $RANDOM % 1000)),$((1 + $RANDOM % 1000)),$((1 + $RANDOM % 1000)),$((1 + $RANDOM % 1000)) >> $2/result.csv