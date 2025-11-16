#!/usr/bin/env python3
"""Script to count code lines excluding documentation."""

from pathlib import Path


def count_lines_in_file(file_path: Path) -> int:
    """Count non-documentation lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        code_lines = 0
        in_docstring = False
        docstring_quote = None

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Handle docstrings
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    # Starting docstring
                    in_docstring = True
                    docstring_quote = '"""' if '"""' in line else "'''"
                    # Check if docstring ends on same line
                    if line.count(docstring_quote) >= 2:
                        in_docstring = False
                else:
                    # Ending docstring
                    if docstring_quote in line:
                        in_docstring = False

            # Skip lines in docstrings
            if in_docstring:
                continue

            # Skip comment lines
            if stripped.startswith('#'):
                continue

            # Skip import statements (optional - remove if you want to count them)
            if stripped.startswith(('import ', 'from ')):
                continue

            code_lines += 1

        return code_lines

    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0


def count_project_lines(project_root: Path) -> dict:
    """Count lines in the entire project."""
    results = {
        'total_files': 0,
        'total_lines': 0,
        'by_extension': {},
        'by_directory': {}
    }

    # File extensions to include
    code_extensions = {'.py', '.js', '.ts', '.cpp', '.c', '.h', '.hpp', '.java', '.go', '.rs'}

    for file_path in project_root.rglob('*'):
        if file_path.is_file() and file_path.suffix in code_extensions:
            # Skip hidden files and common non-code directories
            if any(part.startswith('.') for part in file_path.parts):
                continue
            if any(part in ['node_modules', '__pycache__', '.git', 'venv', '.venv'] for part in file_path.parts):
                continue

            lines = count_lines_in_file(file_path)
            if lines > 0:
                results['total_files'] += 1
                results['total_lines'] += lines

                # Count by extension
                ext = file_path.suffix
                results['by_extension'][ext] = results['by_extension'].get(ext, 0) + lines

                # Count by directory
                dir_name = file_path.parent.name
                if dir_name:
                    results['by_directory'][dir_name] = results['by_directory'].get(dir_name, 0) + lines

    return results


def main():
    """Main function."""
    project_root = Path(__file__).parent.parent

    print(f"Counting code lines in: {project_root}")
    print("=" * 50)

    results = count_project_lines(project_root)

    print(f"Total files: {results['total_files']}")
    print(f"Total code lines: {results['total_lines']}")
    print()

    print("By file extension:")
    for ext, lines in sorted(results['by_extension'].items()):
        print(f"  {ext}: {lines} lines")
    print()

    print("By directory:")
    for dir_name, lines in sorted(results['by_directory'].items()):
        print(f"  {dir_name}/: {lines} lines")


if __name__ == "__main__":
    main()
