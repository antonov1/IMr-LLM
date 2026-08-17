from pathlib import Path
import signal
import time

import pandas as pd
import pm4py

from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.log import obj as log_instance

from local_pm4py import discovery
from local_pm4py.functions import parse_rules
import json

SUPPORT_VALUES = [0.25, 0.5, 0.75, 1.0]
TIMEOUT_SECONDS = 60 * 60

BASE_DIR = Path(__file__).resolve().parent

ARTIFACTS_DIR = BASE_DIR / "artifacts"
EXPERIMENTS_DIR = BASE_DIR / "experiments"
MODELS_DIR = EXPERIMENTS_DIR / "models"

IDS_FILE = BASE_DIR / "ids.json"
RESULTS_FILE = EXPERIMENTS_DIR / "runtimes.csv"

MODELS_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_TEMPLATES = {
    "existence",
    "init",
    "end",
    "responded_existence",
    "response",
    "precedence",
    "coexistence",
    "noncoexistence",
    "nonsuccession",
    "atmost1",
}


class CaseTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise CaseTimeout()


signal.signal(signal.SIGALRM, timeout_handler)


def run_case(eval_id, support):
    log_path = ARTIFACTS_DIR / f"log_{eval_id}.xes"
    rules_path = ARTIFACTS_DIR / f"rules_sampled_{eval_id}.txt"

    support_label = str(support).replace(".", "_")
    model_path = MODELS_DIR / f"{eval_id}_imr_sup_{support_label}.ptml"

    print(f"\nRunning id={eval_id}, support={support}...")

    try:
        # --------------------------------------------------
        # Check inputs
        # --------------------------------------------------

        if not log_path.exists():
            raise FileNotFoundError(f"Missing log: {log_path}")

        if not rules_path.exists():
            raise FileNotFoundError(f"Missing rules: {rules_path}")

        # --------------------------------------------------
        # Load log
        # --------------------------------------------------

        logP = xes_importer.apply(str(log_path))

        logM = log_instance.EventLog()
        logM.append(log_instance.Trace())

        # --------------------------------------------------
        # Parse rules
        # --------------------------------------------------

        rules = parse_rules.parse_constraints(str(rules_path))

        for template in ALLOWED_TEMPLATES:
            rules.setdefault(template, [])

        # --------------------------------------------------
        # Discovery with timeout
        # --------------------------------------------------

        signal.alarm(TIMEOUT_SECONDS)

        start = time.perf_counter()

        ptree = discovery.apply_bi(
            logP,
            logM,
            sup=support,
            ratio=0,
            size_par=len(logP) / max(1, len(logM)),
            rules=rules,
        )

        runtime = time.perf_counter() - start

        signal.alarm(0)

        # --------------------------------------------------
        # Export process tree
        # --------------------------------------------------

        pm4py.write_ptml(
            ptree,
            str(model_path),
        )

        print(
            f"id={eval_id}, support={support}: "
            f"success ({runtime:.2f}s)"
        )

        return {
            "id": eval_id,
            "support": support,
            "runtime_seconds": runtime,
            "status": "success",
        }

    except ValueError as e:
        signal.alarm(0)

        print(
            f"id={eval_id}, support={support}: "
            f"invalid rules: {e}"
        )

        return {
            "id": eval_id,
            "support": support,
            "runtime_seconds": None,
            "status": "invalid_rules",
        }

    except CaseTimeout:
        signal.alarm(0)

        print(
            f"id={eval_id}, support={support}: "
            f"timeout after 60 minutes"
        )

        return {
            "id": eval_id,
            "support": support,
            "runtime_seconds": TIMEOUT_SECONDS,
            "status": "timeout",
        }

    except Exception as e:
        signal.alarm(0)

        print(
            f"id={eval_id}, support={support}: "
            f"error: {e}"
        )

        return {
            "id": eval_id,
            "support": support,
            "runtime_seconds": None,
            "status": f"error: {e}",
        }


def main(ids):
    results = []

    for eval_id in ids:
        for support in SUPPORT_VALUES:
            result = run_case(eval_id, support)
            results.append(result)

            # Checkpoint after every run
            pd.DataFrame(results).to_csv(
                RESULTS_FILE,
                index=False,
            )

    df = pd.DataFrame(results)

    print("\nResults:")
    print(df)

    return df


if __name__ == "__main__":
    with open(IDS_FILE, "r") as f:
        ids = json.load(f)

    ids = [str(eval_id) for eval_id in ids]

    print(f"Loaded {len(ids)} IDs from {IDS_FILE}")

    results = main(ids)