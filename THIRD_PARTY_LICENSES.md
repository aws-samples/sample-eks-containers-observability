# Third-Party Licenses

This document lists the third-party components used in this project and their respective licenses.

## Images and Diagrams

All architecture diagrams and dashboard screenshots in this repository are original works created for this project and are licensed under the same MIT-0 license as the rest of the project.

## Binary Files

### kubectl

- **Source**: https://kubernetes.io/docs/tasks/tools/
- **License**: Apache License 2.0
- **Usage**: Used for Kubernetes cluster management
- **Note**: The binary is not included in the repository. It is downloaded during deployment.

## Third-Party Libraries

This project uses various third-party libraries through package managers (npm, pip). These dependencies are declared in the respective package files:

- `package.json` for Node.js dependencies
- `requirements.txt` for Python dependencies
- `pom.xml` for Java dependencies
- `go.mod` for Go dependencies

Users should install these dependencies using the appropriate package manager, which will download the libraries from their official sources with their respective licenses.

## Docker Images

The Dockerfiles in this repository are used to build container images for demonstration purposes. Users are responsible for complying with the licenses of any base images specified in the Dockerfiles when building and distributing container images.