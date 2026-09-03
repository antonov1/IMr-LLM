from pathlib import Path
import json
import re
import signal
import time

import pandas as pd
import pm4py

from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.log import obj as log_instance

from local_pm4py import discovery
from local_pm4py.functions import parse_rules


TIMEOUT_SECONDS = 10 * 60  # 10 mins

BASE_DIR = Path(__file__).resolve().parent

ARTIFACTS_DIR = BASE_DIR / "artifacts-artificial"
LOGS_DIR = ARTIFACTS_DIR / "logs"
IDS_FILE = ARTIFACTS_DIR / "ids.json"

EXPERIMENTS_DIR = BASE_DIR / "experiments-artificial"
MODELS_DIR = EXPERIMENTS_DIR / "models"

RESULTS_FILE = EXPERIMENTS_DIR / "runtimes.csv"

EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
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


def parse_trial_id(rules_path: Path):
    pattern = re.compile(
        r"^rules_sampled_(?P<trial>\d+)\.txt$"
    )

    match = pattern.match(rules_path.name)

    if match is None:
        raise ValueError(
            f"Unexpected rule filename format: {rules_path.name}"
        )

    return int(match.group("trial"))


def run_case(rules_path, sup):
    trial = parse_trial_id(rules_path)

    log_path = LOGS_DIR / f"log_{trial}.xes"
    model_path = MODELS_DIR / f"imr_{trial}_sup_{sup:.2f}.ptml"

    print(
        f"\nRunning "
        f"trial={trial}, "
        f"sup={sup:.2f}..."
    )

    try:
        # --------------------------------------------------
        # Check inputs
        # --------------------------------------------------

        if not log_path.exists():
            raise FileNotFoundError(
                f"Missing log: {log_path}"
            )

        if not rules_path.exists():
            raise FileNotFoundError(
                f"Missing rules: {rules_path}"
            )

        # --------------------------------------------------
        # Load log
        # --------------------------------------------------

        logP = xes_importer.apply(
            str(log_path)
        )

        logM = log_instance.EventLog()
        logM.append(
            log_instance.Trace()
        )

        # --------------------------------------------------
        # Parse rules
        # --------------------------------------------------

        rules = parse_rules.parse_constraints(
            str(rules_path)
        )

        for template in ALLOWED_TEMPLATES:
            rules.setdefault(
                template,
                [],
            )

        # --------------------------------------------------
        # Discovery
        # --------------------------------------------------

        signal.alarm(TIMEOUT_SECONDS)

        start = time.perf_counter()

        ptree = discovery.apply_bi(
            logP,
            logM,
            sup=sup,
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
            f"trial={trial}, "
            f"sup={sup:.2f}: "
            f"success ({runtime:.2f}s)"
        )

        return {
            "trial": trial,
            "support": sup,
            "rules_file": rules_path.name,
            "log_file": log_path.name,
            "model_file": model_path.name,
            "runtime_seconds": runtime,
            "status": "success",
        }

    except ValueError as e:
        signal.alarm(0)

        print(
            f"trial={trial}, "
            f"sup={sup:.2f}: "
            f"invalid rules: {e}"
        )

        return {
            "trial": trial,
            "support": sup,
            "rules_file": rules_path.name,
            "log_file": log_path.name,
            "model_file": model_path.name,
            "runtime_seconds": None,
            "status": "invalid_rules",
        }

    except CaseTimeout:
        signal.alarm(0)

        print(
            f"trial={trial}, "
            f"sup={sup:.2f}: "
            f"timeout after {TIMEOUT_SECONDS / 60:.0f} minutes"
        )

        return {
            "trial": trial,
            "support": sup,
            "rules_file": rules_path.name,
            "log_file": log_path.name,
            "model_file": model_path.name,
            "runtime_seconds": TIMEOUT_SECONDS,
            "status": "timeout",
        }

    except Exception as e:
        signal.alarm(0)

        print(
            f"trial={trial}, "
            f"sup={sup:.2f}: "
            f"error: {e}"
        )

        return {
            "trial": trial,
            "support": sup,
            "rules_file": rules_path.name,
            "log_file": log_path.name,
            "model_file": model_path.name,
            "runtime_seconds": None,
            "status": f"error: {e}",
        }


def main():
    results = []

    # --------------------------------------------------
    # Find rule files directly from their names
    # --------------------------------------------------

    rules_files = sorted(
        ARTIFACTS_DIR.glob("rules_sampled_*.txt"),
        key=parse_trial_id,
    )

    if len(rules_files) != 100:
        raise RuntimeError(
            f"Expected exactly 100 rule files, "
            f"but found {len(rules_files)} in {ARTIFACTS_DIR}"
        )

    print("Found exactly 100 rule files.")

    # --------------------------------------------------
    # Check corresponding logs
    # --------------------------------------------------

    missing_logs = []

    for rules_path in rules_files:
        trial = parse_trial_id(rules_path)
        log_path = LOGS_DIR / f"log_{trial}.xes"

        if not log_path.exists():
            missing_logs.append(log_path)

    if missing_logs:
        missing_names = "\n".join(
            str(path)
            for path in missing_logs
        )

        raise FileNotFoundError(
            f"Missing {len(missing_logs)} corresponding log files:\n"
            f"{missing_names}"
        )

    print("All 100 corresponding log files exist.")

    # --------------------------------------------------
    # Run both support settings
    # --------------------------------------------------

    supports = [
        1.00,
        0.80,
    ]

    for sup in supports:
        print(
            f"\n{'=' * 60}\n"
            f"Running support={sup:.2f}\n"
            f"{'=' * 60}"
        )

        for rules_path in rules_files:
            result = run_case(
                rules_path,
                sup,
            )

            results.append(
                result
            )

            pd.DataFrame(
                results
            ).to_csv(
                RESULTS_FILE,
                index=False,
            )

    # --------------------------------------------------
    # Final results
    # --------------------------------------------------

    df = pd.DataFrame(
        results
    )

    if not df.empty:
        df = (
            df
            .sort_values(
                [
                    "support",
                    "trial",
                ],
                ascending=[
                    False,
                    True,
                ],
            )
            .reset_index(drop=True)
        )

    df.to_csv(
        RESULTS_FILE,
        index=False,
    )

    print("\nResults:")
    print(df)

    return df

def main():
    results = []

    rules_files = sorted(
        ARTIFACTS_DIR.glob("rules_sampled_*.txt"),
        key=parse_trial_id,
    )

    if len(rules_files) != 100:
        raise RuntimeError(
            f"Expected exactly 100 rule files, "
            f"but found {len(rules_files)}."
        )

    print(f"Found exactly {len(rules_files)} rule files.")

    supports = [1.00, 0.80]

    for sup in supports:
        print(f"\nRunning experiments with support={sup:.2f}")

        for rules_path in rules_files:
            result = run_case(
                rules_path,
                sup,
            )

            results.append(
                result
            )

            pd.DataFrame(
                results
            ).to_csv(
                RESULTS_FILE,
                index=False,
            )

    df = pd.DataFrame(
        results
    )

    if not df.empty:
        df = (
            df
            .sort_values(
                ["support", "trial"],
                ascending=[False, True],
            )
            .reset_index(drop=True)
        )

    df.to_csv(
        RESULTS_FILE,
        index=False,
    )

    print("\nResults:")
    print(df)

    return df


if __name__ == "__main__":
    results = main()