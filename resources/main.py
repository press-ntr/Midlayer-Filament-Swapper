import argparse
import re

from pathlib import Path

# See if we can add better instructions here...
PATCH_GCODE = [
           "; --- Manual filament change ---",
           "M400 U1",
           "; --- End filament change ---"
]

VERSION = None

def find_filament_change_tag(gcode: list[str]) -> str:
    VAR_NAME = "; change_filament_gcode = ;"
    for line in gcode:
        if VAR_NAME not in line:
            continue
        tag: re.Match[str] = re.search(r'===== \w+? \d{8} =======================', line)
        if not tag:
            raise RuntimeError(f"Couldn't parse value from line: {line}")
        return tag.group()
    raise RuntimeError("No filament change tags were found!")


def get_filament_change_sections(gcode: list[str]) -> list[tuple[int,int]]:
    # First occurance is the variable definition
    found_first = False
    # Second occurance is the first filament being set up when Bambu Studio v1 was used to generate GCode
    found_second = False
    change_sections = []

    tag = find_filament_change_tag(gcode)
    start = None
    for i, line in enumerate(gcode):
        # If we found a filement change tag, lets look for when it ends
        if start:
            # v2 adds an OBJECT_ID travel block
            if not line.startswith('; FEATURE:') and not line.startswith('; OBJECT_ID:'):
                continue
            change_sections.append((start, i))
            start = None
            print(f"Found filament change boundaries: {change_sections[-1]}")
            continue
        if not start:
            if not tag in line:
                continue
            if not found_first:
                found_first = True
                continue
            if VERSION == 1 and not found_second:
                found_second = True
                continue
            start = i
    if start:
        raise RuntimeError(f"File ended, but we didn't find an end for a change at line {tag}")
        
    return change_sections

def patch_gcode(gcode: list[str], change_sections: list[tuple[int,int]], remove_change_code: bool = False) -> list[str]:
    for start, end in reversed(change_sections):
        print(f"Patching instruction into: {start}:{end}")
        if remove_change_code:
            print("Deleting filament change code...")
            del gcode[start:end]
            gcode.insert(start, "M400 U1\n")
            gcode.insert(start, "; --- Manual filament change ---\n")
        else:
            # This maintains the visual of the filament change when the gcode is loaded into bambu studio, but it may make things hard for the printer in the future?
            gcode.insert(end, "M400 U1\n")  # Insert after the end of the original section
            gcode.insert(end, "; --- Manual filament change ---\n")
        print("Pause added!")

def inject_pauses(gcode: list[str]) -> list[str]:
    change_sections = get_filament_change_sections(gcode)
    patch_gcode(gcode, change_sections)

def read_in_file(path: str = "input.gcode") -> list[str]:
    try:
        with open(path, 'r+') as f:
            return f.readlines()
    except Exception as e:
        raise RuntimeError(f"Error reading file: {path} | Error: {e}")


def write_out_file(gcode: list[str], path: str = "output.gcode"):
    try:
        with open(path, 'w+') as f:
            f.writelines(gcode)
    except Exception as e:
        raise RuntimeError(f"Error writing file: {path} | Error: {e}")

def validate_path(path: str, must_exist: bool = False):
    PROJECT_DIR = Path(__file__).resolve().parent
    _path = Path(path).resolve()
    if must_exist and not _path.is_file():
        raise FileNotFoundError(f"The provided input file does not exist: {_path}")
    
    try:
        _path.relative_to(PROJECT_DIR)
    except ValueError:
        raise ValueError(f"The provided path must exist inside the project directory: {_path}")
    

def get_version(gcode: str):
    global VERSION
    version_str = "; BambuStudio "
    for line in gcode:
        if version_str in line:
            version = line.split(version_str)[-1]
            if version.startswith("01"):
                VERSION = 1
            elif version.startswith("02"):
                VERSION = 2
            else:
                raise RuntimeError(f"Unknown version found: {version}")
        if VERSION is not None:
            print(f"BambuStudio version detected: {VERSION}")
            return
    if VERSION is None:
        raise RuntimeError(f"Version was not detected in the gcode!")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch G-code files to inject manual filament change prompts."
    )
    parser.add_argument(
        "-i", "--input", type=str, required=True, help="Path to the input G-code file"
    )
    parser.add_argument(
        "-o", "--output", type=str, required=True, help="Path to the output G-code file"
    )

    args = parser.parse_args()

    validate_path(args.input, must_exist=True)
    validate_path(args.output)

    return args

def main_from_browser():
    gcode = read_in_file()
    get_version(gcode)
    inject_pauses(gcode)
    write_out_file(gcode)

def main():
    args = parse_args()
    gcode = read_in_file(args.input)
    get_version(gcode)
    inject_pauses(gcode)
    write_out_file(gcode, args.output)


# if __name__ == "__main__":
#     main()
