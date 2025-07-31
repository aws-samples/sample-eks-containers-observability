from aws_cdk import (
    aws_eks as eks,
    CfnOutput
)
from constructs import Construct

class SampleAppConstruct(Construct):
    """
    Construct for the sample metrics application
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        repository_uri: str,
        compute_config=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.compute_config = compute_config
        
        # Create Deployment for sample metrics app
        app_deployment = cluster.add_manifest("SampleMetricsAppDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "sample-metrics-app",
                "namespace": "default",
                "labels": {
                    "app": "sample-metrics-app"
                }
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "sample-metrics-app"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": self._get_pod_labels(),
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": "8080",
                            "prometheus.io/path": "/metrics"
                        }
                    },
                    "spec": {
                        **self._get_pod_spec(),
                        "containers": [{
                            "name": "sample-metrics-app",
                            "image": f"{repository_uri}:latest",
                            "ports": [
                                {"containerPort": 8000, "name": "http"},
                                {"containerPort": 8080, "name": "metrics"}
                            ],
                            "resources": {
                                "requests": {
                                    "memory": "128Mi",
                                    "cpu": "100m"
                                },
                                "limits": {
                                    "memory": "256Mi",
                                    "cpu": "200m"
                                }
                            }
                        }]
                    }
                }
            }
        })
        
        # Create Service for sample metrics app
        app_service = cluster.add_manifest("SampleMetricsAppService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "sample-metrics-app",
                "namespace": "default"
            },
            "spec": {
                "selector": {
                    "app": "sample-metrics-app"
                },
                "ports": [
                    {"port": 8000, "targetPort": 8000, "name": "http"},
                    {"port": 8080, "targetPort": 8080, "name": "metrics"}
                ]
            }
        })
        app_service.node.add_dependency(app_deployment)
        
        # Create HPA for sample-metrics-app
        sample_hpa = cluster.add_manifest("SampleMetricsAppHPA", {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "sample-metrics-app-hpa",
                "namespace": "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "sample-metrics-app"
                },
                "minReplicas": 2,
                "maxReplicas": 4,
                "metrics": [{
                    "type": "Pods",
                    "pods": {
                        "metric": {
                            "name": "sample_app_requests_rate"
                        },
                        "target": {
                            "type": "AverageValue",
                            "averageValue": "10"
                        }
                    }
                }],
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
        })
        sample_hpa.node.add_dependency(app_deployment)
        
        # Store reference for external dependencies
        self.sample_hpa = sample_hpa
    
    def _get_pod_labels(self) -> dict:
        """Get pod labels based on compute mode"""
        labels = {"app": "sample-metrics-app"}
        if self.compute_config and self.compute_config.mode == "fargate":
            labels["compute-type"] = "fargate"
        return labels
    
    def _get_pod_spec(self) -> dict:
        """Get pod spec based on compute mode"""
        if self.compute_config and self.compute_config.mode == "fargate":
            return {
                "nodeSelector": {"eks.amazonaws.com/compute-type": "fargate"},
                "tolerations": [{
                    "key": "eks.amazonaws.com/compute-type",
                    "operator": "Equal",
                    "value": "fargate",
                    "effect": "NoSchedule"
                }]
            }
        return {}