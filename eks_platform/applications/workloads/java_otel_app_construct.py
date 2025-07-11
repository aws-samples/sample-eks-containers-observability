from aws_cdk import (
    aws_eks as eks,
    CfnOutput
)
from constructs import Construct

class JavaOtelAppConstruct(Construct):
    """
    Construct for the Java OpenTelemetry sample application
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
        self.compute_config = compute_config
        
        # Create Deployment for Java OTEL sample app
        app_deployment = cluster.add_manifest("JavaOtelSampleAppDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "java-otel-sample-app",
                "namespace": "default",
                "labels": {
                    "app": "java-otel-sample-app"
                }
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "java-otel-sample-app"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": self._get_pod_labels(),
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": "8080",
                            "prometheus.io/path": "/actuator/prometheus",
                            "prometheus.io/scheme": "http"
                        }
                    },
                    "spec": {
                        **self._get_pod_spec(),
                        "containers": [{
                            "name": "java-otel-sample-app",
                            "image": f"{repository_uri}:latest",
                            "ports": [
                                {"containerPort": 8080, "name": "http"}
                            ],
                            "env": [
                                {"name": "OTEL_EXPORTER_OTLP_ENDPOINT", 
                                 "value": "http://otel-collector.opentelemetry:4317"},
                                {"name": "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", 
                                 "value": "http://otel-collector.opentelemetry:4317"},
                                {"name": "OTEL_SERVICE_NAME", "value": "java-otel-sample-app"},
                                {"name": "OTEL_RESOURCE_ATTRIBUTES", "value": "service.name=java-otel-sample-app,service.version=1.0.0,deployment.environment=production"},
                                {"name": "OTEL_LOGS_EXPORTER", "value": "otlp"},
                                {"name": "AWS_REGION", "value": region},
                                {"name": "PROMETHEUS_WORKSPACE_ID", "value": prometheus_workspace_id},
                                {"name": "ENVIRONMENT", "value": "production"}
                            ],
                            "resources": {
                                "requests": {
                                    "memory": "256Mi",
                                    "cpu": "200m"
                                },
                                "limits": {
                                    "memory": "512Mi",
                                    "cpu": "400m"
                                }
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8080
                                },
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10
                            },
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8080
                                },
                                "initialDelaySeconds": 60,
                                "periodSeconds": 15
                            }
                        }]
                    }
                }
            }
        })
        
        # Create Service for Java OTEL sample app
        app_service = cluster.add_manifest("JavaOtelSampleAppService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "java-otel-sample-app",
                "namespace": "default"
            },
            "spec": {
                "selector": {
                    "app": "java-otel-sample-app"
                },
                "ports": [
                    {"port": 8080, "targetPort": 8080, "name": "http"}
                ]
            }
        })
        app_service.node.add_dependency(app_deployment)
        
        # Create HPA for Java OTEL sample app
        java_hpa = cluster.add_manifest("JavaOtelSampleAppHPA", {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "java-otel-sample-app-hpa",
                "namespace": "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "java-otel-sample-app"
                },
                "minReplicas": 1,
                "maxReplicas": 4,
                "metrics": [
                    {
                        "type": "Pods",
                        "pods": {
                            "metric": {"name": "java_app_requests_rate"},
                            "target": {"type": "AverageValue", "averageValue": "10"}
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
        java_hpa.node.add_dependency(app_deployment)
        
        # Store reference for external dependencies
        self.java_hpa = java_hpa
    
    def _get_pod_labels(self) -> dict:
        """Get pod labels based on compute mode"""
        labels = {"app": "java-otel-sample-app"}
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
        
        # Add outputs
        CfnOutput(self, "JavaOtelSampleAppUrl",
            value=f"http://java-otel-sample-app.default:8080",
            description="URL for the Java OpenTelemetry sample app"
        )