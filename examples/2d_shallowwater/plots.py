"""Handles the plots for 2D inviscid Shallow Water Equations."""

import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from pyevtk.hl import pointsToVTK

from podnn.metrics import error_podnn
from podnn.plotting import figsize, saveresultdir


def plot_plot(fig, pos, x, y, z, z_min, z_max, title):
    """Does a colorplot from unstructured, 1d (x, y, z) data."""
    ax = fig.add_subplot(pos)
    h = plt.tripcolor(x, y ,z)
    h.set_clim(z_min, z_max)
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(h, cax=cax)
    ax.set_title(title)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")


def plot_spec_time(fig, pos, x, t_i, U_pred, U_val, U_test,
                   title, show_legend=False):
    ax = fig.add_subplot(pos)
    ax.plot(x, U_pred[:, t_i], "b-", label="$\hat{u_V}$")
    ax.plot(x, U_val[:, t_i], "r--", label="$u_V$")
    ax.plot(x, U_test[:, t_i], "k,", label="$u_T$")
    ax.set_title(title)
    ax.set_xlabel("$x$")
    ax.set_title(title)
    if show_legend:
        ax.legend()


def get_min_max(z1, z2):
    """Returns the min and max across the two np array."""

    z_min = min([np.min(z1), np.min(z2)])
    z_max = max([np.max(z1), np.max(z2)])
    return z_min, z_max


def plot_results(x_mesh, U_val, U_pred,
                 HP=None, export_vtk=False, export_txt=False):
    """Handles the plots of 3d_shallowwater."""

    # Keeping only the first nodes
    # lim = 10000
    lim = None
    x = x_mesh[:lim, 1]
    y = x_mesh[:lim, 2]

    # Computing means
    U_val_mean = np.mean(U_val[:, :lim, :], axis=-1)
    U_pred_mean = np.mean(U_pred[:, :lim, :], axis=-1)

    if export_txt:
        print(U_val_mean.T.shape)
        print(x_mesh.shape)
        x_u_mean = np.concatenate((x_mesh, U_val_mean.T), axis=1)
        non_idx_len = x_u_mean.shape[1] - 1
        np.savetxt(os.path.join("cache", "x_u_mean.txt"), x_u_mean,
                   fmt=' '.join(["%i"] + ["%1.6f"]*non_idx_len),
                   delimiter="\t")
        return

    if export_vtk:
        z = np.zeros_like(x)
        pointsToVTK(os.path.join("cache", "rnd_points"), np.ascontiguousarray(x),
                    np.ascontiguousarray(y), np.ascontiguousarray(z),
                    data={
                        "h" : U_val_mean[0],
                        "hu" : U_val_mean[1],
                        "hv" : U_val_mean[2],
                        })
        return

    print("Plotting")
    n_plot_x = 2
    n_plot_y = 4
    fig = plt.figure(figsize=figsize(n_plot_x, n_plot_y, scale=2.5))
    gs = fig.add_gridspec(n_plot_x, n_plot_y)

    quantities = ["h", "(hu)", "(hv)"]
    for i, qty in enumerate(quantities):
        z_min, z_max = get_min_max(U_pred_mean[i], U_val_mean[i])
        plot_plot(fig, gs[0, i], x, y, U_pred_mean[i],
                  z_min, z_max, f"Mean ${qty}(x,y)$ [pred]")
        plot_plot(fig, gs[1, i], x, y, U_val_mean[i],
                  z_min, z_max, f"Mean ${qty}(x,y)$ [val]")

    plt.tight_layout()
    saveresultdir(HP)