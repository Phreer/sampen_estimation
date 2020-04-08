import csv
import numpy as np

from matplotlib import pyplot as plt

if __name__ == '__main__':
    for m in range(3, 7):
        with open('result/wsl/process/219_gauss_sample-num_sample-size_m{}.csv'.format(m)) as f:
            lines = f.readlines()
        reader = csv.reader(lines)
        methods = ['Quasi-Random Sampling', 'KD-Tree Sampling']
        reader = list(reader)
        N = np.array([int(item) for item in reader[0][1:]])
        rel_errs = dict()
        for i, method in enumerate(methods):
            rel_errs[method] = list()
            for item in reader[i+1][1:]:
                if item != 'None':
                    rel_errs[method].append(float(item))
            rel_errs[method] = np.abs(rel_errs[method])
            plt.loglog(N[:len(rel_errs[method])], rel_errs[method])
        plt.xlabel('Sampling Size')
        plt.ylabel('Relative Error')
        plt.legend(rel_errs)
        plt.savefig('result/wsl/process/fig/219_gauss_sample-num_sample-size_m{}.pdf'.format(m))
        plt.show()