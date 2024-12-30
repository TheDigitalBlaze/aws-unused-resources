import boto3
from datetime import datetime, timezone
import csv

class VPC:
    def __init__(self):
        self.unused_vpcs = []

    def check_vpc_usage(self, region, account_id):
        try:
            session = boto3.Session(region_name=region)
            ec2_client = session.client('ec2')
            
            # Get all VPCs in the region
            vpcs = ec2_client.describe_vpcs()['Vpcs']
            
            for vpc in vpcs:
                vpc_id = vpc['VpcId']
                is_default = vpc.get('IsDefault', False)
                
                # Skip default VPCs as they are managed by AWS
                if is_default:
                    continue
                
                print(f"Found VPC: {vpc_id} in region {region}")
                # Check for resources using this VPC
                is_unused = self._check_vpc_resources(ec2_client, vpc_id)
                
                if is_unused:
                    print(f"VPC {vpc_id} is identified as unused")
                    vpc_info = {
                        'Account ID': account_id,
                        'Region': region,
                        'VPC ID': vpc_id,
                        'CIDR Block': vpc.get('CidrBlock', 'N/A'),
                        'Name': self._get_vpc_name(vpc),
                        'State': vpc.get('State', 'N/A'),
                        'Creation Time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    }
                    self.unused_vpcs.append(vpc_info)
                    
            return self.unused_vpcs
        
        except Exception as e:
            print(f"Error checking VPCs in region {region}: {str(e)}")
            return []

    def _check_vpc_resources(self, ec2_client, vpc_id):
        """Check if VPC has any active resources."""
        try:
            # Check EC2 instances
            instances = ec2_client.describe_instances(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['Reservations']
            if instances:
                return False

            # Check subnets
            subnets = ec2_client.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['Subnets']
            
            # Check Network Interfaces
            enis = ec2_client.describe_network_interfaces(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['NetworkInterfaces']
            if len(enis) > 0:
                return False

            # Check NAT Gateways
            nat_gateways = ec2_client.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['NatGateways']
            if nat_gateways:
                return False

            # Check VPC endpoints
            endpoints = ec2_client.describe_vpc_endpoints(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['VpcEndpoints']
            if endpoints:
                return False

            return True

        except Exception as e:
            print(f"Error checking VPC resources for {vpc_id}: {str(e)}")
            return False

    def _get_vpc_name(self, vpc):
        """Extract VPC name from tags."""
        tags = vpc.get('Tags', [])
        for tag in tags:
            if tag['Key'] == 'Name':
                return tag['Value']
        return 'N/A'

    def write_to_csv(self):
        """Write unused VPCs to CSV file."""
        if not self.unused_vpcs:
            return
            
        fieldnames = ['Account ID', 'Region', 'VPC ID', 'CIDR Block', 'Name', 'State', 'Creation Time']
        
        with open('vpc.csv', 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.unused_vpcs) 