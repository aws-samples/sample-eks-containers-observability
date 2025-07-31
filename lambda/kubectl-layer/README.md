# Kubectl Lambda Layer

This directory contains the configuration for creating an AWS Lambda Layer that includes the kubectl binary.

## Usage

Instead of including the kubectl binary directly in the repository, we use the `download-kubectl.sh` script to download it during deployment. This approach:

1. Avoids storing binary files in the repository
2. Ensures you always get the specified version of kubectl
3. Automatically selects the correct binary for your operating system and architecture

## Deployment

To prepare the layer:

1. Run the download script:
   ```bash
   ./download-kubectl.sh
   ```

2. The script will download the kubectl binary to the `bin` directory and make it executable.

3. The CDK code will package this directory as a Lambda Layer.

## Version

The script is configured to download kubectl version v1.28.0 by default. You can modify the `KUBECTL_VERSION` variable in the script if you need a different version.