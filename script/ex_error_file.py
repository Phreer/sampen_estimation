import os
import sys
import math
import glob
import argparse
import time
import logging 

import sampen

import database as db 

sess = db.Session() 
logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser('ex_error.py')
parser.add_argument('-n', type=int, default=0, help='The length of data to compute, 0 for total file. ')
parser.add_argument('-m', type=int, required=True, help='The template length m. ')
parser.add_argument('-r', type=float, default=0.1, help='The threshold r. ')
parser.add_argument('-ss', '--sample-size', type=int, required=True, help='The number of points to sample. ')
parser.add_argument('-sn', '--sample-num', type=int, required=True, help='The number of results to be averaged. ')
parser.add_argument('-if', '--input-format', type=str, default='simple', choices=['simple', 'multi-record'], 
                    help='The format of the input file. If set to be simple, then there is one record '
                    'in the file, and each line contains a single column. If set to be multi-record, '
                    'then multiple records may be contained in the file, and each there are NUM_RECORD + 1 '
                    'columns per line, of which the first is the line number and the rest NUM_RECORD '
                    'ones are signals. ')

def readfile(filename, n=None, input_format='simple'):
    """
    Read a file to a list or lists of integers with length `n`, according to 
    the `input_format`.. 

    @note: The file is supposed to be lines of integers. 
    """
    with open(filename) as f:
        lines = f.readlines()

    if input_format == 'simple': 
        result = list()
        count = 0
        for line in lines:
            if (line.strip()):
                result.append(int(line))
                count += 1
                if count == n: 
                    break 
        result = (result, )
    elif input_format == 'multi-record':
        result = list() 
        count = 0
        for line in lines:
            if line.strip():
                result.append(map(int, line.split()[1:]))
                count += 1
                if count == n:
                    break 
        result = tuple(map(list, zip(*result)))
    
    return result

def variance(data):
    m = sum(data) / len(data)
    data_ = [(d - m) ** 2 for d in data]
    return sum(data_) / len(data)

def search_result(record_name, m, r, length, method, sample_size=None, 
                  sample_num=None, paralleled=True): 
    kwargs = dict(record_name=record_name, m=m, r=r, length=length, method=method, 
                  paralleled=paralleled) 
    if method in ['QMC (presort)', 'QMC']: 
        kwargs['sample_size'] = sample_size 
        kwargs['sample_num'] = sample_num
    return sess.query(db.Result).filter_by(**kwargs).first() 

def experiment(data, record_name, m, r, sample_size, sample_num):
    var = variance(data)
    r_scaled = int(r * math.sqrt(var))
    n = len(data)

    print('=' * 76)
    print('{:<16}: {}'.format('record name', record_name)) 
    print('{:<16}: {}'.format('data length', n))
    print('{:<16}: {}'.format('template length', m))
    print('{:<16}: {}'.format('threshold (r)', r))
    print('{:<16}: {}'.format('threshold (r_scaled)', r_scaled))
    print('{:<16}: {}'.format('sample size', sample_size))
    print('{:<16}: {}'.format('sample num', sample_num))
    print('{:<16}: {:.4}'.format('variance', var))
    print('=' * 76)

    result_d = search_result(record_name, m, r, n, 'direct', paralleled=True) 
    if result_d: 
        result_src = 'database'
        t_d = result_d.computation_time 
        sampen_d = result_d.sample_entropy 
        a_d = result_d.a 
        b_d = result_d.b 
    else: 
        result_src = 'computation'
        t = time.time()
        sampen_d, a_d, b_d = sampen.compute_sampen_direct(data, m, r)
        t_d = time.time() - t
        result_d = db.Result(record_name=record_name, 
                             method='direct', 
                             length=n, 
                             m=m, 
                             r=r, 
                             paralleled=True, 
                             instance=1, 
                             sample_entropy=sampen_d, 
                             a=a_d, 
                             b=b_d, 
                             computation_time=t_d)
        sess.add(result_d)

    
    print('method: direct')
    print('\t{:<30}: {}'.format('result source', result_src))
    print('\t{:<30}: {:.4f}'.format('time', t_d))
    print('\t{:<30}: {:.6}'.format('sample entropy (direct)', sampen_d))
    print('\t{:<30}: {:.2e} ({:.2e})'.format('a', a_d, a_d / n / n))
    print('\t{:<30}: {:.2e} ({:.2e})'.format('b', b_d, b_d / n / n))

    # Method: QMC 
    result_q1 = search_result(record_name, m, r, n, 'QMC', paralleled=True, 
                               sample_size=sample_size, sample_num=sample_num) 
    if result_q1: 
        result_src = 'database'
        t_q1 = result_q1.computation_time 
        sampen_q1 = result_q1.sample_entropy 
        a_q1 = result_q1.a 
        b_q1 = result_q1.b 
    else: 
        result_src = 'computation'
        print('\t{:<30}: {}'.format('result source', 'computation'))
        t = time.time()
        sampen_q1, a_q1, b_q1 = sampen.compute_sampen_qr(
            data, m, r, sample_size, sample_num, False)
        t_q1 = time.time() - t
        result_q1 = db.Result(record_name=record_name, 
                              method='QMC', 
                              length=n, 
                              m=m, 
                              r=r, 
                              sample_size=sample_size, 
                              sample_num=sample_num, 
                              paralleled=True, 
                              instance=1, 
                              sample_entropy=sampen_q1, 
                              a=a_q1, 
                              b=b_q1, 
                              computation_time=t_q1)
        sess.add(result_q1)
    print('method: QMC')
    print('\t{:<30}: {}'.format('result source', result_src))
    print('\t{:<30}: {:.4f}'.format('time', t_q1))
    print('\t{:<30}: {:.6f}'.format('sample entropy (qr1)', sampen_q1))
    err = (sampen_q1 - sampen_d) / (sampen_d + 1e-8)
    print('\t{:<30}: {:.2e}'.format('absolute error', sampen_q1 - sampen_d))
    print('\t{:<30}: {:.2e}'.format('relative error', err))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('a', a_q1, a_q1 / sample_size / sample_size))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('b', b_q1, b_q1 / sample_size / sample_size))

    print('\t{:<30}: {:.2e}'.format('error of a', a_q1 / sample_size / sample_size - a_d / n / n))
    print('\t{:<30}: {:.2e}'.format('error of b', b_q1 / sample_size / sample_size - b_d / n / n))

    # method: QMC (presort) 
    result_q2 = search_result(record_name, m, r, n, 'QMC', paralleled=True, 
                              sample_size=sample_size, sample_num=sample_num) 
    if result_q2: 
        result_src = 'database'
        t_q2 = result_q2.computation_time 
        sampen_q2 = result_q2.sample_entropy 
        a_q2 = result_q2.a 
        b_q2 = result_q2.b 
    else: 
        result_src = 'computation'
        t = time.time()
        sampen_q2, a_q2, b_q2 = sampen.compute_sampen_qr(
            data, m, r, sample_size, sample_num, False)
        t_q2 = time.time() - t
        result_q2 = db.Result(record_name=record_name, 
                              method='QMC', 
                              length=n, 
                              m=m, 
                              r=r, 
                              sample_size=sample_size, 
                              sample_num=sample_num, 
                              paralleled=True, 
                              instance=1, 
                              sample_entropy=sampen_q2, 
                              a=a_q2, 
                              b=b_q2, 
                              computation_time=t_q2)
        sess.add(result_q2)
    print('method: quasi-Monte Carlo (presort)')
    print('\t{:<30}: {}'.format('result source', result_src))
    print('\t{:<30}: {:.4f}'.format('time', t_q2))
    print('\t{:<30}: {:.6f}'.format('sample entropy', sampen_q2))
    err = (sampen_q2 - sampen_d) / (sampen_d + 1e-8)
    print('\t{:<30}: {:.2e}'.format('absolute error', sampen_q2 - sampen_d))
    print('\t{:<30}: {:.2e}'.format('relative error', err))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('a', a_q2, a_q2 / sample_size / sample_size))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('b', b_q2, b_q2 / sample_size / sample_size))
    print('\t{:<30}: {:.2e}'.format('error of a', a_q2 / sample_size / sample_size - a_d / n / n))
    print('\t{:<30}: {:.2e}'.format('error of a', b_q2 / sample_size / sample_size - b_d / n / n))

    # method: MC (uniform) 
    result_u = search_result(record_name, m, r, n, 'MC (uniform)', 
                             paralleled=True, 
                             sample_size=sample_size, 
                             sample_num=sample_num) 
    if result_u: 
        result_src = 'database'
        t_u = result_u.computation_time 
        sampen_u = result_u.sample_entropy 
        a_u = result_u.a 
        b_u = result_u.b 
    else: 
        result_src = 'computation'
        t = time.time()
        sampen_u, a_u, b_u = sampen.compute_sampen_qr(
            data, m, r, sample_size, sample_num, False)
        t_u = time.time() - t
        result_u = db.Result(record_name=record_name, 
                              method='MC (uniform)', 
                              length=n, 
                              m=m, 
                              r=r, 
                              sample_size=sample_size, 
                              sample_num=sample_num, 
                              paralleled=True, 
                              instance=1, 
                              sample_entropy=sampen_u, 
                              a=a_u, 
                              b=b_u, 
                              computation_time=t_u)
        sess.add(result_u)

    print('method: MC (uniform)')
    print('\t{:<30}: {}'.format('result source', result_src))
    print('\t{:<30}: {:.4f}'.format('time', t_u))
    print('\t{:<30}: {:.6f}'.format('sample entropy', sampen_u))
    err = (sampen_u - sampen_d) / (sampen_d + 1e-8)
    print('\t{:<30}: {:.2e}'.format('absolute error', sampen_u - sampen_d))
    print('\t{:<30}: {:.2e}'.format('relative error', err))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('a', a_u, a_u / sample_size / sample_size))
    print('\t{:<30}: {:.2e}, ({:.2e})'.format('b', b_u, b_u / sample_size / sample_size))
    print('\t{:<30}: {:.2e}'.format('error of a', a_u / sample_size / sample_size - a_d / n / n))
    print('\t{:<30}: {:.2e}'.format('error of a', b_u / sample_size / sample_size - b_d / n / n))
    sess.commit() 

def main():
    files = ['data.PhysioNet/chfdb/chf01.txt', 
             'data.PhysioNet/ltafdb/00.txt', 
             'data.PhysioNet/ltstdb/s20011.txt',
             'data.PhysioNet/mit-bih-long-term-ecg-database-1.0.0/14046.txt']

    args = parser.parse_args()
    
    for file_ in files: 
        record = readfile(file_, args.n, input_format=args.input_format)
        experiment(record[0], '%s (%d)' % (file_, 1), args.m, args.r, 
                   args.sample_size, args.sample_num)

if __name__ == '__main__':
    main()
