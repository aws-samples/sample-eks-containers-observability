from aws_cdk import (
    aws_eks as eks,
    CfnOutput
)
from constructs import Construct

class GoOtelAppConstruct(Construct):
    """
    Construct for the Go OpenTelemetry sample application
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        repository_uri: str,
        region: str,
        prometheus_workspace_id: str,
        compute_config=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.compute_config = compute_config
        
        # Create Deployment for Go OTEL app
        app_deployment = cluster.add_manifest("GoOtelAppDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "go-otel-sample-app",
                "namespace": "default",
                "labels": {
                    "app": "go-otel-sample-app"
                }
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "go-otel-sample-app"
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
                            "name": "go-otel-sample-app",
                            "image": f"{repository_uri}:latest",
                            "ports": [
                                {"containerPort": 8080, "name": "http"}
                            ],
                            "env": [
                                {
                                    "name": "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                                    "value": "otel-collector.opentelemetry:4317"
                                },
                                {
                                    "name": "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", 
                                    "value": "otel-collector.opentelemetry:4317"
                                },
                                {
                                    "name": "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", 
                                    "value": "otel-collector.opentelemetry:4317"
                                },
                                {
                                    "name": "AWS_REGION",
                                    "value": region
                                },
                                {
                                    "name": "PROMETHEUS_WORKSPACE_ID",
                                    "value": prometheus_workspace_id
                                },
                                {
                                    "name": "ENVIRONMENT",
                                    "value": "production"
                                }
                            ],
                            "resources": {
                                "requests": {
                                    "memory": "64Mi",
                                    "cpu": "50m"
                                },
                                "limits": {
                                    "memory": "128Mi",
                                    "cpu": "100m"
                                }
                            },
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8080
                                },
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8080
                                },
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5
                            }
                        }]
                    }
                }
            }
        })
        
        # Create Service for Go OTEL app
        app_service = cluster.add_manifest("GoOtelAppService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "go-otel-sample-app",
                "namespace": "default"
            },
            "spec": {
                "selector": {
                    "app": "go-otel-sample-app"
                },
                "ports": [
                    {"port": 8080, "targetPort": 8080, "name": "http"}
                ]
            }
        })
        app_service.node.add_dependency(app_deployment)
        
        # Create HPA for Go OTEL app
        go_hpa = cluster.add_manifest("GoOtelAppHPA", {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "go-otel-sample-app-hpa",
                "namespace": "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "go-otel-sample-app"
                },
                "minReplicas": 2,
                "maxReplicas": 6,
                "metrics": [
                    {
                        "type": "Pods",
                        "pods": {
                            "metric": {
                                "name": "go_app_requests_rate"
                            },
                            "target": {
                                "type": "AverageValue",
                                "averageValue": "10"
                            }
                        }
                    }
                ],
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
        go_hpa.node.add_dependency(app_deployment)
        
        # Store reference for external dependencies
        self.go_hpa = go_hpa
    
    def _get_pod_labels(self) -> dict:
        """Get pod labels based on compute mode"""
        labels = {"app": "go-otel-sample-app"}
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