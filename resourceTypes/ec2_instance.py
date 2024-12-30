import boto3
from datetime import datetime, timedelta

class EC2Instance:
    def __init__(self, instance_id, ec2_client, cw_client):
        self.instance_id = instance_id
        self.ec2_client = ec2_client
        self.cw_client = cw_client
        print(f"Found EC2 instance: {instance_id}")
        self.instance_details = self._get_instance_details()

    def _get_instance_details(self):
        response = self.ec2_client.describe_instances(InstanceIds=[self.instance_id])
        return response['Reservations'][0]['Instances'][0]

    def isIdle(self):
        # Get CPU utilization for the last 14 days
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)

        response = self.cw_client.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': self.instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour periods
            Statistics=['Average']
        )

        if not response['Datapoints']:
            return False  # No data points means we can't determine if it's idle

        # Calculate average CPU utilization
        total_cpu = sum(dp['Average'] for dp in response['Datapoints'])
        avg_cpu = total_cpu / len(response['Datapoints'])

        is_idle = avg_cpu < 5  # Consider idle if average CPU < 5%
        if is_idle:
            print(f"EC2 instance {self.instance_id} is identified as idle")
        return is_idle

    def getSavings(self):
        current_type = self.instance_details['InstanceType']
        
        # For this example, we'll suggest stopping/terminating idle instances
        # You could expand this to suggest downsizing based on usage patterns
        return {
            'currentType': current_type,
            'currentPrice': 'running',  # You could add actual pricing data here
            'newType': 'stopped',
            'newPrice': '0'
        } 