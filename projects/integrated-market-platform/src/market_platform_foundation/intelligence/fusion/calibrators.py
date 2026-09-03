"""Deterministic calibration model fitting for BUILD 14."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from .calibration_data import (
    MINIMUM_CALIBRATION_SAMPLES,
    MINIMUM_CLASS_COUNT,
    dataset_support_summary,
)
from .errors import CalibrationTrainingError
from .identity import derive_calibration_model_id, parameter_fingerprint
from .types import CalibrationDataset, CalibrationMethod, CalibrationModelArtifact

LOGISTIC_METHOD_VERSION = "1"
ISOTONIC_METHOD_VERSION = "1"
IDENTITY_METHOD_VERSION = "1"


@dataclass(frozen=True, slots=True)
class CalibrationTrainer:
  minimum_samples: int = MINIMUM_CALIBRATION_SAMPLES
  minimum_per_class: int = MINIMUM_CLASS_COUNT
  random_state: int = 0

  def fit(
      self,
      dataset: CalibrationDataset,
      *,
      method: CalibrationMethod,
      available_time_ns: int,
  ) -> CalibrationModelArtifact | None:
      support = dataset_support_summary(dataset)
      if support["sample_count"] < self.minimum_samples:
          return None
      if support["class_0"] < self.minimum_per_class or support["class_1"] < self.minimum_per_class:
          return None

      probabilities = np.array([example.raw_probability for example in dataset.examples], dtype=float)
      labels = np.array([example.label for example in dataset.examples], dtype=int)
      if not np.all(np.isfinite(probabilities)):
          raise CalibrationTrainingError("NON_FINITE_TRAINING_PROBABILITY")

      if method == CalibrationMethod.IDENTITY_CONTROL:
          parameters = {"kind": "identity"}
          method_version = IDENTITY_METHOD_VERSION
      elif method == CalibrationMethod.LOGISTIC_PROBABILITY:
          model = LogisticRegression(random_state=self.random_state, max_iter=1000)
          model.fit(probabilities.reshape(-1, 1), labels)
          parameters = {
              "coef": [float(value) for value in model.coef_.reshape(-1)],
              "intercept": float(model.intercept_[0]),
          }
          method_version = LOGISTIC_METHOD_VERSION
      elif method == CalibrationMethod.ISOTONIC:
          model = IsotonicRegression(out_of_bounds="raise")
          model.fit(probabilities, labels)
          parameters = {
              "x_thresholds": [float(value) for value in model.X_thresholds_],
              "y_thresholds": [float(value) for value in model.y_thresholds_],
          }
          method_version = ISOTONIC_METHOD_VERSION
      else:
          raise CalibrationTrainingError(f"UNSUPPORTED_METHOD:{method.value}")

      param_fp = parameter_fingerprint(parameters)
      dataset_fp = dataset.dataset_id
      hyperparameters = {"random_state": self.random_state}
      model_id = derive_calibration_model_id(
          method=method.value,
          method_version=method_version,
          dataset_fingerprint=dataset_fp,
          target=dataset.target,
          horizon=dataset.horizon,
          fusion_policy_identity=dataset.fusion_policy_identity,
          training_cutoff_ns=dataset.calibration_cutoff_ns,
          available_time_ns=available_time_ns,
          hyperparameters=hyperparameters,
          regime_key=dataset.regime_key,
      )
      return CalibrationModelArtifact(
          calibration_model_id=model_id,
          method=method,
          method_version=method_version,
          target=dataset.target,
          horizon=dataset.horizon,
          fusion_policy_identity=dataset.fusion_policy_identity,
          dataset_fingerprint=dataset_fp,
          training_cutoff_ns=dataset.calibration_cutoff_ns,
          available_time_ns=available_time_ns,
          parameters=parameters,
          parameter_fingerprint=param_fp,
          min_training_raw_probability=float(np.min(probabilities)),
          max_training_raw_probability=float(np.max(probabilities)),
          sample_count=support["sample_count"],
          class_counts={"0": support["class_0"], "1": support["class_1"]},
          regime_key=dataset.regime_key,
      )


def apply_calibration(artifact: CalibrationModelArtifact, raw_probability: float) -> float:
  if not math.isfinite(raw_probability):
      raise CalibrationTrainingError("RAW_PROBABILITY_NOT_FINITE")
  if artifact.method == CalibrationMethod.IDENTITY_CONTROL:
      return raw_probability
  if artifact.method == CalibrationMethod.LOGISTIC_PROBABILITY:
      coef = artifact.parameters["coef"][0]
      intercept = artifact.parameters["intercept"]
      logit = coef * raw_probability + intercept
      return 1.0 / (1.0 + math.exp(-logit))
  if artifact.method == CalibrationMethod.ISOTONIC:
      x_thresholds = artifact.parameters["x_thresholds"]
      y_thresholds = artifact.parameters["y_thresholds"]
      if raw_probability < x_thresholds[0] or raw_probability > x_thresholds[-1]:
          raise CalibrationTrainingError("ISOTONIC_OUT_OF_BOUNDS")
      for index in range(len(x_thresholds) - 1):
          left_x = x_thresholds[index]
          right_x = x_thresholds[index + 1]
          if left_x <= raw_probability <= right_x:
              if right_x == left_x:
                  return y_thresholds[index]
              fraction = (raw_probability - left_x) / (right_x - left_x)
              left_y = y_thresholds[index]
              right_y = y_thresholds[index + 1]
              return left_y + fraction * (right_y - left_y)
      raise CalibrationTrainingError("ISOTONIC_OUT_OF_BOUNDS")
  raise CalibrationTrainingError(f"UNSUPPORTED_METHOD:{artifact.method.value}")


__all__ = [
    "CalibrationTrainer",
    "IDENTITY_METHOD_VERSION",
    "ISOTONIC_METHOD_VERSION",
    "LOGISTIC_METHOD_VERSION",
    "apply_calibration",
]
