from aws_cdk import (
    aws_eks as eks,
    CfnOutput
)
from constructs import Construct
from typing import Dict, Any, List

class DeploymentConstruct(Construct):
    """
    Reusable construct for deploying applications to EKS
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.cluster = cluster
        self.manifests = []
    
    def add_namespace(self, name: str, labels: Dict[str, str] = None) -> eks.KubernetesManifest:
        """
        Add a namespace to the cluster
        """
        if labels is None:
            labels = {"name": name}
        
        manifest = self.cluster.add_manifest(
            f"{name.replace('-', '')}Namespace",
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": name,
                    "labels": labels
                }
            }
        )
        
        self.manifests.append(manifest)
        return manifest
    
    def add_deployment(
        self, 
        name: str, 
        manifest: Dict[str, Any],
        dependencies: List[eks.KubernetesManifest] = None
    ) -> eks.KubernetesManifest:
        """
        Add a deployment to the cluster
        """
        deployment = self.cluster.add_manifest(
            f"{name.replace('-', '')}Deployment",
            manifest
        )
        
        # Add dependencies if provided
        if dependencies:
            for dependency in dependencies:
                deployment.node.add_dependency(dependency)
        
        self.manifests.append(deployment)
        return deployment
    
    def add_service(
        self, 
        name: str, 
        manifest: Dict[str, Any],
        dependencies: List[eks.KubernetesManifest] = None
    ) -> eks.KubernetesManifest:
        """
        Add a service to the cluster
        """
        service = self.cluster.add_manifest(
            f"{name.replace('-', '')}Service",
            manifest
        )
        
        # Add dependencies if provided
        if dependencies:
            for dependency in dependencies:
                service.node.add_dependency(dependency)
        
        self.manifests.append(service)
        return service
    
    def add_config_map(
        self, 
        name: str, 
        namespace: str,
        data: Dict[str, str],
        dependencies: List[eks.KubernetesManifest] = None
    ) -> eks.KubernetesManifest:
        """
        Add a config map to the cluster
        """
        config_map = self.cluster.add_manifest(
            f"{name.replace('-', '')}ConfigMap",
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": name,
                    "namespace": namespace
                },
                "data": data
            }
        )
        
        # Add dependencies if provided
        if dependencies:
            for dependency in dependencies:
                config_map.node.add_dependency(dependency)
        
        self.manifests.append(config_map)
        return config_map
    
    def add_horizontal_pod_autoscaler(
        self,
        name: str,
        namespace: str,
        target_name: str,
        min_replicas: int = 2,
        max_replicas: int = 4,
        metrics: List[Dict[str, Any]] = None,
        dependencies: List[eks.KubernetesManifest] = None
    ) -> eks.KubernetesManifest:
        """
        Add a horizontal pod autoscaler to the cluster
        """
        # Default metrics if none provided
        if metrics is None:
            metrics = [{
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": 80
                    }
                }
            }]
        
        hpa = self.cluster.add_manifest(
            f"{name.replace('-', '')}HPA",
            {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {
                    "name": name,
                    "namespace": namespace
                },
                "spec": {
                    "scaleTargetRef": {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": target_name
                    },
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                    "metrics": metrics,
                    "behavior": {
                        "scaleUp": {
                            "stabilizationWindowSeconds": 60,
                            "policies": [{
                                "type": "Percent",
                                "value": 100,
                                "periodSeconds": 15
                            }]
                        },
                        "scaleDown": {
                            "stabilizationWindowSeconds": 300,
                            "policies": [{
                                "type": "Percent",
                                "value": 10,
                                "periodSeconds": 60
                            }]
                        }
                    }
                }
            }
        )
        
        # Add dependencies if provided
        if dependencies:
            for dependency in dependencies:
                hpa.node.add_dependency(dependency)
        
        self.manifests.append(hpa)
        return hpa