# docker-compose-buildx

This script is using plain `docker buildx build` functionality
to build multi-architecture docker images of selected
`docker-compose` services and load them into current docker instance.

## Usage

Current working directory should be where your `docker-compose.yaml`
configuration is located.

Run `buildx.py my-service` to just build "my-service" for current architecture.

Run `buildx.py --all-arch my-service` to just build "my-service" for
`linux/amd64` & `linux/arm64` architecture.

Run `buildx.py --help` to get commandline help.

## Why ?

The original docker functionality from
[bake](https://github.com/docker/buildx/blob/master/docs/reference/buildx_bake.md)
command seems to lack functionality related to `services.<SERVICE>.build.ssh`
from a docker-compose configuration.
