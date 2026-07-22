import tomllib
import unittest
from pathlib import Path

import ping


class VersionTests(unittest.TestCase):
    def test_runtime_version_is_derived_from_project_metadata(self) -> None:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject.open("rb") as file:
            expected = tomllib.load(file)["project"]["version"]

        self.assertEqual(ping.__version__, expected)


if __name__ == "__main__":
    unittest.main()
