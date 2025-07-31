from aws_cdk import (
    aws_eks as eks,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

class PrometheusConstruct(Construct):
    """
    Construct for deploying Prometheus server for metrics collection
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str,
        cluster: eks.ICluster,
        workspace_id: str,
        region: str,
        monitoring_namespace=None,
        compute_config=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.cluster = cluster
        self.compute_config = compute_config
        
        # Use provided monitoring namespace or create one
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
        
        # Create service account for Prometheus
        prometheus_sa = cluster.add_service_account(
            "prometheus-sa",
            name="amp-iamproxy-service-account",
            namespace="monitoring"
        )
        prometheus_sa.node.add_dependency(self.monitoring_namespace)
        
        # Add AMP permissions
        prometheus_sa.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "aps:RemoteWrite",
                    "aps:QueryMetrics",
                    "aps:GetSeries",
                    "aps:GetLabels",
                    "aps:GetMetricMetadata",
                    "sts:AssumeRoleWithWebIdentity"
                ],
                resources=[f"arn:aws:aps:{region}:*:workspace/{workspace_id}"]
            )
        )
        
        # Create RBAC
        self._create_rbac()
        
        # Create Prometheus ConfigMap
        prometheus_config = cluster.add_manifest("PrometheusConfigMap", {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "prometheus-server-conf",
                "namespace": "monitoring"
            },
            "data": {
                "prometheus.yml": f"""global:
  scrape_interval: 15s
  evaluation_interval: 15s

remote_write:
  - url: https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}/api/v1/remote_write
    sigv4:
      region: {region}

scrape_configs:
  - job_name: kubernetes-pods
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
        regex: ([^:]+)(?:\\d+)?;(\\d+)
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
"""
            }
        })
        prometheus_config.node.add_dependency(self.monitoring_namespace)
        
        # Create Prometheus Deployment
        prometheus_deployment = cluster.add_manifest("PrometheusDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "prometheus-server",
                "namespace": "monitoring"
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": "prometheus-server"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": self._get_pod_labels()
                    },
                    "spec": {
                        **self._get_pod_spec(),
                        "serviceAccountName": "amp-iamproxy-service-account",
                        "dnsPolicy": "ClusterFirst",
                        "containers": [{
                            "name": "prometheus",
                            "image": "prom/prometheus:v2.40.0",
                            "args": [
                                "--config.file=/etc/prometheus/prometheus.yml",
                                "--storage.tsdb.path=/prometheus/",
                                "--web.console.libraries=/usr/share/prometheus/console_libraries",
                                "--web.console.templates=/usr/share/prometheus/consoles",
                                "--web.listen-address=0.0.0.0:9090"
                            ],
                            "env": [
                                {"name": "AWS_REGION", "value": region},
                                {"name": "AWS_DEFAULT_REGION", "value": region},
                                {"name": "AWS_STS_REGIONAL_ENDPOINTS", "value": "regional"}
                            ],
                            "ports": [{
                                "containerPort": 9090
                            }],
                            "volumeMounts": [{
                                "name": "prometheus-config-volume",
                                "mountPath": "/etc/prometheus/"
                            }, {
                                "name": "prometheus-storage-volume",
                                "mountPath": "/prometheus/"
                            }]
                        }],
                        "volumes": [{
                            "name": "prometheus-config-volume",
                            "configMap": {
                                "name": "prometheus-server-conf"
                            }
                        }, {
                            "name": "prometheus-storage-volume",
                            "emptyDir": {}
                        }]
                    }
                }
            }
        })
        prometheus_deployment.node.add_dependency(prometheus_config)
        prometheus_deployment.node.add_dependency(prometheus_sa)
        prometheus_deployment.node.add_dependency(self.cluster_role_binding)
        
        # Create Prometheus Service
        prometheus_service = cluster.add_manifest("PrometheusService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "prometheus-service",
                "namespace": "monitoring"
            },
            "spec": {
                "selector": {
                    "app": "prometheus-server"
                },
                "ports": [{
                    "port": 9090,
                    "targetPort": 9090
                }]
            }
        })
        prometheus_service.node.add_dependency(prometheus_deployment)
        
        # Add outputs
        CfnOutput(self, "PrometheusServiceName",
            value="prometheus-service",
            description="Name of the Prometheus service"
        )
    
    def _get_pod_labels(self) -> dict:
        """Get pod labels based on compute mode"""
        labels = {"app": "prometheus-server"}
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
    
    def _create_rbac(self):
        """Create RBAC for Prometheus"""
        # Create ClusterRole for Prometheus
        self.cluster_role = self.cluster.add_manifest("PrometheusClusterRole", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {
                "name": "prometheus-cluster-role"
            },
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["nodes", "nodes/proxy", "services", "endpoints", "pods"],
                    "verbs": ["get", "list", "watch"]
                },
                {
                    "apiGroups": ["extensions", "networking.k8s.io"],
                    "resources": ["ingresses"],
                    "verbs": ["get", "list", "watch"]
                },
                {
                    "apiGroups": [""],
                    "resources": ["configmaps"],
                    "verbs": ["get", "list", "watch"]
                },
                {
                    "nonResourceURLs": ["/metrics"],
                    "verbs": ["get"]
                },
                {
                    "apiGroups": ["authorization.k8s.io"],
                    "resources": ["subjectaccessreviews"],
                    "verbs": ["create"]
                }
            ]
        })
        
        # Create ClusterRoleBinding
        self.cluster_role_binding = self.cluster.add_manifest("PrometheusClusterRoleBinding", {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {
                "name": "prometheus-cluster-role-binding"
            },
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": "prometheus-cluster-role"
            },
            "subjects": [{
                "kind": "ServiceAccount",
                "name": "amp-iamproxy-service-account",
                "namespace": "monitoring"
            }]
        })
        self.cluster_role_binding.node.add_dependency(self.cluster_role)
        self.cluster_role_binding.node.add_dependency(self.monitoring_namespace)