"""
Not used in production, for testing only
Used in "experiments.py"
"""

import matplotlib.pyplot as plt
import numpy as np

from ml.core import TOURNESOL_DEV

if not TOURNESOL_DEV:
    raise Exception('Dev module called whereas TOURNESOL_DEV=0')


INTENS = 0.4  # intensity of coloration

PLOTS = {
    'loss': ['loss_fit', 'loss_s', 'loss_gen', 'loss_reg'],
    'grad': ['grad_sp', 'grad_norm'],
    'norm_glob': ['norm_glob'],
    'norm_loc': ['norm_loc'],
    'diff_glob': ['diff_glob'],
    'diff_loc': ['diff_loc'],
    'diff_s': ['diff_s'],

    # in test mode only (generated data)
    'error_glob': ['error_glob'],
    'error_loc': ['error_loc'],
}


def get_style():
    """gives different line styles for plots"""
    styles = ["-", "-.", ":", "--"]
    for i in range(10000):
        yield styles[i % 4]


def get_color():
    """gives different line colors for plots"""
    colors = ["red", "green", "blue", "grey"]
    for i in range(10000):
        yield colors[i % 4]


STYLES = get_style()  # generator for looping styles
COLORS = get_color()


def _title_save(title=None, path=None, suff=".png"):
    """ Adds title and saves plot """
    if title is not None:
        plt.title(title)
    if path is not None:
        plt.savefig(path + suff)
    plt.clf()


def _legendize(y, x="Epochs"):
    """ Labels axis of plt plot """
    plt.xlabel(x)
    plt.ylabel(y)
    plt.legend()


def _means_bounds(arr):
    """
    arr: 2D array of values (one line is one run)

    Returns:
    - array of means
    - array of (mean - var)
    - array of (mean + var)
    """
    means = np.mean(arr, axis=0)
    var = np.var(arr, axis=0)
    return means, means - var, means + var


# ------------- utility for what follows -------------------------
def _plot_var(l_hist, plot_name, focus=False):
    """ add curve of asked indexes of history to the plot """
    l_metrics = PLOTS[plot_name]
    epochs = range(1, len(l_hist[0][l_metrics[0]]) + 1)
    for metric in l_metrics:
        vals = np.asarray(
            [hist[metric] for hist in l_hist]
        )
        vals_m, vals_l, vals_u = _means_bounds(vals)
        style, color = next(STYLES), next(COLORS)
        plt.plot(epochs, vals_m, label=metric,
                 linestyle=style, color=color)
        if focus:
            plt.ylim([0, np.mean(vals_m)])
        plt.fill_between(epochs, vals_u, vals_l, alpha=INTENS, color=color)


def _plotfull_var(l_hist, plot_name, path=None):
    """ plot metrics asked in -l_metrics and save if -path provided """
    l_metrics = PLOTS[plot_name]
    if all(metric in l_hist[0] for metric in l_metrics):
        _plot_var(l_hist, plot_name)
        _legendize(plot_name)
        _title_save(plot_name, path, plot_name + '.png')


# plotting all the metrics we have
def plot_metrics(l_hist, path=None):
    """ Plots and saves the different metrics from list of historys """
    for plot_name in PLOTS:
        _plotfull_var(l_hist, plot_name, path)


# histogram
def plot_density(tens, title=None, path=None, name="hist.png"):
    """ Saves histogram of repartition

    tens (tensor): data of which we want repartition
    """
    arr = np.array(tens)
    _ = plt.hist(arr, density=False, label=title, bins=40)
    _legendize("Number", "Value")
    _title_save(title, path, name)


# -------- clouds of points ----------
def plot_s_predict_gt(s_predict, s_gt, path, name='s_correlation.png'):
    """ Saves cloud of point of s parameters (test mode only)

    s_predict (float list): predicted s parameters
    s_gt (float list): ground truth s parameters
    """
    plt.plot(s_predict, s_gt, 'ro', label='loss_s')
    _legendize('ground truths', 'predicted')
    _title_save('s parameters', path, name)


def plot_loc_uncerts(l_nb_comps, l_uncerts, path, name='uncertainties.png'):
    """ Saves local uncertainties in function of number of ratings

    l_nb_vids (int list): number of comparisons for each video by each user
    l_uncert (float list): uncertainty for each video of each user
    """
    plt.plot(l_nb_comps, l_uncerts, 'ro', label='uncertainty', ms=0.5)
    _legendize('uncertainty', 'number of comparisons')
    _title_save('Local uncertainties', path, name)
