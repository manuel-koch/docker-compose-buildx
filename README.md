# docker-compose-buildx

This script is using plain `docker buildx build` functionality
to build multi-architecture docker images of selected
`docker-compose` services and load them into current docker instance.

## Why ?

The original docker functionality from
[bake](https://github.com/docker/buildx/blob/master/docs/reference/buildx_bake.md)
command seems to lack functionality related to `services.<SERVICE>.build.ssh`
from a docker-compose configuration.
