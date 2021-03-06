#!/bin/bash 
# Run experiment for the relation of sample size to convergent and length of 
# the data. 

# 2020-7-28 
set -o noclobber 
label=20-08-16
m=4
r=0.3
sn=10
result_file=result/linux/output_sample-size_n_m${m}_r${r}_sn${sn}_ecg_$label.txt 
if [ -e $result_file ]; then 
    echo "Output file [$result_file] exists. " >&2 
    exit 1
fi 
python script/run_ex_sample-size_n.py \
    -m $m \
    -r $r \
    --input-format multi-record \
    --database-label $label \
    --sample-num $sn \
   > $result_file 
