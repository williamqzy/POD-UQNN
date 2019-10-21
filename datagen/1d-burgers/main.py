import sys
import os
import numpy as np
from tqdm import tqdm
from pyDOE import lhs

eqnPath = "1d-burgers"
sys.path.append(eqnPath)
sys.path.append("utils")
sys.path.append(os.path.join(eqnPath, "burgersutils"))
from burgersutils import plot_results
from burgers import burgers_viscous_time_exact1 as burgers_u

from names import X_FILE, T_FILE, U_MEAN_FILE, U_STD_FILE

# Hyperparameters
n_x = 300
n_t = 100
n_s = int(1e5)
x_min = -1.
x_max = 1.
t_min = 0.
t_max = 1.
mu_mean = 0.01/np.pi

# Static data
x = np.linspace(x_min, x_max, n_x)
t = np.linspace(x_min, t_max, n_t)
X, T = np.meshgrid(x, t)
n_h = n_x
n_d = 1 + 1
lb = mu_mean * (1 - np.sqrt(3)/10)
ub = mu_mean * (1 + np.sqrt(3)/10)

# The sum and sum of squares recipient vectors
# TODO, stopped here
# U_tot = np.zeros((n_x))
# U_tot_sq = np.zeros((n_x*n_y, 1))

# # Going through the snapshots one by one without saving them
# for i in tqdm(range(n_s)):
#     # Computing one snapshot
#     X_mu = lhs(1, mu.shape[0]).T
#     mu_lhs = lb + (ub - lb)*X_mu
#     U = np.reshape(u_h(X, Y, mu_lhs[0, :]), (n_x * n_y, 1))

#     # Building the sum and the sum of squaes
#     U_tot += U
#     U_tot_sq += U**2

# # Recreating the mean and the std
# U_mean = U_tot / n_s
# U_std = np.sqrt((n_s*U_tot_sq - U_tot**2) / (n_s*(n_s - 1)))

# # Reshaping into a 2D-valued solution
# U_test_mean = np.reshape(U_mean, (n_x, n_y))
# U_test_std = np.reshape(U_std, (n_x, n_y))

dirname = os.path.join(eqnPath, "data")
print(f"Saving data to {dirname}")
np.save(os.path.join(dirname, X_FILE), X)
np.save(os.path.join(dirname, T_FILE), T)
np.save(os.path.join(dirname, U_MEAN_FILE), 0)
np.save(os.path.join(dirname, U_STD_FILE), 0)
# np.save(os.path.join(dirname, U_STD_FILE), U_test_std)
# np.save(os.path.join(dirname, U_MEAN_FILE), U_test_mean)