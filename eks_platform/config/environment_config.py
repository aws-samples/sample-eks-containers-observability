"""
Environment-specific configuration for EKS Fargate Platform
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class NetworkConfig:
    """Network configuration for the environment"""
    vpc_cidr: str = "10.0.0.0/16"
    max_azs: int = 2
    nat_gateways: int = 1
    enable_flow_logs: bool = False


@dataclass
class ComputeConfig:
    """Compute configuration for EKS cluster"""
    mode: str = "auto-mode"  # "fargate" or "auto-mode"
    fargate_profiles: List[str] = field(default_factory=lambda: ["default", "monitoring", "kube-system"])
    auto_mode_enabled: bool = True

@dataclass
class EksConfig:
    cluster_name: str
    version: str = "1.32"
    compute: ComputeConfig = field(default_factory=ComputeConfig)
    admin_user_arn: Optional[str] = None
    admin_role_arn: Optional[str] = None

@dataclass
class MonitoringConfig:
    """Monitoring configuration for the environment"""
    prometheus_enabled: bool = True
    grafana_enabled: bool = True
    retention_days: int = 30
    scrape_interval: str = "15s"
    namespace: str = "monitoring"


@dataclass
class EnvironmentConfig:
    """Complete environment configuration"""
    environment_name: str
    account: str
    region: str
    network: NetworkConfig
    eks: EksConfig
    monitoring: MonitoringConfig

    @classmethod
    def development(cls, account: str, region: str) -> 'EnvironmentConfig':
        """Development environment configuration (Auto Mode)"""
        return cls(
            environment_name="dev",
            account=account,
            region=region,
            network=NetworkConfig(
                nat_gateways=1,
                enable_flow_logs=False
            ),
            eks=EksConfig(
                cluster_name="dev-eks-automode",
                version="1.32",
                compute=ComputeConfig(
                    mode="auto-mode",
                    auto_mode_enabled=True
                ),
                admin_user_arn="arn:aws:iam::123456789:user/user-cli"
            ),
            monitoring=MonitoringConfig(
                prometheus_enabled=True,
                grafana_enabled=True,
                retention_days=7
            )
        )
    
    @classmethod
    def fargate_development(cls, account: str, region: str) -> 'EnvironmentConfig':
        """Development environment configuration (Fargate)"""
        return cls(
            environment_name="dev-fargate",
            account=account,
            region=region,
            network=NetworkConfig(
                nat_gateways=1,
                enable_flow_logs=False
            ),
            eks=EksConfig(
                cluster_name="dev-eks-fargate",
                version="1.32",
                compute=ComputeConfig(
                    mode="fargate",
                    fargate_profiles=["default", "monitoring", "opentelemetry", "kube-system"],
                    auto_mode_enabled=False
                ),
                admin_user_arn="arn:aws:iam::123456789:user/user-cli"
            ),
            monitoring=MonitoringConfig(
                prometheus_enabled=True,
                grafana_enabled=True,
                retention_days=7
            )
        )

