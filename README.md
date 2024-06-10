# Trailhead Devcontainer Image

This repository specifies the Docker image and Python requirements.txt for the COMP110 Trailhead system.

More on multi-architecture images: <https://www.docker.com/blog/multi-arch-build-and-images-the-simple-way/>

Prior to building and pushing image, be sure to build the distribution of trailhead from devcontainer using the `build-trailhead` script found in `bin`:

~~~bash
$ build-trailhead
~~~

Command to build and push multi-arch image, replace `TAG` with the version:

~~~bash
export TAG=0.2.0
docker buildx build \
    --push \
    --platform linux/arm64,linux/amd64 \
    --tag krisjordan/trailhead:$TAG \
    --file Dockerfile.students \
    .
~~~
