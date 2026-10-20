import unittest

from diagnostics import DiagnosticSample, DiagnosticThresholds, analyze_samples


class AnalyzeSamplesTests(unittest.TestCase):
    def samples(self, count=8, **values):
        return [DiagnosticSample(timestamp=float(index), **values) for index in range(count)]

    def test_threshold_boundary_is_inclusive_and_sustained(self):
        report = analyze_samples(self.samples(cpu_percent=85.0))
        self.assertIn("Sustained high CPU utilization", [
                      item.title for item in report.findings])

    def test_one_high_sample_is_insufficient(self):
        samples = [DiagnosticSample(timestamp=float(index), cpu_percent=99.0 if index == 7 else 10.0)
                   for index in range(8)]
        report = analyze_samples(samples)
        self.assertEqual(report.findings, ())
        self.assertEqual(report.assessment,
                         "No sustained pressure signals detected")

    def test_too_few_samples_are_insufficient(self):
        report = analyze_samples(self.samples(count=4, cpu_percent=100.0))
        self.assertEqual(report.assessment, "Insufficient data")

    def test_missing_values_do_not_count_as_low_or_high(self):
        samples = [
            DiagnosticSample(timestamp=float(index),
                             cpu_percent=90.0 if index < 4 else None)
            for index in range(8)
        ]
        report = analyze_samples(samples)
        self.assertNotIn("Sustained high CPU utilization", [
                         item.title for item in report.findings])
        self.assertEqual(report.assessment, "Insufficient data")

    def test_ram_pressure_requires_both_high_use_and_low_available_memory(self):
        high_use_only = self.samples(ram_percent=95.0, ram_available_gb=4.0)
        pressured = self.samples(ram_percent=88.0, ram_available_gb=1.5)
        self.assertNotIn(
            "RAM", [item.component for item in analyze_samples(high_use_only).findings])
        finding = next(item for item in analyze_samples(
            pressured).findings if item.component == "RAM")
        self.assertEqual(finding.confidence, "High")

    def test_conflicting_cpu_and_gpu_signals_are_both_reported(self):
        report = analyze_samples(self.samples(
            cpu_percent=90.0, gpu_percent=95.0))
        self.assertIn("Multiple pressure signals", report.assessment)
        self.assertEqual(
            {item.component for item in report.findings}, {"CPU", "GPU"})

    def test_nvml_thermal_flag_is_explicit_evidence(self):
        report = analyze_samples(self.samples(
            gpu_thermal_throttling="Active (hardware thermal)"))
        finding = next(
            item for item in report.findings if "thermal throttling" in item.title.lower())
        self.assertEqual(finding.confidence, "High")
        self.assertIn("NVML reported", finding.observed)

    def test_custom_thresholds_are_respected(self):
        thresholds = DiagnosticThresholds(cpu_percent=70.0)
        report = analyze_samples(self.samples(cpu_percent=70.0), thresholds)
        self.assertIn("Sustained high CPU utilization", [
                      item.title for item in report.findings])

    def test_storage_limitation_is_reported_without_diagnosing_it(self):
        report = analyze_samples(self.samples(cpu_percent=20.0))
        self.assertTrue(
            any("Storage pressure is not assessed" in item for item in report.limitations))
        self.assertNotIn(
            "Storage", [item.component for item in report.findings])


if __name__ == "__main__":
    unittest.main()
