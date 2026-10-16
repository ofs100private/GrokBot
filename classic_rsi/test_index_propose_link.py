import json, tempfile, unittest
from pathlib import Path
from classic_rsi.audit import append_audit

class IndexProposeLink(unittest.TestCase):
    def test_auto_row_has_propose_run_id(self):
        with tempfile.TemporaryDirectory() as d:
            append_audit("propose", {"symbols": ["X"]}, audit_dir=Path(d), run_id="classic-rsi-propose-t")
            append_audit("auto", {"symbols": ["X"], "propose_run_id": "classic-rsi-propose-t"},
                         audit_dir=Path(d), run_id="classic-rsi-auto-t", params={"a": 1})
            rows = [json.loads(l) for l in (Path(d) / "index.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["kind"], "auto")
            self.assertEqual(rows[1]["propose_run_id"], "classic-rsi-propose-t")
            self.assertNotIn("propose_run_id", rows[0])

if __name__ == "__main__":
    unittest.main()
