import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def on_event(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    
    request_type = event['RequestType']
    cluster_name = event['ResourceProperties']['ClusterName']
    node_role_arn = event['ResourceProperties']['NodeRoleArn']
    
    eks_client = boto3.client('eks')
    
    try:
        if request_type in ['Create', 'Update']:
            logger.info(f"Enabling Auto Mode for cluster: {cluster_name}")
            
            response = eks_client.update_cluster_config(
                name=cluster_name,
                computeConfig={
                    'enabled': True,
                    'nodeRoleArn': node_role_arn,
                    'nodePools': [
                        'general-purpose',  
                        'system'          
                    ]
                },
                kubernetesNetworkConfig={
                    'elasticLoadBalancing': {
                        'enabled': True
                    }
                },
                storageConfig={
                    'blockStorage': {
                        'enabled': True
                    }
                }
            )
            
            logger.info(f"Auto Mode update initiated: {response['update']['id']}")
            
            return {
                'PhysicalResourceId': f"{cluster_name}-auto-mode",
                'Data': {
                    'UpdateId': response['update']['id'],
                    'Status': 'INITIATED'
                }
            }
            
        elif request_type == 'Delete':
            logger.info(f"Disabling Auto Mode for cluster: {cluster_name}")
            
            response = eks_client.update_cluster_config(
                name=cluster_name,
                computeConfig={
                    'enabled': False
                }
            )
            
            return {
                'PhysicalResourceId': f"{cluster_name}-auto-mode",
                'Data': {
                    'UpdateId': response['update']['id'],
                    'Status': 'DISABLED'
                }
            }
            
    except ClientError as e:
        logger.error(f"Error: {str(e)}")
        if request_type == 'Delete':
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info("Cluster not found during delete - treating as success")
                return {
                    'PhysicalResourceId': f"{cluster_name}-auto-mode",
                    'Data': {'Status': 'NOT_FOUND'}
                }
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise e