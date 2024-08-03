import mimetypes
import re
from pathlib import Path
from typing import List, Optional, Dict

import pathspec
import typer
from rich import print
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree

app = typer.Typer()


class FilteringError(Exception):
    """Custom exception for filtering errors."""
    pass


def validate_filters(include: List[str], exclude: List[str], name: str) -> None:
    """
    Validate that both include and exclude lists are not specified simultaneously.

    :param include: List of include patterns.
    :param exclude: List of exclude patterns.
    :param name: Name of the filter category.
    :raises FilteringError: If both include and exclude are specified.
    """
    if include and exclude:
        raise FilteringError(f"Error: Cannot specify both include and exclude for {name}. Please use only one.")


def parse_gitignore(gitignore_path: Path) -> Optional[pathspec.PathSpec]:
    """
    Parse a .gitignore file and return a PathSpec object.

    :param gitignore_path: Path to the .gitignore file.
    :return: PathSpec object or None if the file does not exist.
    """
    if not gitignore_path.exists():
        return None
    with gitignore_path.open() as gitignore_file:
        spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_file)
    return spec


def is_binary_file(file_path: Path) -> bool:
    """
    Check if a file is binary.

    :param file_path: Path to the file.
    :return: True if the file is binary, False otherwise.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # If we can't determine the MIME type, try to read it as text
        try:
            with file_path.open('r') as f:
                f.read(1024)
            return False
        except UnicodeDecodeError:
            return True
    return not mime_type.startswith('text')


def is_file_empty(file_path: Path) -> bool:
    """
    Check if a file is empty.

    :param file_path: Path to the file.
    :return: True if the file is empty, False otherwise.
    """
    if not file_path.is_file():
        return False
    if file_path.stat().st_size == 0:
        return True
    if is_binary_file(file_path):
        return False  # Assume binary files are not empty
    return file_path.read_text().strip() == ''


def filter_path(
        path: Path,
        root_path: Path,
        gitignore_spec: Optional[pathspec.PathSpec],
        include_dirs: List[str],
        exclude_dirs: List[str],
        include_files: List[str],
        exclude_files: List[str],
        include_extensions: List[str],
        exclude_extensions: List[str],
        include_binary: bool
) -> bool:
    """
    Filter a path based on various criteria.

    :param path: Path to the file or directory.
    :param root_path: Root path for relative calculations.
    :param gitignore_spec: PathSpec object for .gitignore rules.
    :param include_dirs: List of directory include patterns.
    :param exclude_dirs: List of directory exclude patterns.
    :param include_files: List of file include patterns.
    :param exclude_files: List of file exclude patterns.
    :param include_extensions: List of file extension include patterns.
    :param exclude_extensions: List of file extension exclude patterns.
    :param include_binary: Whether to include binary files.
    :return: True if the path passes the filters, False otherwise.
    """
    relative_path = path.relative_to(root_path)
    str_path = str(relative_path)

    # Apply gitignore first
    if gitignore_spec and gitignore_spec.match_file(path.relative_to(root_path)):
        return False

    if path.is_dir():
        if include_dirs:
            return any(re.search(pattern, str_path) for pattern in include_dirs)
        if exclude_dirs:
            return not any(re.search(pattern, str_path) for pattern in exclude_dirs)
    else:
        if not include_binary and is_binary_file(path):
            return False
        if include_files:
            return any(re.search(pattern, str_path) or re.search(pattern, path.name) for pattern in include_files)
        if exclude_files:
            return not any(re.search(pattern, str_path) or re.search(pattern, path.name) for pattern in exclude_files)
        if include_extensions:
            return path.suffix.lstrip('.') in include_extensions
        if exclude_extensions:
            return path.suffix.lstrip('.') not in exclude_extensions
    return True


def add_to_tree(
        tree: Tree,
        path: Path,
        root_path: Path,
        gitignore_spec: Optional[pathspec.PathSpec],
        tree_filters: Dict[str, List[str]],
        content_filters: Dict[str, List[str]]
) -> bool:
    """
    Add a path to a tree structure based on filters.

    :param tree: Tree object to add paths to.
    :param path: Path to the file or directory.
    :param root_path: Root path for relative calculations.
    :param gitignore_spec: PathSpec object for .gitignore rules.
    :param tree_filters: Dictionary of filters for the tree.
    :param content_filters: Dictionary of filters for the content.
    :return: True if the path was added to the tree, False otherwise.
    """
    relative_path = path.relative_to(root_path)

    # Check gitignore first
    if gitignore_spec and gitignore_spec.match_file(relative_path):
        return False

    if not filter_path(path, root_path, gitignore_spec, **tree_filters):
        return False

    if path.is_file():
        file_text = Text(path.name)
        if is_file_empty(path):
            file_text.append(" [empty]", style="dim italic")
        elif is_binary_file(path):
            file_text.append(" [binary]", style="dim italic")
        elif filter_path(path, root_path, gitignore_spec, **content_filters):
            file_text.append(" [content]", style="dim italic")
        tree.add(file_text)
        return True
    else:
        branch = Tree(path.name)
        has_visible_children = False
        for child in path.iterdir():
            if add_to_tree(branch, child, root_path, gitignore_spec, tree_filters, content_filters):
                has_visible_children = True

        if has_visible_children:
            tree.add(branch)
            return True
        else:
            return False


def print_file_contents(path: Path) -> None:
    """
    Print the contents of a file.

    :param path: Path to the file.
    """
    if not is_file_empty(path):
        print(f"\n### {path}")
        syntax = Syntax.from_path(path, line_numbers=True)
        print(syntax)
        print(f"### end of {path}\n")


@app.command()
def generate_context(
        path: str = typer.Argument(".", help="Path to the directory to analyze"),
        gitignore: Optional[Path] = typer.Option(None, "--gitignore", "-g", help="Path to .gitignore file"),
        tree_include_dirs: Optional[List[str]] = typer.Option(None, "--tree-include-dir",
                                                              help="Directories to include (regex)"),
        tree_exclude_dirs: Optional[List[str]] = typer.Option(None, "--tree-exclude-dir",
                                                              help="Directories to exclude (regex)"),
        tree_include_files: Optional[List[str]] = typer.Option(None, "--tree-include-file",
                                                               help="Files to include (regex, can be full path or filename)"),
        tree_exclude_files: Optional[List[str]] = typer.Option(None, "--tree-exclude-file",
                                                               help="Files to exclude (regex, can be full path or filename)"),
        tree_include_extensions: Optional[List[str]] = typer.Option(None, "--tree-include-ext",
                                                                    help="File extensions to include"),
        tree_exclude_extensions: Optional[List[str]] = typer.Option(None, "--tree-exclude-ext",
                                                                    help="File extensions to exclude"),
        content_include_dirs: Optional[List[str]] = typer.Option(None, "--content-include-dir",
                                                                 help="Additional directories to include in content (regex)"),
        content_exclude_dirs: Optional[List[str]] = typer.Option(None, "--content-exclude-dir",
                                                                 help="Additional directories to exclude from content (regex)"),
        content_include_files: Optional[List[str]] = typer.Option(None, "--content-include-file",
                                                                  help="Additional files to include in content (regex, can be full path or filename)"),
        content_exclude_files: Optional[List[str]] = typer.Option(None, "--content-exclude-file",
                                                                  help="Additional files to exclude from content (regex, can be full path or filename)"),
        content_include_extensions: Optional[List[str]] = typer.Option(None, "--content-include-ext",
                                                                       help="Additional file extensions to include in content"),
        content_exclude_extensions: Optional[List[str]] = typer.Option(None, "--content-exclude-ext",
                                                                       help="Additional file extensions to exclude from content"),
        exclude_git: bool = typer.Option(True, "--include-git/--exclude-git",
                                         help="Exclude .git directory from analysis"),
        include_binary: bool = typer.Option(False, "--include-binary/--exclude-binary",
                                            help="Include binary files in analysis"),
) -> None:
    """
    Generate context from codebases for LLMs with exclusive filtering options and .gitignore support.
    Tree filters apply to both tree and content. Content filters only affect content display.
    Include and exclude options are mutually exclusive for each category.
    .gitignore patterns take precedence over other filters and apply to both tree and content.
    Empty files are marked in the tree and excluded from content output.
    .git directory and binary files are excluded by default.
    File inclusion/exclusion can be specified by full path or filename.
    """
    try:
        validate_filters(tree_include_dirs, tree_exclude_dirs, "tree directories")
        validate_filters(tree_include_files, tree_exclude_files, "tree files")
        validate_filters(tree_include_extensions, tree_exclude_extensions, "tree extensions")
        validate_filters(content_include_dirs, content_exclude_dirs, "content directories")
        validate_filters(content_include_files, content_exclude_files, "content files")
        validate_filters(content_include_extensions, content_exclude_extensions, "content extensions")

        root_path = Path(path).resolve()
        if not root_path.exists():
            typer.echo(f"Error: Path '{root_path}' does not exist.")
            raise typer.Exit(code=1)

        gitignore_spec = None
        if gitignore:
            gitignore_path = Path(gitignore).resolve()
        else:
            gitignore_path = root_path / ".gitignore"

        if gitignore_path.exists():
            with gitignore_path.open() as gitignore_file:
                gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_file)
        elif gitignore:
            typer.echo(f"Warning: Specified .gitignore file at {gitignore_path} does not exist.")

        tree_filters = {
            "include_dirs": tree_include_dirs or [],
            "exclude_dirs": tree_exclude_dirs or [],
            "include_files": tree_include_files or [],
            "exclude_files": tree_exclude_files or [],
            "include_extensions": tree_include_extensions or [],
            "exclude_extensions": tree_exclude_extensions or [],
            "include_binary": include_binary
        }

        content_filters = {
            "include_dirs": (tree_include_dirs or []) + (content_include_dirs or []),
            "exclude_dirs": (tree_exclude_dirs or []) + (content_exclude_dirs or []),
            "include_files": (tree_include_files or []) + (content_include_files or []),
            "exclude_files": (tree_exclude_files or []) + (content_exclude_files or []),
            "include_extensions": (tree_include_extensions or []) + (content_include_extensions or []),
            "exclude_extensions": (tree_exclude_extensions or []) + (content_exclude_extensions or []),
            "include_binary": include_binary
        }

        if exclude_git:
            tree_filters["exclude_dirs"].append(r"\.git")
            content_filters["exclude_dirs"].append(r"\.git")

        # Generate tree structure
        tree = Tree(f"[bold]{root_path.name}")
        for child in root_path.iterdir():
            add_to_tree(tree, child, root_path, gitignore_spec, tree_filters, content_filters)

        if len(tree.children) > 0:
            print(tree)
        else:
            print("No visible content based on the current filters and .gitignore rules.")

        # Print file contents
        for item in root_path.rglob("*"):
            if item.is_file() and filter_path(item, root_path, gitignore_spec, **content_filters):
                if not is_binary_file(item) or include_binary:
                    print_file_contents(item)

    except Exception as e:
        typer.echo(f"An error occurred: {str(e)}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
