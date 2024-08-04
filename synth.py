from tree.formula import Always, Formula
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from matplotlib import pyplot as plt
import json
with open("config.json") as config_file:
    config = json.load(config_file)

def plot(arr, boundary: float = None, title=""):
    plt.figure(figsize=(10, 6))
    plt.plot(arr)
    plt.xlabel("Trace")
    plt.ylabel("Robustness")
    if boundary:
        plt.axhline(boundary, color="red", label=f"Mean prediction error <= {boundary}")
    plt.title(title)
    plt.legend()
    plt.show()


def classify_traces(traces, phi, plot_rob=False):
    split_traces = traces.reshape((traces.shape[0], phi.end, -1))
    rob = (
        np.max(split_traces, axis=1)
        if isinstance(phi, Always)
        else np.min(split_traces, axis=1)
    )
    mean_rob = rob.mean(axis=1)
    if plot_rob:
        plot(mean_rob, boundary=phi.boundary)
    classifications = np.where(mean_rob <= phi.boundary, True, False)
    return classifications


def weighted_closeness(arr: np.ndarray, interval: int, operator=None, trace_length=-1) -> float:
    contraction_fn = lambda r, size: r * (1 + config["GAMMA"] * np.exp(0.5 - size))
    expansion_fn = lambda r, size: r  * (1 + config["GAMMA"] * np.exp(size - 0.5))
    score = -arr.ptp() # Aim to maximise score
    proportion = np.log(interval) / np.log(trace_length)
    result = contraction_fn(score, proportion) if operator=="F" else expansion_fn(score, proportion)
    return result
    
def positive_synth(traces, interval=1, best_value=-np.inf, best_op="", best_threshold=-1, operators="FG_", invariance=False, use_mean=True):
    trace_length = traces.size // traces.shape[0]
    if invariance:
        max_threshold = traces.mean(axis=1).max() if use_mean else traces.max()
        boundary = 1 if use_mean else config["BATCH_SIZE"]
        return Formula.build_formula(max_threshold, "G", boundary)
    if "F" in operators:
        ev_rob = np.min(traces, axis=2)  # Pick the best value
        ev_mean_rob = ev_rob.mean(axis=1)
        ev_value = weighted_closeness(ev_mean_rob, traces.shape[2], operator="F", trace_length=trace_length)
    else:
        ev_mean_rob, ev_value = np.inf, np.inf
    if "G" in operators:
        alw_rob = np.max(traces, axis=2)  # Pick the worst value
        alw_mean_rob = alw_rob.mean(axis=1)
        alw_value = weighted_closeness(alw_mean_rob, traces.shape[2], operator="G", trace_length=trace_length)
    else:
        alw_mean_rob, alw_value = np.inf, np.inf
    if ev_value > alw_value:
        value, op, threshold = ev_value, "F", ev_mean_rob.max()
    else:
        value, op, threshold = alw_value, "G", alw_mean_rob.max()
    if value > best_value:
        best_value = value
        interval = traces.shape[2]
        best_op = op
        best_threshold = threshold
    if traces.shape[1] % 2 != 0:
        return Formula.build_formula(best_threshold, best_op, interval)
    new_shape = (-1, traces.shape[1] // 2, traces.shape[2] * 2)
    return positive_synth(traces.reshape(new_shape), interval, best_value, best_op, best_threshold, operators=operators, invariance=invariance)


def main():
    # predict(anomaly_size=0.0003)
    predictions_file = "csv/predictions.csv"
    traces = np.genfromtxt(predictions_file, delimiter=",", dtype=float)
    testing = False
    filetype = "test" if testing else "val"
    neg_infile = f"csv/negative_{filetype}.csv"
    pos_infile = f"csv/positive_{filetype}.csv"
    negatives = np.genfromtxt(neg_infile, delimiter=",", dtype=float)  # no anomalies
    positives = np.genfromtxt(pos_infile, delimiter=",", dtype=float)  # has anomalies
    num_sensors = 27
    neg_classifications = []
    pos_classifications = []
    traces = traces.reshape(num_sensors, traces.shape[1], -1)
    negatives = negatives.reshape(num_sensors, negatives.shape[1], -1)
    positives = positives.reshape(num_sensors, positives.shape[1], -1)
    for sensor_index in range(num_sensors):
        if sensor_index != 0:
            continue
        sensor_traces = traces[sensor_index]
        formula = positive_synth(sensor_traces[:, :, np.newaxis], best=default_best())
        print(f"Sensor {sensor_index+1} formula: {formula}")
        neg_classifications += classify_traces(negatives[sensor_index], formula).tolist()
        pos_classifications += classify_traces(positives[sensor_index], formula).tolist()
    ground_truth_neg = np.full_like(neg_classifications, False)
    ground_truth_pos = np.full_like(pos_classifications, True)
    ground_truth = np.concatenate([ground_truth_neg, ground_truth_pos])
    predictions = ~np.concatenate([neg_classifications, pos_classifications])
    print(f"Accuracy: {accuracy_score(ground_truth, predictions)}")
    print(f"Precision: {precision_score(ground_truth, predictions, zero_division=0)}")
    print(f"Recall: {recall_score(ground_truth, predictions, zero_division=0)}")
    print(f"F1: {f1_score(ground_truth, predictions, zero_division=0)}")
    # print("=" * 50)
    # print("Non-anomalous predictions:", ~np.array(neg_classifications))
    # print("=" * 50)
    # print("Anomalous predictions:", ~np.array(pos_classifications))
    # print("=" * 50)
    # print("Ground truth:", ground_truth)


if __name__ == "__main__":
    traces = np.array([
        [2,2,2,0.98,2,2,2,1],
        [3,3,3,1,3,3,3,0.97]
    ])
    print(positive_synth(traces[:, :, np.newaxis], invariance=False))
    #main()
