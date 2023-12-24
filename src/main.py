import pathlib
import toml
import git
import os
import shutil
import sys

# Make ansi work on windows
os.system("")

# Colors
RED = "\u001b[31m"
BLUE = "\u001b[36m"
GREEN = "\u001b[32m"
RESET = "\u001b[0m"


HERE_DIR = pathlib.Path(__file__).parent.resolve()

with open(HERE_DIR / "config.toml", 'r') as f:
    config = toml.loads(f.read())

INSTALL_DIR = pathlib.Path(config["install_dir"])
INDEX_DIR = pathlib.Path(config["index_clone_dir"])

# ensure its set to a boolean (not a string)
if config["relative_paths"] == True:
    INSTALL_DIR = HERE_DIR / config["install_dir"]
    INDEX_DIR = HERE_DIR / config["index_clone_dir"]

PKG_LIST_DIR = INSTALL_DIR / "package_list.txt"


def _clean_package_index():
    for file in os.listdir(INDEX_DIR):
        file_path = os.path.join(INDEX_DIR, file)
        if os.path.isfile(file_path):
            os.unlink(file_path)
        else:
            shutil.rmtree(file_path)


def _get_package_loc(pkg_name: str) -> pathlib.Path:
    starting_letter = pkg_name[0].lower()
    pkg_index_loc = INDEX_DIR / starting_letter / pkg_name

    if not os.path.exists(INDEX_DIR / starting_letter) or not os.path.exists(pkg_index_loc):
        print(f"{RED}Could not find package:{BLUE} {pkg_name}{RESET}")
        exit(1)

    return pkg_index_loc


def _get_package_versions(pkg_loc: pathlib.Path) -> list[str]:
    return [ver.replace('.toml', '') for ver in os.listdir(pkg_loc)]


def _get_package_config(pkg_loc: pathlib.Path) -> dict:
    with open(pkg_loc / "package.toml", 'r') as f:
        return toml.loads(f.read())


def _get_installed():
    with open(PKG_LIST_DIR, 'r') as f:
        return [line.strip().split(' ') for line in f.readlines() if not line.startswith("#") and line!="\n"]


def refresh_index():
    '''
    CmdDesc: Re-clone the package index. Required on first use
    '''
    url = config["index_url"]

    if config["index_method"].lower() == "git":
        _clean_package_index()
        git.Repo.clone_from(url, INDEX_DIR)


def install_pkg(pkg_name: str, version="latest"):
    '''
    CmdArgs: <pkg_name> [pkg_version]
    CmdDesc: Installs a specified package with an optional version. \
The default is "latest"
    '''
    pkg_loc = _get_package_loc(pkg_name)
    pkg_conf = _get_package_config(pkg_loc)

    if version == "latest":
        version = pkg_conf["latest_version"]

    if version not in _get_package_versions(pkg_loc):
        print(f"{RED}Version: {BLUE}'{version}'{RED} not found for package: {BLUE}'{pkg_name}'{RED}{RESET}")
        exit(1)

    for name, ver in _get_installed():
        if name == pkg_name and ver == version:
            print(f"{RED}Version: {BLUE}'{version}'{RED} is already installed{RESET}")
            exit(1)

    ver_file = pkg_loc / (version + '.toml')
    with open(ver_file, 'r') as f:
        ver_config = toml.loads(f.read())

    install_config = ver_config["Install"]
    install_url = install_config["install_url"]

    install_to = INSTALL_DIR / pkg_name / version
    os.makedirs(INSTALL_DIR / pkg_name, exist_ok=True)
    os.makedirs(install_to)

    if install_config["install_method"].lower() == "git":
        git.Repo.clone_from(install_url, install_to)

    os.symlink(install_to / install_config["package_src_dir"],
               install_to / install_config["install_folder"])

    with open(PKG_LIST_DIR, 'a+') as f:
        f.write(f"\n{pkg_name} {version}")

    os.makedirs(install_to / ".pkg_info")
    with open(install_to / ".pkg_info" / f"{version}.toml", 'w+') as f:
        with open(pkg_loc / f"{version}.toml", 'r') as conf:
            f.write(conf.read())


def _compare_version_gr(v1, v2):
    '''check if a version is greater than another'''
    version1 = [int(num) for num in v1.split('.')]
    version2 = [int(num) for num in v2.split('.')]

    for left, right in zip(version1, version2):
        if left < right:
            return False
        elif left > right:
            return True
        # if they are equal, keep recursing

    # if they are truly equal
    return False


def uninstall_pkg(pkg_name: str, version="latest"):
    '''
    CmdArgs: <pkg_name> [pkg_version]
    CmdDesc: Uninstalls a specified package with an optional version. \
The default is "latest"
    '''
    highest_version = "0.0.0"
    found_version = False

    for c, (name, ver) in enumerate(_get_installed()):
        if name == pkg_name and (ver == version or version == "latest"):
            found_version = True
            if version == "latest" and _compare_version_gr(ver, highest_version):
                highest_version = ver
                continue
            break
    else:
        if version != "latest":
            print(f"{RED}Pkg: {BLUE}'{pkg_name}'{RED} Version: {BLUE}'{version}'{RED} not installed{RESET}")
            exit(1)

    if not found_version:
        print(f"{RED}Pkg: {BLUE}'{pkg_name}'{RED} not installed{RESET}")
        exit(1)

    if version == "latest":
        version = highest_version

    version_directory = INSTALL_DIR / pkg_name / version
    shutil.rmtree(version_directory, ignore_errors=True)

    with open(PKG_LIST_DIR, 'r+') as f:
        lines = f.readlines()
        f.seek(0)
        for c, data in enumerate(lines):
            if data == "\n":
                continue
            if data.strip() == f"{pkg_name} {version}":
                continue
            f.write('\n'+data.strip())
        f.truncate()


def _generate_usage_str(name: str, func):
    cmd_args = ""
    cmd_description = ""

    for line in func.__doc__.split('\n'):
        line = line.strip()
        if line.startswith("CmdArgs:"):
            cmd_args = line[len("CmdArgs: "):]
        if line.startswith("CmdDesc:"):
            cmd_description = line[len("CmdDesc: "):]

    return f"{name}:\n  Usage:\n    {BLUE}BPM {name} {cmd_args}" + \
           f"\n  {GREEN}Description:\n    {cmd_description}"


def help_command():
    '''
    CmdDesc: Show this page
    '''
    print(GREEN, end="")
    print("Here are all the sub-commands:\n")
    for name, func in commands.items():
        print(_generate_usage_str(name, func))
    print(RESET, end="")


def _get_package_dir(pkg_name, version="latest"):
    highest_version = "0.0.0"
    found_version = False

    for name, ver in _get_installed():
        if name == pkg_name and (ver == version or version == "latest"):
            found_version = True
            if version == "latest" and _compare_version_gr(ver, highest_version):
                highest_version = ver
                continue
            break
    else:
        if version != "latest":
            print(f"{RED}Pkg: {BLUE}'{pkg_name}'{RED} Version: {BLUE}'{version}'{RED} not installed{RESET}")
            exit(1)

    if not found_version:
        print(f"{RED}Pkg: {BLUE}'{pkg_name}'{RED} not installed{RESET}")
        exit(1)

    if version == "latest":
        version = highest_version

    pkg_dir = INSTALL_DIR / pkg_name / version
    config = pkg_dir / ".pkg_info" / f"{version}.toml"

    with open(config, 'r') as f:
        return pkg_dir / toml.loads(f.read())["Install"]["install_folder"]


def get_package_dirs(*package_list):
    '''
    CmdArgs: <pkg_name> [pkg_version]
    CmdDesc: List all install directories for packages
The default is "latest"
    '''

    for pkg_text in package_list:
        if "=" in pkg_text:
            pkg_name, pkg_version = pkg_text.split('=')
        else:
            pkg_name, pkg_version = pkg_text, "latest"

        print(_get_package_dir(pkg_name, pkg_version))


commands = {
    "refresh": refresh_index,
    "install": install_pkg,
    "help": help_command,
    "uninstall": uninstall_pkg,
    "pkgdirs": get_package_dirs
}


if __name__ == "__main__":
    args = sys.argv[1:]

    command = commands[args[0]]

    try:
        if len(args) < 2:
            command()
        else:
            command(*args[1:])
    except TypeError as e:
        print(f"{RED}Invalid number of arguments used.{RESET}")
