import json
import subprocess
import unittest
from pathlib import Path

from usage_widget.display import countdown, label, percent_text

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "tests" / "vectors.json").read_text(encoding="utf-8"))


class DisplayTests(unittest.TestCase):
    def test_countdown_vectors(self) -> None:
        for row in VECTORS["countdown"]:
            with self.subTest(remaining=row["remaining"]):
                self.assertEqual(countdown(row["remaining"]), row["expected"])

    def test_percent_vectors(self) -> None:
        for row in VECTORS["percent"]:
            with self.subTest(value=row["value"]):
                self.assertEqual(percent_text(row["value"]), row["expected"])

    def test_label_vectors(self) -> None:
        for row in VECTORS["label"]:
            with self.subTest(row=row):
                self.assertEqual(label(row["percent"], row["remaining"]), row["expected"])

    def test_javascript_matches_vectors(self) -> None:
        node = subprocess.run(["node", "--version"], check=False, capture_output=True)
        if node.returncode != 0:
            self.skipTest("node is not installed")
        script = r"""
const fs = require("fs");
const root = process.argv[1];
const vectors = JSON.parse(fs.readFileSync(root + "/tests/vectors.json", "utf8"));
const source = fs.readFileSync(root + "/Format.js", "utf8").replace(/^\.pragma library\s*/, "");
const fn = new Function(source + "\nreturn { countdown, percentText, label };");
const format = fn();
const failures = [];
for (const row of vectors.countdown) {
  const got = format.countdown(row.remaining);
  if (got !== row.expected) failures.push(`countdown ${row.remaining}: ${got} != ${row.expected}`);
}
for (const row of vectors.percent) {
  const got = format.percentText(row.value);
  if (got !== row.expected) failures.push(`percent ${row.value}: ${got} != ${row.expected}`);
}
for (const row of vectors.label) {
  const got = format.label(row.percent, row.remaining);
  if (got !== row.expected) failures.push(`label: ${got} != ${row.expected}`);
}
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
"""
        result = subprocess.run(["node", "-e", script, str(ROOT)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
