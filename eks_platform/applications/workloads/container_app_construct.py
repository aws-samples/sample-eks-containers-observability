from aws_cdk import (
    aws_ecr as ecr,
    aws_eks as eks,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
from typing import Dict, Any, List, Optional

class ContainerAppConstruct(Construct):
    """
    Reusable construct for containerized applications
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        app_name: str,
        repository_name: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Use provided repository name or default to app name
        repo_name = repository_name or app_name
        
        # Create ECR repository for the application
        self.repository = ecr.Repository(
            self, 
            f"{app_name.replace('-', '')}Repo",
            repository_name=repo_name,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True  # Use this instead of deprecated autoDeleteImages
        )
        
        # Store the repository URI for use in deployments
        self.repository_uri = self.repository.repository_uri
        
        # Output the repository URI
        CfnOutput(
            self,
            f"{app_name.replace('-', '')}RepoUri",
            value=self.repository_uri,
            description=f"ECR Repository URI for {app_name}"
        )
    
    def create_deployment_manifest(
        self,
        namespace: str = "default",
        replicas: int = 2,
        container_port: int = 8080,
        resources: Dict[str, Dict[str, str]] = None,
        env_vars: List[Dict[str, Any]] = None,
        annotations: Dict[str, str] = None,
        labels: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Create a Kubernetes deployment manifest for the application
        """
        # Default resources if none provided
        if resources is None:
            resources = {
                "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                },
                "limits": {
                    "cpu": "200m",
                    "memory": "256Mi"
                }
            }
        
        # Default environment variables if none provided
        if env_vars is None:
            env_vars = []
        
        # Default annotations if none provided
        if annotations is None:
            annotations = {
                "prometheus.io/scrape": "true",
                "prometheus.io/port": str(container_port)
            }
        
        # Default labels if none provided
        if labels is None:
            labels = {
                "app": self.node.id.lower()
            }
        
        # Create the deployment manifest
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.node.id.lower(),
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {
                        "app": self.node.id.lower()
                    }
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": annotations
                    },
                    "spec": {
                        "containers": [{
                            "name": self.node.id.lower(),
                            "image": f"{self.repository_uri}:latest",
                            "ports": [{
                                "containerPort": container_port
                            }],
                            "env": env_vars,
                            "resources": resources
                        }]
                    }
                }
            }
        }
    
    def create_service_manifest(
        self,
        namespace: str = "default",
        port: int = 80,
        target_port: int = 8080,
        service_type: str = "ClusterIP"
    ) -> Dict[str, Any]:
        """
        Create a Kubernetes service manifest for the application
        """
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.node.id.lower(),
                "namespace": namespace,
                "labels": {
                    "app": self.node.id.lower()
                }
            },
            "spec": {
                "type": service_type,
                "ports": [{
                    "port": port,
                    "targetPort": target_port,
                    "protocol": "TCP"
                }],
                "selector": {
                    "app": self.node.id.lower()
                }
            }
        }