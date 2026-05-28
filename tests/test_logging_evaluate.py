import json
import tempfile
import unittest
from pathlib import Path

from evaluate import evaluate
from pulse50.logging import append_predictions


class LoggingEvaluateTests(unittest.TestCase):
    def test_prediction_logger_and_evaluator(self):
        with tempfile.TemporaryDirectory() as tmp:
            prediction_path = Path(tmp) / "predictions.jsonl"
            outcome_path = Path(tmp) / "outcomes.jsonl"
            response = {
                "as_of": "2026-05-27T10:00:00+00:00",
                "model_version": "v1.0-rules",
                "debug_features": {"BTC": {"current_price": 100.0}},
                "signals": [
                    {"symbol": "BTC", "direction": "UP", "probability_up": 0.6, "confidence": "Medium"}
                ],
            }

            rows = append_predictions(response, prediction_path)
            outcome_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-05-27T10:00:00+00:00",
                        "symbol": "BTC",
                        "price_after_15m": 101.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            metrics = evaluate(prediction_path, outcome_path)

            self.assertEqual(rows, 1)
            self.assertEqual(metrics["count"], 1)
            self.assertEqual(metrics["hit_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
