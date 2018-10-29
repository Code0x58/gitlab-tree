"""Module for the config schema, loading, and runtime representation.

The only method expected to be used from this module is find_and_load_config,
other members should be considered private.

"""
import os
import subprocess
import sys
import typing
from pathlib import Path

import attr
import toml
from voluptuous import All, And, Any, Invalid, MultipleInvalid, Optional, Replace, Required, Schema, Url


def absolute_dir_path(string) -> Path:
    """Make sure the input path string is absolute."""
    path = Path(string)
    if not path.is_absolute():
        path = path.expanduser()
        if not path.is_absolute():
            raise Invalid("path must be absolute (~ allowed)")
    path.mkdir(parents=True, exist_ok=True)
    return path


def gitlab_path(string) -> Path:
    return Path(string)


def string_or_source(value: typing.Union[str, typing.List[str]]) -> str:
    """Requires a literal string, or list of strings describing a command."""
    if isinstance(value, str):
        return value
    return subprocess.run(
        value,
        stderr=sys.stderr,
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    ).stdout.strip()


schema = Schema({
    Required(absolute_dir_path): {
        Required(All("access-token", Replace("-", "_"))): And(
            Any(
                str,
                All([str]),
            ), string_or_source,
        ),
        Required("paths"): [gitlab_path],
        Optional(All("gitlab-url", Replace("-", "_"))): Url(),
    }
})


def find_config() -> Path:
    """Find a config file to use, or raise if none available."""
    environ = "GITLAB_SYNC_CONFIG"
    path = os.environ.get(environ)
    if path:
        path = Path(path)
        if path.is_file():
            return path
        else:
            raise Exception("{} given in {} is not a file".format(path, environ))
    home = Path.home()
    for path in (home / ".config/gitlab-sync.toml", home / ".gitlab-sync.toml"):
        if path.is_file():
            return path
    raise Exception("No config file found")


def load_config(file_: typing.TextIO) -> dict:
    """Load and validate config from a file"""
    try:
        return schema(toml.load(file_))
    except (toml.TomlDecodeError, IOError, FileNotFoundError, TypeError) as e:
        raise Exception("Unable to load config: %s" % e) from e
    except MultipleInvalid as e:
        raise Exception("Config not valid: %s" % e) from e


@attr.s(auto_attribs=True)
class RunConfig:
    base_path: Path
    paths: typing.List[Path]
    access_token: str
    gitlab_url: str = "https://gitlab.com/"


def find_and_load_config() -> typing.List[RunConfig]:
    """Top level method to acquire config for gitlab-sync."""
    data = load_config(find_config().open())
    return {
        path: RunConfig(path, **settings)
        for path, settings in data.items()
    }