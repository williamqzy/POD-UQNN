import os
import sys
import json
import numpy as np
import tensorflow as tf

eqnPath = "1d-burgers2"
sys.path.append(eqnPath)
from dataprep import prep_data
from regression import create_model_and_train
from predictions import predict_and_assess
from plots import plot_results

sys.path.append(os.path.join(eqnPath, "utils"))
from podnn import PodnnModel
from metrics import error_podnn
from mesh import create_linear_mesh


# HYPER PARAMETERS
if len(sys.argv) > 1:
    with open(sys.argv[1]) as hpFile:
        hp = json.load(hpFile)
else:
    from hyperparams import hp


class Burgers2PodnnModel(PodnnModel):
    def u_0(self, X, mu):
        x = X[0]
        return x / (1 + np.exp(1/(4*mu)*(x**2 - 1/4)))

    def u(self, X, t, mu):
        x = X[0]
        t0 = np.exp(1 / (8*mu))
        return (x/t) / (1 + np.sqrt(t/t0)*np.exp(x**2/(4*mu*t)))


x_mesh = create_linear_mesh(hp["x_min"], hp["x_max"], hp["n_x"])
model = Burgers2PodnnModel(hp["n_v"], x_mesh, hp["n_t"], eqnPath)

X_v_train, v_train, \
    X_v_val, v_val, \
    U_val = model.generate_dataset(hp["t_min"], hp["t_max"],
                                   hp["mu_min"], hp["mu_max"],
                                   hp["n_s"],
                                   hp["train_val_ratio"],
                                   hp["eps"])

def error_val():
    U_pred = model.predict(X_v_val)
    return error_podnn(U_val, U_pred)
model.train(X_v_train, v_train, error_val, hp["h_layers"],
            hp["epochs"], hp["lr"], hp["lambda"]) 

U_pred = model.predict(X_v_val)

U_pred_struct = model.restruct(U_pred)
U_val_struct = model.restruct(U_val)
 
# PLOTTING AND SAVING RESULTS
plot_results(U_val_struct, U_pred_struct, hp, eqnPath)
plot_results(U_val_struct, U_pred_struct, hp)
