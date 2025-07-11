from aws_cdk import (
    aws_ecr as ecr,
    aws_eks as eks,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct

class OtelAppConstruct(Construct):
    """
    Construct for the OpenTelemetry sample application
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        repository_uri: str,
        region: str,
        prometheus_workspace_id: str,
        opentelemetry_namespace=None,
        compute_config=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.compute_config = compute_config
        
        # Use pre-created opentelemetry namespace
        namespace = None  # Will be created in app.py
        
        # Create service account for the ADOT collector
        adot_role_arn = f"arn:aws:iam::{scope.account}:role/EKS-ADOT-PrometheusRemoteWrite-EksClusterStack"
        service_account = cluster.add_manifest("OtelCollectorSA", {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "otel-collector-sa",
                "namespace": "opentelemetry",
                "annotations": {
                    "eks.amazonaws.com/role-arn": adot_role_arn,
                    "eks.amazonaws.com/sts-regional-endpoints": "true"
                }
            }
        })
        service_account.node.add_dependency(opentelemetry_namespace)
        
        # Create ClusterRole for ADOT collector
        cluster_role = cluster.add_manifest("OtelCollectorRole", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {
                "name": "otel-collector-role"
            },
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["pods", "nodes", "namespaces"],
                    "verbs": ["get", "watch", "list"]
                }
            ]
        })
        
        # Create ClusterRoleBinding for ADOT collector
        cluster_role_binding = cluster.add_manifest("OtelCollectorRoleBinding", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "otel-collector-role-binding"
            },
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": "otel-collector-sa",
                    "namespace": "opentelemetry"
                }
            ],
            "roleRef": {
                "kind": "ClusterRole",
                "name": "otel-collector-role",
                "apiGroup": "rbac.authorization.k8s.io"
            }
        })
        cluster_role_binding.node.add_dependency(cluster_role)
        cluster_role_binding.node.add_dependency(service_account)
        
        # Create ConfigMap for ADOT collector with complete backup config
        collector_config = cluster.add_manifest("OtelCollectorConfig", {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "otel-collector-conf",
                "namespace": "opentelemetry"
            },
            "data": {
                "collector.yaml": f"""receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      global:
        scrape_interval: 15s
        evaluation_interval: 15s
      scrape_configs:
        - job_name: 'otel-collector'
          static_configs:
            - targets: ['localhost:8888']
        - job_name: 'kubernetes-pods'
          kubernetes_sd_configs:
            - role: pod
          relabel_configs:
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
              action: keep
              regex: true
            - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
              action: replace
              target_label: __metrics_path__
              regex: (.+)
            - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
              action: replace
              regex: ([^:]+)(?:\\\\d+)?;(\\\\d+)
              replacement: $1:$2
              target_label: __address__
            - action: labelmap
              regex: __meta_kubernetes_pod_label_(.+)
            - source_labels: [__meta_kubernetes_namespace]
              action: replace
              target_label: kubernetes_namespace
            - source_labels: [__meta_kubernetes_pod_name]
              action: replace
              target_label: kubernetes_pod_name

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  resource:
    attributes:

      - action: insert
        key: service.namespace
        value: "default"
      - action: insert
        key: deployment.environment
        value: "test"
      - action: insert
        key: ClusterName
        value: "{cluster.cluster_name}"
      - action: insert
        key: aws.ecs.cluster.name
        value: "{cluster.cluster_name}"
      - action: insert
        key: aws.ecs.task.family
        value: "otel-collector"
  filter:
    metrics:
      include:
        match_type: regexp
        metric_names:
          - pod_cpu_utilization
          - pod_memory_utilization
          - pod_network_rx_bytes
          - pod_network_tx_bytes
          - pod_cpu_utilization_over_pod_limit
          - pod_memory_utilization_over_pod_limit
          - container_cpu_utilization
          - container_memory_utilization
          - container_cpu_limit
          - container_memory_limit
          - service_number_of_running_pods
          - otel_sample_app_.*

exporters:
  awsxray:
    region: {region}
  awsemf:
    region: {region}
    namespace: ContainerInsights
    log_group_name: /aws/eks/automode-platform/otel
    dimension_rollup_option: NoDimensionRollup
    parse_json_encoded_attr_values: ["Sources", "kubernetes"]
    metric_declarations:
      - dimensions: [[ClusterName], [ClusterName, Namespace], [ClusterName, Namespace, PodName]]
        metric_name_selectors:
          - pod_cpu_utilization
          - pod_memory_utilization
          - pod_network_rx_bytes
          - pod_network_tx_bytes
          - pod_cpu_utilization_over_pod_limit
          - pod_memory_utilization_over_pod_limit
      - dimensions: [[ClusterName], [ClusterName, Namespace], [ClusterName, Namespace, Service]]
        metric_name_selectors:
          - service_number_of_running_pods
      - dimensions: [[ClusterName, Namespace, PodName], [ClusterName, Namespace, PodName, ContainerName]]
        metric_name_selectors:
          - container_cpu_utilization
          - container_memory_utilization
          - container_cpu_limit
          - container_memory_limit
      - dimensions: [[endpoint]]
        metric_name_selectors:
          - "otel_sample_app_*"
      - dimensions: [[service.name, service.namespace]]
        metric_name_selectors:
          - ".*"
    output_destination: logs
  prometheusremotewrite:
    endpoint: https://aps-workspaces.{region}.amazonaws.com/workspaces/{prometheus_workspace_id}/api/v1/remote_write
    auth:
      authenticator: sigv4auth
    resource_to_telemetry_conversion:
      enabled: true
    namespace: otel_sample_app
    add_metric_suffixes: false
  debug:
    verbosity: detailed
  awscloudwatchlogs:
    region: {region}
    log_group_name: "/aws/eks/automode-platform/applications"
    log_stream_name: "otel-collector-logs"

extensions:
  health_check:
    endpoint: 0.0.0.0:13133
  sigv4auth:
    region: {region}
    service: "aps"

service:
  extensions: [health_check, sigv4auth]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [awsxray, debug]
    metrics:
      receivers: [otlp, prometheus]
      processors: [batch, filter, resource]
      exporters: [prometheusremotewrite, awsemf, debug]
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [awscloudwatchlogs, debug]
"""
            }
        })
        collector_config.node.add_dependency(opentelemetry_namespace)
        
        # Create Deployment for ADOT collector with complete env vars
        collector_deployment = cluster.add_manifest("OtelCollectorDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "otel-collector",
                "namespace": "opentelemetry",
                "labels": {
                    "app": "otel-collector"
                }
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": "otel-collector"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "otel-collector"
                        }
                    },
                    "spec": {
                        "serviceAccountName": "otel-collector-sa",
                        "containers": [{
                            "name": "otel-collector",
                            "image": "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3",
                            "command": [
                                "/awscollector"
                            ],
                            "args": [
                                "--config=/conf/collector.yaml"
                            ],
                            "volumeMounts": [{
                                "name": "otel-collector-config-volume",
                                "mountPath": "/conf"
                            }],
                            "ports": [
                                {"containerPort": 4317},
                                {"containerPort": 4318},
                                {"containerPort": 13133},
                                {"containerPort": 8888, "name": "metrics"}
                            ],
                            "env": [
                                {"name": "AWS_REGION", "value": region},
                                {"name": "AWS_STS_REGIONAL_ENDPOINTS", "value": "regional"},
                                {"name": "OTEL_METRICS_EXPORTER", "value": "prometheus"},
                                {"name": "OTEL_EXPORTER_OTLP_ENDPOINT", "value": "http://localhost:4317"},
                                {"name": "METRICS_EXPOSITION_PORT", "value": "8888"},
                                {"name": "METRICS_EXPOSITION_HOST", "value": "0.0.0.0"},
                                {"name": "K8S_NODE_NAME", "valueFrom": {"fieldRef": {"fieldPath": "spec.nodeName"}}},
                                {"name": "K8S_POD_NAME", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
                                {"name": "K8S_NAMESPACE", "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}}},
                                {"name": "HOST_IP", "valueFrom": {"fieldRef": {"fieldPath": "status.hostIP"}}},
                                {"name": "HOST_NAME", "valueFrom": {"fieldRef": {"fieldPath": "spec.nodeName"}}},
                                {"name": "K8S_CLUSTER_NAME", "value": cluster.cluster_name}
                            ],
                            "resources": {
                                "limits": {
                                    "cpu": "200m",
                                    "memory": "400Mi"
                                },
                                "requests": {
                                    "cpu": "100m",
                                    "memory": "200Mi"
                                }
                            }
                        }],
                        "volumes": [{
                            "name": "otel-collector-config-volume",
                            "configMap": {
                                "name": "otel-collector-conf"
                            }
                        }]
                    }
                }
            }
        })
        collector_deployment.node.add_dependency(collector_config)
        collector_deployment.node.add_dependency(cluster_role_binding)
        
        # Create Service for ADOT collector
        collector_service = cluster.add_manifest("OtelCollectorService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "otel-collector",
                "namespace": "opentelemetry"
            },
            "spec": {
                "selector": {
                    "app": "otel-collector"
                },
                "ports": [
                    {"name": "otlp-grpc", "port": 4317, "targetPort": 4317},
                    {"name": "otlp-http", "port": 4318, "targetPort": 4318},
                    {"name": "health-check", "port": 13133, "targetPort": 13133},
                    {"name": "metrics", "port": 8888, "targetPort": 8888}
                ]
            }
        })
        collector_service.node.add_dependency(collector_deployment)
        
        # Create Deployment for sample app
        app_deployment = cluster.add_manifest("OtelSampleAppDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "otel-sample-app",
                "namespace": "default",
                "labels": {
                    "app": "otel-sample-app"
                }
            },
            "spec": {
                "replicas": 2,
                "selector": {
                    "matchLabels": {
                        "app": "otel-sample-app"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": self._get_pod_labels(),
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": "8080",
                            "prometheus.io/path": "/metrics",
                            "prometheus.io/scheme": "http",
                            "container.insights/collect": "true"
                        }
                    },
                    "spec": {
                        **self._get_pod_spec(),
                        "containers": [{
                            "name": "otel-sample-app",
                            "image": f"{repository_uri}:latest",
                            "ports": [
                                {"containerPort": 8000, "name": "http"},
                                {"containerPort": 8080, "name": "metrics"}
                            ],
                            "env": [
                                {"name": "AWS_REGION", "value": region},
                                {"name": "OTEL_SERVICE_NAME", "value": "otel_sample_app"},
                                {"name": "OTEL_EXPORTER_OTLP_ENDPOINT", "value": "http://otel-collector.opentelemetry:4317"},
                                {"name": "OTEL_RESOURCE_ATTRIBUTES", "value": f"service.name=otel_sample_app,service.namespace=default,deployment.environment=test,aws.region={region},ClusterName={cluster.cluster_name},Namespace=default,PodName=$(HOSTNAME)"},
                                {"name": "OTEL_METRICS_EXPORTER", "value": "otlp"},
                                {"name": "OTEL_EXPORTER_OTLP_PROTOCOL", "value": "grpc"},
                                {"name": "CLUSTER_NAME", "value": cluster.cluster_name}
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
                            },
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8000
                                },
                                "initialDelaySeconds": 10,
                                "periodSeconds": 5
                            },
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8000
                                },
                                "initialDelaySeconds": 15,
                                "periodSeconds": 10
                            }
                        }]
                    }
                }
            }
        })
        app_deployment.node.add_dependency(collector_service)
        
        # Create Service for sample app
        app_service = cluster.add_manifest("OtelSampleAppService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "otel-sample-app",
                "namespace": "default"
            },
            "spec": {
                "selector": {
                    "app": "otel-sample-app"
                },
                "ports": [
                    {"port": 8000, "targetPort": 8000, "name": "http"},
                    {"port": 8080, "targetPort": 8080, "name": "metrics"}
                ]
            }
        })
        app_service.node.add_dependency(app_deployment)
        
        # Create HPA for otel-sample-app
        otel_hpa = cluster.add_manifest("OtelSampleAppHPA", {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "otel-sample-app-hpa",
                "namespace": "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "otel-sample-app"
                },
                "minReplicas": 2,
                "maxReplicas": 3,
                "metrics": [{
                    "type": "Pods",
                    "pods": {
                        "metric": {
                            "name": "pod_cpu_utilization"
                        },
                        "target": {
                            "type": "AverageValue",
                            "averageValue": "50"
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
        otel_hpa.node.add_dependency(app_deployment)
        
        # Store reference for external dependencies
        self.otel_hpa = otel_hpa
    
    def _get_pod_labels(self) -> dict:
        """Get pod labels based on compute mode"""
        labels = {"app": "otel-sample-app"}
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
        CfnOutput(self, "OtelSampleAppUrl",
            value=f"http://otel-sample-app.default:8000",
            description="URL for the OpenTelemetry sample app"
        )