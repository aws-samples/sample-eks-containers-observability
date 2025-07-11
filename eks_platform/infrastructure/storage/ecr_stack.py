from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
from typing import List

class EcrRepositoriesStack(Stack):
    """
    Creates ECR repositories for container images
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        repository_names: List[str],
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.repositories = {}
        
        # Create ECR repositories
        for repo_name in repository_names:
            repository = ecr.Repository(
                self, 
                f"{repo_name.replace('-', '')}Repo",
                repository_name=repo_name,
                removal_policy=RemovalPolicy.DESTROY,
                empty_on_delete=True  # Use this instead of deprecated autoDeleteImages
            )
            
            self.repositories[repo_name] = repository
            
            # Output the repository URI
            CfnOutput(
                self,
                f"{repo_name.replace('-', '')}RepoUri",
                value=repository.repository_uri,
                description=f"URI for the {repo_name} ECR repository"
            )