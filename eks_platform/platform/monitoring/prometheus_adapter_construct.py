from aws_cdk import (
    aws_eks as eks,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

class PrometheusAdapterConstruct(Construct):
    """
    Construct for deploying Prometheus Adapter for custom metrics
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        prometheus_workspace_id: str,
        region: str,
        monitoring_namespace=None,
        compute_mode: str = "auto-mode",
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        

        
        if monitoring_namespace is None:
            self.monitoring_namespace = cluster.add_manifest("MonitoringNamespacePrometheus", {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": "monitoring"
                }
            })
        else:
            self.monitoring_namespace = monitoring_namespace

        # Create service account for Prometheus Adapter in monitoring namespace with AMP permissions
        prometheus_adapter_sa = cluster.add_service_account(
            "prometheus-adapter-sa",
            name="prometheus-adapter",
            namespace="monitoring"
        )
        
        # Add basic AWS permissions for debugging (Prometheus Adapter queries local Prometheus, not AMP)
        prometheus_adapter_sa.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        # Create ClusterRole for Prometheus Adapter
        prometheus_adapter_role = cluster.add_manifest("PrometheusAdapterRole", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {
                "name": "prometheus-adapter"
            },
            "rules": [
                {
                    "apiGroups": ["custom.metrics.k8s.io"],
                    "resources": ["*"],
                    "verbs": ["*"]
                },
                {
                    "apiGroups": [""],
                    "resources": ["nodes", "pods", "services", "configmaps"],
                    "verbs": ["get", "list", "watch"]
                },
                {
                    "apiGroups": ["authorization.k8s.io"],
                    "resources": ["subjectaccessreviews"],
                    "verbs": ["create"]
                },
                {
                    "apiGroups": ["apiregistration.k8s.io"],
                    "resources": ["apiservices"],
                    "verbs": ["get", "list", "watch"]
                },
                {
                    "apiGroups": ["authentication.k8s.io"],
                    "resources": ["tokenreviews"],
                    "verbs": ["create"]
                }
            ]
        })
        
        # Create ClusterRoleBinding for Prometheus Adapter
        prometheus_adapter_binding = cluster.add_manifest("PrometheusAdapterBinding", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "prometheus-adapter"
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "prometheus-adapter"
            },
            "subjects": [{
                "kind": "ServiceAccount",
                "name": "prometheus-adapter",
                "namespace": "monitoring"
            }]
        })
        
        # Create ConfigMap for Prometheus Adapter with compute-mode specific metrics
        prometheus_adapter_config = cluster.add_manifest("PrometheusAdapterConfig", {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "adapter-config",
                "namespace": "monitoring"
            },
            "data": {
                "config.yaml": self._get_adapter_config(compute_mode)
            }
        })
        
        # Create Deployment for Prometheus Adapter
        prometheus_adapter_deployment = cluster.add_manifest("PrometheusAdapterDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "prometheus-adapter",
                "namespace": "monitoring"
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": "prometheus-adapter"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "prometheus-adapter",
                            "app": "prometheus-adapter"
                        }
                    },
                    "spec": {
                        "serviceAccountName": "prometheus-adapter",
                        "tolerations": self._get_tolerations(compute_mode),
                        "containers": [{
                            "name": "prometheus-adapter",
                            "image": "k8s.gcr.io/prometheus-adapter/prometheus-adapter:v0.12.0",
                            "args": [
                                "--cert-dir=/tmp/cert",
                                "--secure-port=6443",
                                "--prometheus-url=http://prometheus-service.monitoring.svc.cluster.local:9090",
                                "--config=/etc/adapter/config.yaml",
                                "--v=4"
                            ],
                            "env": [
                                {"name": "AWS_REGION", "value": region},
                                {"name": "AWS_DEFAULT_REGION", "value": region}
                            ],
                            "ports": [{
                                "containerPort": 6443
                            }],
                            "volumeMounts": [{
                                "name": "config",
                                "mountPath": "/etc/adapter/"
                            }]
                        }],
                        "volumes": [{
                            "name": "config",
                            "configMap": {
                                "name": "adapter-config"
                            }
                        }]
                    }
                }
            }
        })
        
        # Create Service for Prometheus Adapter
        prometheus_adapter_service = cluster.add_manifest("PrometheusAdapterService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "prometheus-adapter",
                "namespace": "monitoring"
            },
            "spec": {
                "ports": [{
                    "name": "https",
                    "port": 443,
                    "targetPort": 6443
                }],
                "selector": {
                    "app": "prometheus-adapter"
                }
            }
        })
        
        # ServiceAccount already created by CDK add_service_account above
        
        # Create APIService for Prometheus Adapter
        prometheus_adapter_apiservice = cluster.add_manifest("PrometheusAdapterAPIService", {
            "apiVersion": "apiregistration.k8s.io/v1",
            "kind": "APIService",
            "metadata": {
                "name": "v1beta1.custom.metrics.k8s.io"
            },
            "spec": {
                "service": {
                    "name": "prometheus-adapter",
                    "namespace": "monitoring"
                },
                "group": "custom.metrics.k8s.io",
                "version": "v1beta1",
                "insecureSkipTLSVerify": True,
                "groupPriorityMinimum": 100,
                "versionPriority": 100
            }
        })
        
        # Add dependencies between manifests (monitoring namespace created by PrometheusConstruct)
        prometheus_adapter_deployment.node.add_dependency(prometheus_adapter_config)
        prometheus_adapter_deployment.node.add_dependency(prometheus_adapter_sa)
        prometheus_adapter_service.node.add_dependency(prometheus_adapter_deployment)
        prometheus_adapter_apiservice.node.add_dependency(prometheus_adapter_service)
        
        # Store references for external dependencies
        self.prometheus_adapter_deployment = prometheus_adapter_deployment
        self.prometheus_adapter_apiservice = prometheus_adapter_apiservice
    
    def _get_tolerations(self, compute_mode: str) -> list:
        """Return appropriate tolerations based on compute mode"""
        if compute_mode == "fargate":
            return [{
                "key": "eks.amazonaws.com/compute-type",
                "operator": "Equal",
                "value": "fargate",
                "effect": "NoSchedule"
            }]
        else:
            return [{
                "key": "eks.amazonaws.com/compute-type",
                "operator": "Equal",
                "value": "prometheus-adapter",
                "effect": "NoSchedule"
            }]
        
        # Add outputs
        CfnOutput(self, "PrometheusAdapterStatus",
            value=f"Prometheus Adapter deployment complete for {compute_mode} mode",
            description=f"Status of the Prometheus Adapter deployment with {compute_mode} metrics configuration"
        )
    
    def _get_adapter_config(self, compute_mode: str) -> str:
        """Return appropriate Prometheus Adapter config based on compute mode"""
        if compute_mode == "fargate":
            return self._get_fargate_config()
        else:
            return self._get_auto_mode_config()
    
    def _get_auto_mode_config(self) -> str:
        """Auto Mode-specific Prometheus Adapter configuration"""
        return """
rules:
# Java OTEL App - using http_requests_total
- seriesQuery: 'http_requests_total{app="java-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "java_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="java-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Go OTEL App - using http_requests_total
- seriesQuery: 'http_requests_total{app="go-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "go_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="go-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Sample Metrics App - using sample_app_requests_total
- seriesQuery: 'sample_app_requests_total{app="sample-metrics-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "sample_app_requests_rate"
  metricsQuery: 'rate(sample_app_requests_total{app="sample-metrics-app",<<.LabelMatchers>>}[1m]) * 60'

# OTEL Sample App - using pod_cpu_utilization
- seriesQuery: 'pod_cpu_utilization{app="otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "pod_cpu_utilization"
  metricsQuery: 'pod_cpu_utilization{app="otel-sample-app",<<.LabelMatchers>>}'
"""
    
    def _get_fargate_config(self) -> str:
        """Fargate-specific Prometheus Adapter configuration"""
        return """
rules:
# Java OTEL App - Fargate (same as auto-mode, metrics don't have compute_type label)
- seriesQuery: 'http_requests_total{app="java-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "java_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="java-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Go OTEL App - Fargate
- seriesQuery: 'http_requests_total{app="go-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "go_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="go-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Sample Metrics App - Fargate
- seriesQuery: 'sample_app_requests_total{app="sample-metrics-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "sample_app_requests_rate"
  metricsQuery: 'rate(sample_app_requests_total{app="sample-metrics-app",<<.LabelMatchers>>}[1m]) * 60'

# OTEL Sample App - Fargate CPU utilization
- seriesQuery: 'pod_cpu_utilization{app="otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "pod_cpu_utilization"
  metricsQuery: 'pod_cpu_utilization{app="otel-sample-app",<<.LabelMatchers>>}'
"""