#!/usr/bin/env python3
#
# This script is using plain "docker buildx build" functionality
# to build multi-architecture docker images
# of selected `docker-compose` services and load the image
# into current docker instance.
#
# Usage:
#   buildx.py [--help] <SERVICE>
#
import argparse
import dataclasses
import json
import logging
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Union

logger = logging.getLogger()


class Architecture(Enum):
    LINUX_ARM64 = "linux/arm64"
    LINUX_AMD64 = "linux/amd64"

    def is_current_architecture(self):
        return self.value.split("/")[1] == platform.machine()


@dataclass
class BuildArg:
    name: str
    value: str

    @classmethod
    def from_dict(cls, **kwargs):
        fields = dataclasses.fields(cls)
        field_names = [f.name for f in fields]
        for k, v in list(kwargs.items()):
            if k not in field_names:
                kwargs.pop(k)
        return cls(**kwargs)


@dataclass
class ServiceBuild:
    dockerfile: str = "Dockerfile"
    context: str = "."
    args: Optional[List[BuildArg]] = None
    ssh: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, **kwargs):
        fields = dataclasses.fields(cls)
        field_names = [f.name for f in fields]
        for k, v in list(kwargs.items()):
            if k not in field_names:
                kwargs.pop(k)
        if "args" in kwargs:
            kwargs["args"] = [BuildArg(name=k, value=v) for k, v in kwargs["args"].items()]
        return cls(**kwargs)


@dataclass
class Service:
    name: str
    image: str = None
    build: Optional[ServiceBuild] = None

    def build_image(self,
                    architecture: Architecture,
                    tags: Optional[Union[str, List[str]]] = None,
                    target: Optional[str] = None,
                    ignore_errors: bool = False):
        if not self.build:
            return
        buildx_image(self.name,
                     architecture,
                     tags=tags,
                     ssh=service.build.ssh,
                     build_args=self.build.args,
                     dockerfile_path=Path(self.build.dockerfile),
                     context_path=Path(self.build.context),
                     target=target,
                     ignore_errors=ignore_errors)

    @classmethod
    def from_dict(cls, **kwargs):
        fields = dataclasses.fields(cls)
        field_names = [f.name for f in fields]
        for k, v in list(kwargs.items()):
            if k not in field_names:
                kwargs.pop(k)
        if "build" in kwargs:
            kwargs["build"] = ServiceBuild.from_dict(**kwargs["build"])
        return cls(**kwargs)


class ComposeConfig:
    def __init__(self):
        config_json = subprocess.check_output(["docker-compose", "config", "--format", "json"])
        self._config = json.loads(config_json)

    def service_names(self):
        return list(self._config["services"].keys())

    def get_service(self, name) -> Service:
        service_config = self._config["services"].get(name)
        if not service_config:
            raise Exception(f"Service {name} not found in docker-compose config")
        return Service.from_dict(name=name, **service_config)


def build_heading(msg):
    msg_len = max([len(t) for t in msg.split("\n")])
    return "=" * msg_len


def build_args_message(args):
    msg_args = ""
    for a in args:
        sep = ""
        if msg_args:
            if a.startswith("-"):
                sep = "\n\t"
            else:
                sep = " "
        msg_args += sep + a
    return msg_args


def buildx_image(name: str,
                 architecture: Architecture,
                 tags: Optional[Union[str, List[str]]],
                 ssh: Optional[List[str]],
                 build_args: Optional[List[BuildArg]],
                 dockerfile_path: Path = None,
                 context_path: Path = None,
                 target: str = None,
                 ignore_errors: bool = False):
    build_args = build_args or []
    tags = tags or []
    if isinstance(tags, str):
        tags = [tags]
    ssh = ssh or []
    dockerfile_path = dockerfile_path or Path(".")
    args = ["docker", "buildx", "build", "--platform", architecture.value]
    if architecture.is_current_architecture():
        args += ["--load"]
    for build_arg in build_args:
        args += ["--build-arg", f"{build_arg.name}={build_arg.value}"]
    for tag in tags:
        args += ["--tag", tag]
    if target:
        args += ["--target", target]
    for s in ssh:
        args += ["--ssh", s]

    if dockerfile_path:
        if not dockerfile_path.is_absolute():
            dockerfile_path = context_path / dockerfile_path
        args += ["-f", dockerfile_path.absolute().as_posix()]
    args += [context_path.absolute().as_posix()]

    msg = f"Building {name} {architecture.value} image"
    logger.info(build_heading(msg))
    logger.info(msg)
    logger.debug(build_args_message(args))
    logger.info(build_heading(msg))

    exitcode = subprocess.call(args)
    if exitcode:
        msg = f"Docker build failed for {name} {architecture.value} image !"
        logger.error(build_heading(msg))
        logger.error(msg)
        logger.error(build_args_message(args))
        if not ignore_errors:
            sys.exit(1)


def setup_logging(verbose: bool):
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Docker Compose 'buildx' Helper")
    parser.add_argument("services", metavar="SRV", type=str, nargs="*",
                        help="Services to be build")
    parser.add_argument("--all-arch", dest="all_architectures", action="store_const",
                        const=True, default=False,
                        help=f"Build for all architectures, not just for {platform.machine()}")
    parser.add_argument("--verbose", dest="verbose", action="store_const",
                        const=True, default=False,
                        help=f"Be more verbose")
    parser.add_argument("--ignore-errors", dest="ignore_errors", action="store_const",
                        const=True, default=False,
                        help=f"Continue building even on errors")
    parser.add_argument("--target", dest="target", default=None,
                        help="Just build selected target stage of Dockerfile")
    parser.add_argument("--tag", dest="tag", default=None,
                        help="Use given tag instead of the image/tag configured by docker compose")
    parser.add_argument("--no-cache", dest="no_cache", action="store_const",
                        const=True, default=False,
                        help="Don't use previously cached layers while building")
    cli_args = parser.parse_args()

    setup_logging(cli_args.verbose)

    if cli_args.all_architectures:
        build_architectures = list(Architecture)
    else:
        build_architectures = [a for a in Architecture if a.is_current_architecture()]

    config = ComposeConfig()
    if cli_args.services:
        service_names = cli_args.services
    else:
        service_names = config.service_names()
    services = [config.get_service(s) for s in service_names]

    if services and (cli_args.tag or cli_args.target):
        logger.warning("Using --tag or --target likely only makes sense when building just one service !")

    for service in services:
        for arch in build_architectures:
            service.build_image(arch,
                                tags=cli_args.tag or service.image,
                                target=cli_args.target,
                                ignore_errors=cli_args.ignore_errors)
