import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from robonuggets_ops.dnc_guard import evaluate_outreach_target


class TestRobonuggetsDncGuard(unittest.TestCase):
    def test_blocks_oracle_employers_and_domains(self):
        self.assertFalse(evaluate_outreach_target(company="Oracle")["allowed"])
        self.assertFalse(evaluate_outreach_target(company="Oracle Health")["allowed"])
        self.assertFalse(evaluate_outreach_target(company="Cerner")["allowed"])
        self.assertFalse(evaluate_outreach_target(company="Acme", recipient_domain="oracle.com")["allowed"])

    def test_blocks_matt_colmia_regardless_of_company(self):
        self.assertFalse(evaluate_outreach_target(company="", person_name="Matt Colmia")["allowed"])
        self.assertFalse(evaluate_outreach_target(company="Example Corp", person_name="Matt Colmia")["allowed"])

    def test_allows_non_oracle_employers_hosted_on_oracle_cloud_ats(self):
        jpmc = evaluate_outreach_target(company="JPMorganChase", url="https://jpmc.fa.oraclecloud.com/hcmUI")
        ucsf = evaluate_outreach_target(company="UCSF", url="https://ucsf.fa.us2.oraclecloud.com/hcmUI")
        coherent = evaluate_outreach_target(company="Coherent", url="https://coherent.fa.oraclecloud.com/jobs")
        self.assertTrue(jpmc["allowed"] and jpmc["atsHostCarveOut"])
        self.assertTrue(ucsf["allowed"] and ucsf["atsHostCarveOut"])
        self.assertTrue(coherent["allowed"] and coherent["atsHostCarveOut"])


if __name__ == "__main__":
    unittest.main()
