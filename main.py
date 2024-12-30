# identify the following unused AWS resources:
# - EBS volumes
# - EIPs
# - Load Balancers
# - EFS volumes
# - NAT Gateways
# - RDS instances
# - RDS snapshots
# - DynamoDB tables
# - VPCs

import os
import boto3
import argparse
from resourceTypes.ebs_volume import EBSVolume
from resourceTypes.efs import EFSFileSystem
from resourceTypes.elastic_ip import ElasticIP
from resourceTypes.load_balancer import ElasticLoadBalancer
from resourceTypes.nat_gateway import NATGateway
from resourceTypes.rds import DatabaseInstance, RDSSnapshot
from resourceTypes.dynamodb import DynamoDBTable
from resourceTypes.vpc import VPC
from resourceTypes.ec2_instance import EC2Instance
from uploadFile import upload_file
from writeToCSV import write_to_csv

def clean_old_files():
    csv_files = [
        "eip.csv", "ebs.csv", "elb.csv", "natgw.csv", "efs.csv", 
        "rds.csv", "rds_snapshots.csv", "ec2.csv", "dynamodb.csv", "vpc.csv"
    ]
    for file in csv_files:
        if os.path.exists(file):
            os.remove(file)

def get_account_ids():
    accounts = []
    org = boto3.client('organizations')
    next_token = None
    
    while True:
        if next_token is None:
            resp = org.list_accounts()
        else:
            resp = org.list_accounts(NextToken=next_token)
        
        for acc in resp['Accounts']:
            accounts.append(acc['Id'])

        if 'NextToken' not in resp:
            break
        next_token = resp['NextToken']

    return accounts

def get_session_for_account(account, sts_client):
    if account == sts_client.get_caller_identity()['Account']:
        return boto3.Session()
    
    creds = sts_client.assume_role(
        RoleArn=f'arn:aws:iam::{account}:role/OrganizationAccountAccessRole',
        RoleSessionName='unusedResources'
    )
    return boto3.Session(
        aws_access_key_id=creds['Credentials']['AccessKeyId'],
        aws_secret_access_key=creds['Credentials']['SecretAccessKey'],
        aws_session_token=creds['Credentials']['SessionToken']
    )

def get_regions(region_var=None):
    if region_var:
        return {'Regions': [{'RegionName': region_var}]}
    
    ac = boto3.client('account')
    return ac.list_regions(RegionOptStatusContains=['ENABLED','ENABLED_BY_DEFAULT'])

def check_ebs_volumes(region, account):
    try:
        ec2client = boto3.client('ec2', region_name=region)
        cwclient = boto3.client('cloudwatch', region_name=region)
        
        volumes = ec2client.describe_volumes()
        for volume in volumes["Volumes"]:
            try:
                id = volume['VolumeId']
                print("Volume found: " + id)
                v = EBSVolume(id, ec2client, cwclient)
                if v.inUse() == False:
                    volumeSavings = v.getSavings()
                    write_to_csv("ebs.csv", account, region, "EBSVolume", id, 
                               volumeSavings['currentType'], volumeSavings['currentPrice'], 
                               volumeSavings['newType'], volumeSavings['newPrice'])
            except Exception as error:
                print(f"Error processing volume {id}: {error}")
    except Exception as error:
        print(f"Error checking EBS volumes in {region}: {error}")

def check_elastic_ips(region, account):
    try:
        ec2client = boto3.client('ec2', region_name=region)
        
        eips = ec2client.describe_addresses()
        for eip in eips["Addresses"]:
            try:
                eipId = eip['AllocationId']
                print("EIP found: " + eipId)
                eip = ElasticIP(eipId, ec2client)
                if eip.inUse() == False:
                    eipSavings = eip.getSavings()
                    write_to_csv("eip.csv", account, region, eipId, 
                               eipSavings['currentType'], eipSavings['currentPrice'], 
                               eipSavings['newType'], eipSavings['newPrice'])
            except Exception as error:
                print(f"Error processing EIP {eipId}: {error}")
    except Exception as error:
        print(f"Error checking Elastic IPs in {region}: {error}")

def check_load_balancers(region, account):
    try:
        elbv2client = boto3.client('elbv2', region_name=region)
        cwclient = boto3.client('cloudwatch', region_name=region)
        
        elbs = elbv2client.describe_load_balancers()
        for elb in elbs["LoadBalancers"]:
            try:
                if elb["State"]["Code"] == "active":
                    lbId = elb["LoadBalancerArn"].split('/',1)[1]
                    print("LB found: " + lbId)
                    lb = ElasticLoadBalancer(elb["LoadBalancerArn"], elbv2client, cwclient)
                    if lb.inUse() == False:
                        lbSavings = lb.getSavings()
                        write_to_csv("elb.csv", account, region, "ELB", lbId, 
                                   lbSavings['currentType'], lbSavings['currentPrice'], 
                                   lbSavings['newType'], lbSavings['newPrice'])
            except Exception as error:
                print(f"Error processing Load Balancer {lbId}: {error}")
    except Exception as error:
        print(f"Error checking Load Balancers in {region}: {error}")

def check_nat_gateways(region, account):
    try:
        ec2client = boto3.client('ec2', region_name=region)
        cwclient = boto3.client('cloudwatch', region_name=region)
        
        natgws = ec2client.describe_nat_gateways()
        for natgw in natgws['NatGateways']:
            try:
                if natgw['State'] == 'available':
                    natgwId = natgw['NatGatewayId']
                    print("NATGW found: " + natgwId)
                    natgw = NATGateway(natgwId, ec2client, cwclient)
                    if natgw.inUse() == False:
                        natgwSavings = natgw.getSavings()
                        write_to_csv("natgw.csv", account, region, "NATGW", natgwId, 
                                   natgwSavings['currentType'], natgwSavings['currentPrice'], 
                                   natgwSavings['newType'], natgwSavings['newPrice'])
            except Exception as error:
                print(f"Error processing NAT Gateway {natgwId}: {error}")
    except Exception as error:
        print(f"Error checking NAT Gateways in {region}: {error}")

def check_efs_filesystems(region, account):
    try:
        efsclient = boto3.client('efs', region_name=region)
        cwclient = boto3.client('cloudwatch', region_name=region)
        
        filesystems = efsclient.describe_file_systems()['FileSystems']
        for fs in filesystems:
            try:
                print("FileSystem found: " + fs['FileSystemId'])
                i = EFSFileSystem(fs['FileSystemId'], efsclient, cwclient)
                if i.isUsed() == False:
                    efsSavings = i.getSavings()
                    write_to_csv("efs.csv", account, region, "EFSFileSystem", fs['FileSystemId'], 
                               efsSavings['currentType'], efsSavings['currentPrice'], 
                               efsSavings['newType'], efsSavings['newPrice'])
            except Exception as error:
                print(f"Error processing EFS {fs['FileSystemId']}: {error}")
    except Exception as error:
        print(f"Error checking EFS in {region}: {error}")

def check_rds_instances(region, account):
    try:
        rdsclient = boto3.client('rds', region_name=region)
        cwclient = boto3.client('cloudwatch', region_name=region)
        
        dbs = rdsclient.describe_db_instances()
        for db in dbs['DBInstances']:
            try:
                if db['DBInstanceStatus'] == 'available':
                    dbId = db['DBInstanceIdentifier']
                    print("DB found: " + dbId)
                    dbi = DatabaseInstance(dbId, region, cwclient, rdsclient)
                    if dbi.isIdle():
                        computeSavings = dbi.rightsizeCompute()
                        storageSavings = dbi.rightsizeStorage()
                        write_to_csv("rds.csv", account, region, "RDSInstance", dbId, 
                                   computeSavings['currentInstanceType'], computeSavings['currentInstancePrice'], 
                                   computeSavings['newInstanceType'], computeSavings['newInstancePrice'])
                        write_to_csv("rds.csv", account, region, "RDSStorageVolume", dbId, 
                                   storageSavings['currentType'], storageSavings['currentPrice'], 
                                   storageSavings['newType'], storageSavings['newPrice'])
                    
                    # Handle unused snapshots
                    for snapshot in dbi.unused_snapshots:
                        snapshotSavings = snapshot.get_savings()
                        write_to_csv("rds_snapshots.csv", account, region, "RDSSnapshot", 
                                   f"{dbId}-{snapshot.snapshot_id}", snapshotSavings['currentType'], 
                                   snapshotSavings['currentPrice'], snapshotSavings['newType'], 
                                   snapshotSavings['newPrice'])
            except Exception as error:
                print(f"Error processing RDS instance {dbId}: {error}")

        # Also check for snapshots of deleted instances
        try:
            all_snapshots = rdsclient.describe_db_snapshots()['DBSnapshots']
            checked_instances = set(db['DBInstanceIdentifier'] for db in dbs['DBInstances'])
            
            for snapshot in all_snapshots:
                if snapshot['DBInstanceIdentifier'] not in checked_instances:
                    try:
                        snapshot_obj = RDSSnapshot(snapshot['DBSnapshotIdentifier'], rdsclient)
                        if snapshot_obj.is_unused():
                            snapshotSavings = snapshot_obj.get_savings()
                            write_to_csv("rds_snapshots.csv", account, region, "RDSSnapshot", 
                                       f"deleted-{snapshot_obj.snapshot_id}", snapshotSavings['currentType'], 
                                       snapshotSavings['currentPrice'], snapshotSavings['newType'], 
                                       snapshotSavings['newPrice'])
                    except Exception as error:
                        print(f"Error processing snapshot {snapshot['DBSnapshotIdentifier']}: {error}")
        except Exception as error:
            print(f"Error checking snapshots for deleted instances: {error}")
    except Exception as error:
        print(f"Error checking RDS instances in {region}: {error}")

def check_dynamodb_tables(region, account_id):
    dynamodb = boto3.client('dynamodb', region_name=region)
    cloudwatch = boto3.client('cloudwatch', region_name=region)

    try:
        paginator = dynamodb.get_paginator('list_tables')
        for page in paginator.paginate():
            for table_name in page['TableNames']:
                table = DynamoDBTable(table_name, region, cloudwatch, dynamodb)
                if table.is_unused():
                    savings = table.get_savings()
                    write_to_csv("dynamodb.csv", account_id, region, "DynamoDBTable", table_name,
                               savings['currentType'], savings['currentPrice'],
                               savings['newType'], savings['newPrice'])
    except Exception as e:
        print(f"Error checking DynamoDB tables in {region}: {str(e)}")

def check_vpc(region, account_id):
    vpc = VPC()
    vpc.check_vpc_usage(region, account_id)
    vpc.write_to_csv()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="if true, fetch resources from all accounts in the organization")
    parser.add_argument("--s3", help="store the reports in a bucket at this location")
    parser.add_argument("--region", help="only scan resources in this region")
    parser.add_argument("--profile", help="AWS profile name")
    
    args = parser.parse_args()
    
    if args.profile:
        boto3.setup_default_session(profile_name=args.profile)
    
    # Clean up old CSV files
    clean_old_files()
    
    # Get accounts to scan
    sts = boto3.client('sts')
    accounts = get_account_ids() if args.org == "true" else [sts.get_caller_identity()['Account']]
    
    # Get regions to scan
    regions = get_regions(args.region)
    
    # Scan resources in each account and region
    for account in accounts:
        try:
            session = get_session_for_account(account, sts)
            
            for region in regions['Regions']:
                region_name = region['RegionName']
                print(f"Scanning region: {region_name} in account: {account}")
                
                try:
                    check_ebs_volumes(region_name, account)
                    check_elastic_ips(region_name, account)
                    check_load_balancers(region_name, account)
                    check_nat_gateways(region_name, account)
                    check_efs_filesystems(region_name, account)
                    check_rds_instances(region_name, account)
                    check_dynamodb_tables(region_name, account)
                    check_vpc(region_name, account)
                except Exception as error:
                    print(f"Error processing region {region_name}: {error}")
                    continue
                
        except Exception as error:
            print(f"Error processing account {account}: {error}")
            continue
    
    # Upload results to S3 if specified
    if args.s3:
        try:
            file_list = [
                "ebs.csv", "eip.csv", "elb.csv", "natgw.csv", "efs.csv", 
                "rds.csv", "rds_snapshots.csv", "ec2.csv", "dynamodb.csv", "vpc.csv"
            ]
            for file in file_list:
                if os.path.exists(file):
                    upload_file(file, args.s3)
        except Exception as error:
            print(f"Error uploading files to S3: {error}")

if __name__ == "__main__":
    main()