import datetime
import boto3

class DynamoDBTable:
    def __init__(self, table_name, region, cwClient, dynamoClient):
        self.table_name = table_name
        self.region = region
        self.cloudwatch = cwClient
        self.dynamodb = dynamoClient
        print(f"Found DynamoDB table: {table_name} in region {region}")
        self.get_table_details()
        self.get_usage_metrics()

    def get_table_details(self):
        table = self.dynamodb.describe_table(TableName=self.table_name)['Table']
        self.provisioned_read = table.get('ProvisionedThroughput', {}).get('ReadCapacityUnits', 0)
        self.provisioned_write = table.get('ProvisionedThroughput', {}).get('WriteCapacityUnits', 0)
        self.billing_mode = table.get('BillingModeSummary', {}).get('BillingMode', 'PAY_PER_REQUEST')
        self.size_bytes = table.get('TableSizeBytes', 0)
        self.item_count = table.get('ItemCount', 0)

    def get_usage_metrics(self):
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=14)

        # Get read and write consumed capacity
        metrics = [
            ('ConsumedReadCapacityUnits', 'Sum'),
            ('ConsumedWriteCapacityUnits', 'Sum'),
            ('ReadThrottleEvents', 'Sum'),
            ('WriteThrottleEvents', 'Sum')
        ]

        self.metrics = {}
        for metric_name, stat in metrics:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName=metric_name,
                Dimensions=[{'Name': 'TableName', 'Value': self.table_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=[stat]
            )
            
            # Store the average usage over the period
            datapoints = response['Datapoints']
            if datapoints:
                self.metrics[metric_name] = sum(d[stat] for d in datapoints) / len(datapoints)
            else:
                self.metrics[metric_name] = 0

    def is_unused(self):
        # Consider a table unused if it has very low usage over the past 14 days
        read_usage = self.metrics.get('ConsumedReadCapacityUnits', 0)
        write_usage = self.metrics.get('ConsumedWriteCapacityUnits', 0)
        
        # If the table has less than 1 read/write per hour on average
        is_unused = read_usage < 1 and write_usage < 1
        if is_unused:
            print(f"DynamoDB table {self.table_name} is identified as unused")
        return is_unused

    def get_savings(self):
        monthly_storage_cost = (self.size_bytes / (1024 * 1024 * 1024)) * 0.25  # $0.25 per GB-month
        
        if self.billing_mode == 'PROVISIONED':
            # Calculate monthly cost for provisioned capacity
            monthly_read_cost = self.provisioned_read * 0.0065 * 730  # $0.0065 per RCU-hour
            monthly_write_cost = self.provisioned_write * 0.0065 * 730  # $0.0065 per WCU-hour
            
            current_monthly_cost = monthly_storage_cost + monthly_read_cost + monthly_write_cost
            
            # Calculate on-demand cost based on actual usage
            avg_read_units = self.metrics.get('ConsumedReadCapacityUnits', 0)
            avg_write_units = self.metrics.get('ConsumedWriteCapacityUnits', 0)
            new_monthly_cost = monthly_storage_cost + \
                             (avg_read_units * 0.00000025 * 730 * 3600) + \
                             (avg_write_units * 0.00000125 * 730 * 3600)
            
            return {
                "currentType": "Provisioned Capacity",
                "currentPrice": round(current_monthly_cost, 2),
                "newType": "On-Demand" if not self.is_unused() else "Consider Deletion",
                "newPrice": round(new_monthly_cost, 2) if not self.is_unused() else 0
            }
        else:
            # For on-demand tables, just show current cost
            avg_read_units = self.metrics.get('ConsumedReadCapacityUnits', 0)
            avg_write_units = self.metrics.get('ConsumedWriteCapacityUnits', 0)
            current_monthly_cost = monthly_storage_cost + \
                                 (avg_read_units * 0.00000025 * 730 * 3600) + \
                                 (avg_write_units * 0.00000125 * 730 * 3600)
            
            return {
                "currentType": "On-Demand",
                "currentPrice": round(current_monthly_cost, 2),
                "newType": "Consider Deletion" if self.is_unused() else "On-Demand",
                "newPrice": 0 if self.is_unused() else round(current_monthly_cost, 2)
            } 