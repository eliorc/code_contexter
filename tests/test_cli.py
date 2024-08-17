from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import app


@pytest.fixture
def runner() -> CliRunner:
    """
    Fixture to create a CliRunner instance.

    :return: A CliRunner instance.
    """
    return CliRunner()


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """
    Fixture to create a test directory structure.

    :param tmp_path: Temporary path provided by pytest.
    :return: Path to the created test directory.
    """
    top = tmp_path / "top"
    top.mkdir()
    (top / "file1.txt").write_text("Content of file1")
    (top / "file2.py").write_text("print('Hello')")

    level1 = top / "level1"
    level1.mkdir()
    (level1 / "file3.txt").write_text("Content of file3")

    app = level1 / "app"
    app.mkdir()
    (app / "main.py").write_text("def main():\n    pass")

    top_app = top / "app"
    top_app.mkdir()
    (top_app / "main.py").write_text("def top_main():\n    pass")

    return tmp_path


def test_default_behavior(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the default behavior of the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir)])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "├── file1.txt [content]" in result.output
    assert "├── file2.py [content]" in result.output
    assert "├── level1" in result.output
    assert "│   ├── file3.txt [content]" in result.output
    assert "│   └── app" in result.output
    assert "│       └── main.py [content]" in result.output
    assert "└── app" in result.output
    assert "    └── main.py [content]" in result.output
    assert "Content of file1" in result.output
    assert "print('Hello')" in result.output
    assert "Content of file3" in result.output
    assert "def main():" in result.output
    assert "def top_main():" in result.output


def test_tree_filter_only(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the tree filter functionality of the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir), "--tree-include-dir", "level1"])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "└── level1" in result.output
    assert "    ├── file3.txt [content]" in result.output
    assert "    └── app" in result.output
    assert "        └── main.py [content]" in result.output
    assert "file1.txt" not in result.output
    assert "file2.py" not in result.output
    assert "Content of file1" in result.output
    assert "print('Hello')" in result.output
    assert "Content of file3" in result.output
    assert "def main():" in result.output
    assert "def top_main():" in result.output


def test_content_filter_only(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the content filter functionality of the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir), "--content-include-ext", "py"])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "├── file1.txt" in result.output
    assert "├── file2.py [content]" in result.output
    assert "├── level1" in result.output
    assert "│   ├── file3.txt" in result.output
    assert "│   └── app" in result.output
    assert "│       └── main.py [content]" in result.output
    assert "└── app" in result.output
    assert "    └── main.py [content]" in result.output
    assert "Content of file1" not in result.output
    assert "Content of file3" not in result.output
    assert "print('Hello')" in result.output
    assert "def main():" in result.output
    assert "def top_main():" in result.output


def test_tree_and_content_filter(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the combination of tree and content filters in the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir), "--tree-include-dir", "level1", "--content-include-ext", "txt"])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "└── level1" in result.output
    assert "    ├── file3.txt [content]" in result.output
    assert "    └── app" in result.output
    assert "        └── main.py" in result.output
    assert "file1.txt [content]" in result.output
    assert "file2.py" not in result.output
    assert "Content of file1" in result.output
    assert "Content of file3" in result.output
    assert "print('Hello')" not in result.output
    assert "def main():" not in result.output
    assert "def top_main():" not in result.output


def test_content_filter_adds_to_tree(runner: CliRunner, test_dir: Path) -> None:
    """
    Test that content filters can add files to the tree structure in the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir), "--tree-include-dir", "level1", "--content-include-file", "file1.txt"])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "├── file1.txt [content]" in result.output
    assert "└── level1" in result.output
    assert "    ├── file3.txt" in result.output
    assert "    └── app" in result.output
    assert "        └── main.py" in result.output
    assert "file2.py" not in result.output
    assert "Content of file1" in result.output
    assert "Content of file3" not in result.output
    assert "print('Hello')" not in result.output
    assert "def main():" not in result.output
    assert "def top_main():" not in result.output


def test_gitignore_support(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the .gitignore support in the CLI application.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    gitignore = test_dir / "top" / ".gitignore"
    gitignore.write_text("*.txt\n")

    result = runner.invoke(app, [str(test_dir / "top"), "--gitignore", str(gitignore)])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "├── file2.py [content]" in result.output
    assert "├── level1" in result.output
    assert "│   └── app" in result.output
    assert "│       └── main.py [content]" in result.output
    assert "└── app" in result.output
    assert "    └── main.py [content]" in result.output
    assert "file1.txt" not in result.output
    assert "file3.txt" not in result.output
    assert "print('Hello')" in result.output
    assert "def main():" in result.output
    assert "def top_main():" in result.output


def test_empty_directory(runner: CliRunner, tmp_path: Path) -> None:
    """
    Test the behavior of the CLI application with an empty directory.

    :param runner: CliRunner instance.
    :param tmp_path: Temporary path provided by pytest.
    """
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 0
    assert "No visible content based on the current filters and .gitignore rules." in result.output


def test_nonexistent_directory(runner: CliRunner) -> None:
    """
    Test the behavior of the CLI application with a nonexistent directory.

    :param runner: CliRunner instance.
    """
    result = runner.invoke(app, ["/path/that/does/not/exist"])
    assert result.exit_code == 1
    assert "Error: Path '/path/that/does/not/exist' does not exist." in result.output


def test_include_exclude_conflict(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the behavior of the CLI application when both include and exclude options are specified.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    result = runner.invoke(app, [str(test_dir), "--tree-include-dir", "level1", "--tree-exclude-dir", "app"])
    assert result.exit_code == 1
    assert "Error: Cannot specify both include and exclude for tree directories." in result.output


def test_binary_file_handling(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the behavior of the CLI application with binary files.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    binary_file = test_dir / "top" / "binary.bin"
    binary_file.write_bytes(b'\x00\x01\x02\x03')

    result = runner.invoke(app, [str(test_dir), "--include-binary"])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "└── binary.bin [binary]" in result.output

    result = runner.invoke(app, [str(test_dir)])  # Default behavior (exclude binary)
    assert result.exit_code == 0
    assert "binary.bin" not in result.output


def test_empty_file_handling(runner: CliRunner, test_dir: Path) -> None:
    """
    Test the behavior of the CLI application with empty files.

    :param runner: CliRunner instance.
    :param test_dir: Path to the test directory.
    """
    empty_file = test_dir / "top" / "empty.txt"
    empty_file.touch()

    result = runner.invoke(app, [str(test_dir)])
    assert result.exit_code == 0
    assert "top" in result.output
    assert "└── empty.txt [empty]" in result.output
