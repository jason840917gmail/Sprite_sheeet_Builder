from __future__ import annotations

import unittest
from unittest.mock import patch

from sprite_sheet_cleaner.ai_worker.capabilities import (
    CUDA_PROVIDER,
    ComputeSelectionError,
    discover_nvidia_devices,
    parse_nvidia_smi_csv,
    select_backend,
)


class ComputeCapabilitiesTests(unittest.TestCase):
    def test_parse_nvidia_csv(self) -> None:
        devices = parse_nvidia_smi_csv("RTX 4070, 8192, 4096\n")
        self.assertEqual(devices[0].name, "RTX 4070")
        self.assertEqual(devices[0].free_memory_bytes, 4096 * 1024 * 1024)

    def test_discovery_handles_missing_tool(self) -> None:
        with patch("sprite_sheet_cleaner.ai_worker.capabilities.shutil.which", return_value=None):
            self.assertEqual(discover_nvidia_devices(executable=None, runner=None), ())

    def test_auto_falls_back_when_warmup_fails(self) -> None:
        result = select_backend("auto", (CUDA_PROVIDER, "CPUExecutionProvider"), warmup=lambda _: (_ for _ in ()).throw(RuntimeError("DLL")))
        self.assertEqual(result.backend, "cpu")
        self.assertIn("DLL", result.fallback_reason or "")

    def test_forced_cuda_fails_without_opt_in(self) -> None:
        with self.assertRaises(ComputeSelectionError):
            select_backend("cuda", ("CPUExecutionProvider",))

