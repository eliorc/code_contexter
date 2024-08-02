import typer
from pathlib import Path
import re
from rich import print
from rich.tree import Tree
from rich.text import Text
from rich.syntax import Syntax
from typing import List, Optional
import pathspec

app = typer.Typer()


class FilteringError(Exception):
    pass


def validate_filters(include: List[str], exclude: List[str], name: str):
    if include and exclude:
        raise FilteringError(f"Error: Cannot specify both include and exclude for {name}. Please use only one.")


def parse_gitignore(gitignore_path: Path):
    if not gitignore_path.exists():
        return None
    with gitignore_path.open() as gitignore_file:
        spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_file)
    return spec


def is_file_empty(file_path: Path) -> bool:
    return file_path.stat().st_size == 0 or file_path.read_text().strip() == ''


def filter_path(
        path: Path,
        root_path: Path,
        gitignore_spec: pathspec.PathSpec,
        include_dirs: List[str],
        exclude_dirs: List[str],
        include_files: List[str],
        exclude_files: List[str],
        include_extensions: List[str],
        exclude_extensions: List[str]
) -> bool:
    if gitignore_spec and gitignore_spec.match_file(path.relative_to(root_path)):
        return False

    if path.is_dir():
        if include_dirs:
            return any(re.search(pattern, str(path)) for pattern in include_dirs)
        if exclude_dirs:
            return not any(re.search(pattern, str(path)) for pattern in exclude_dirs)
    else:
        if include_files:
            return any(re.search(pattern, path.name) for pattern in include_files)
        if exclude_files:
            return not any(re.search(pattern, path.name) for pattern in exclude_files)
        if include_extensions:
            return path.suffix.lstrip('.') in include_extensions
        if exclude_extensions:
            return path.suffix.lstrip('.') not in exclude_extensions
    return True


def add_to_tree(
    tree: Tree,
    path: Path,
    root_path: Path,
    gitignore_spec: pathspec.PathSpec,
    tree_filters: dict,
    content_filters: dict
):
    if not filter_path(path, root_path, gitignore_spec, **tree_filters):
        return

    if path.is_file():
        content_included = filter_path(path, root_path, gitignore_spec, **content_filters)
        file_text = Text(path.name)
        if content_included:
            if is_file_empty(path):
                file_text.append(" [empty]", style="dim italic")
            else:
                file_text.append(" [content]", style="dim italic")
        tree.add(file_text)
    else:
        if path != root_path:  # Only add directories that are not the root
            branch = tree.add(path.name)
            for child in path.iterdir():
                add_to_tree(branch, child, root_path, gitignore_spec, tree_filters, content_filters)
        else:  # For the root, add children directly to the tree
            for child in path.iterdir():
                add_to_tree(tree, child, root_path, gitignore_spec, tree_filters, content_filters)


def print_file_contents(path: Path):
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
                                                               help="Files to include (regex)"),
        tree_exclude_files: Optional[List[str]] = typer.Option(None, "--tree-exclude-file",
                                                               help="Files to exclude (regex)"),
        tree_include_extensions: Optional[List[str]] = typer.Option(None, "--tree-include-ext",
                                                                    help="File extensions to include"),
        tree_exclude_extensions: Optional[List[str]] = typer.Option(None, "--tree-exclude-ext",
                                                                    help="File extensions to exclude"),
        content_include_dirs: Optional[List[str]] = typer.Option(None, "--content-include-dir",
                                                                 help="Additional directories to include in content (regex)"),
        content_exclude_dirs: Optional[List[str]] = typer.Option(None, "--content-exclude-dir",
                                                                 help="Additional directories to exclude from content (regex)"),
        content_include_files: Optional[List[str]] = typer.Option(None, "--content-include-file",
                                                                  help="Additional files to include in content (regex)"),
        content_exclude_files: Optional[List[str]] = typer.Option(None, "--content-exclude-file",
                                                                  help="Additional files to exclude from content (regex)"),
        content_include_extensions: Optional[List[str]] = typer.Option(None, "--content-include-ext",
                                                                       help="Additional file extensions to include in content"),
        content_exclude_extensions: Optional[List[str]] = typer.Option(None, "--content-exclude-ext",
                                                                       help="Additional file extensions to exclude from content"),
):
    """
    Generate context from codebases for LLMs with exclusive filtering options and .gitignore support.
    Tree filters apply to both tree and content. Content filters only affect content display.
    Include and exclude options are mutually exclusive for each category.
    .gitignore patterns take precedence over other filters and apply to both tree and content.
    Empty files are marked in the tree and excluded from content output.
    """
    try:
        validate_filters(tree_include_dirs, tree_exclude_dirs, "tree directories")
        validate_filters(tree_include_files, tree_exclude_files, "tree files")
        validate_filters(tree_include_extensions, tree_exclude_extensions, "tree extensions")
        validate_filters(content_include_dirs, content_exclude_dirs, "content directories")
        validate_filters(content_include_files, content_exclude_files, "content files")
        validate_filters(content_include_extensions, content_exclude_extensions, "content extensions")
    except FilteringError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    root_path = Path(path).resolve()
    if not root_path.exists():
        typer.echo(f"Error: Path '{root_path}' does not exist.")
        raise typer.Exit(code=1)

    gitignore_spec = None
    if gitignore:
        gitignore_path = Path(gitignore).resolve()
    else:
        gitignore_path = root_path / ".gitignore"

    gitignore_spec = parse_gitignore(gitignore_path)
    if gitignore and not gitignore_spec:
        typer.echo(f"Warning: Could not parse .gitignore file at {gitignore_path}")

    tree_filters = {
        "include_dirs": tree_include_dirs or [],
        "exclude_dirs": tree_exclude_dirs or [],
        "include_files": tree_include_files or [],
        "exclude_files": tree_exclude_files or [],
        "include_extensions": tree_include_extensions or [],
        "exclude_extensions": tree_exclude_extensions or [],
    }

    content_filters = {
        "include_dirs": (tree_include_dirs or []) + (content_include_dirs or []),
        "exclude_dirs": (tree_exclude_dirs or []) + (content_exclude_dirs or []),
        "include_files": (tree_include_files or []) + (content_include_files or []),
        "exclude_files": (tree_exclude_files or []) + (content_exclude_files or []),
        "include_extensions": (tree_include_extensions or []) + (content_include_extensions or []),
        "exclude_extensions": (tree_exclude_extensions or []) + (content_exclude_extensions or []),
    }

    # Generate tree structure
    tree = Tree(f"[bold]{root_path.name}")
    for child in root_path.iterdir():
        add_to_tree(tree, child, root_path, gitignore_spec, tree_filters, content_filters)
    print(tree)

    # Print file contents
    for item in root_path.rglob("*"):
        if item.is_file() and filter_path(item, root_path, gitignore_spec, **content_filters):
            print_file_contents(item)


if __name__ == "__main__":
    app()
