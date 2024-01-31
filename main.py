# identify the following unused AWS resources:
# - EBS volumes
# - EIPs
# - Load Balancers
# - EFS volumes
# - NAT Gateways
# - RDS instances

import os
import boto3
import argparse
from resourceTypes.ebs_volume import EBSVolume
from resourceTypes.efs import EFSFileSystem
from resourceTypes.elastic_ip import ElasticIP
from resourceTypes.load_balancer import ElasticLoadBalancer
from resourceTypes.nat_gateway import NATGateway
from resourceTypes.rds import DatabaseInstance
from uploadFile import upload_file
from writeToCSV import write_to_csv

# Remove old eip.csv and ebs.csv from the current path if they exist
if os.path.exists("eip.csv"):
    os.remove("eip.csv")
if os.path.exists("ebs.csv"):
    os.remove("ebs.csv")
if os.path.exists("elb.csv"):
    os.remove("elb.csv")
if os.path.exists("natgw.csv"):
    os.remove("natgw.csv")
if os.path.exists("efs.csv"):
    os.remove("efs.csv")
if os.path.exists("rds.csv"):
    os.remove("rds.csv")

# get all account ids in the organization
def getAccountIds():
    accounts = []

    org = boto3.client('organizations')
    nextToken = None
    while True:
        if nextToken == None:
            resp = org.list_accounts()
        else:
            resp = org.list_accounts(NextToken=nextToken)
        
        for acc in resp['Accounts']:
            accounts.append(acc['Id'])

        if 'NextToken' not in resp:
            break
        else:
            nextToken = resp['NextToken']

    return accounts

# get params from command line
parser = argparse.ArgumentParser()
parser.add_argument("--org", help="if true, fetch resources from all accounts in the organization")
parser.add_argument("--s3", help="store the reports in a bucket at this location")
parser.add_argument("--region", help="only scan resources in this region")

args = parser.parse_args()
scanOrg = False
if args.org == "true":
    scanOrg = True

regionVar = None
if args.region != None:
    regionVar = args.region

# get the account id(s) to scan
sts = boto3.client('sts')

if scanOrg:
    accounts = getAccountIds()
else:
    accounts = [sts.get_caller_identity()['Account']]

for account in accounts:
    # sts assumerole into the accounts and get active regions
    try:
        if account == sts.get_caller_identity()['Account']:
            new_session = boto3.Session()
        else:
            newCreds = sts.assume_role(RoleArn='arn:aws:iam::' + str(account) + ':role/OrganizationAccountAccessRole', RoleSessionName='unusedResources')
            new_session = boto3.Session(aws_access_key_id=newCreds['Credentials']['AccessKeyId'],
                            aws_secret_access_key=newCreds['Credentials']['SecretAccessKey'],
                            aws_session_token=newCreds['Credentials']['SessionToken'])
        ac = boto3.client('account')
        if regionVar != None:
            regions = {'Regions': [{'RegionName': regionVar}] }
        else:
            regions = ac.list_regions(RegionOptStatusContains=['ENABLED','ENABLED_BY_DEFAULT'])
    except Exception as error:
        print(error)
        continue

    # iterate through the regions and get the resources
    for region in regions['Regions']:
        print("Scanning region: " + region['RegionName'] + " in account: " + account)
        try:
            ec2client = new_session.client('ec2', region_name=region['RegionName'])
            elbv2client = new_session.client('elbv2', region_name=region['RegionName'])
            efsclient = new_session.client('efs', region_name=region['RegionName'])
            rdsclient = new_session.client('rds', region_name=region['RegionName'])
            cwclient = new_session.client('cloudwatch', region_name=region['RegionName'])
        except Exception as error:
            print(error)
            continue

        # EIPs
        try:
            eips = ec2client.describe_addresses()
            for eip in eips["Addresses"]:
                try:
                    eipId = eip['AllocationId']
                    print("EIP found: " + eipId)
                    eip = ElasticIP(eipId, ec2client)
                    if eip.inUse() == False:
                        eipSavings = eip.getSavings()
                        write_to_csv("eip.csv", account, region['RegionName'], eipId, eipSavings['currentType'], eipSavings['currentPrice'], eipSavings['newType'], eipSavings['newPrice'])
                except Exception as error:
                    print(error)
        except Exception as error:
            print(error)

        # EBS Volumes
        try:
            volumes = ec2client.describe_volumes()
            for volume in volumes["Volumes"]:
                try:
                    id = volume['VolumeId']
                    print("Volume found: " + id)
                    v = EBSVolume(id, ec2client, cwclient)
                    if v.inUse() == False:
                        volumeSavings = v.getSavings()
                        write_to_csv("ebs.csv", account, region['RegionName'], "EBSVolume", id, volumeSavings['currentType'], volumeSavings['currentPrice'], volumeSavings['newType'], volumeSavings['newPrice'])
                except Exception as error:
                    print(error)
        except Exception as error:
            print(error)

        # Load Balancers
        try:
            elbs = elbv2client.describe_load_balancers()
            for elb in elbs["LoadBalancers"]:
                try:
                    if elb["State"]["Code"] == "active":
                        lbId = elb["LoadBalancerArn"].split('/',1)[1]
                        print("LB found: " + lbId)
                        lb = ElasticLoadBalancer(elb["LoadBalancerArn"], elbv2client, cwclient)
                        if lb.inUse() == False:
                            lbSavings = lb.getSavings()
                            write_to_csv("elb.csv", account, region['RegionName'], "ELB", lbId, lbSavings['currentType'], lbSavings['currentPrice'], lbSavings['newType'], lbSavings['newPrice'])
                except Exception as error:
                    print(error)
        except Exception as error:
            print(error)

        # NAT Gateways
        try:
            natgws = ec2client.describe_nat_gateways()
            for natgw in natgws['NatGateways']:
                try:
                    if natgw['State'] == 'available':
                        natgwId = natgw['NatGatewayId']
                        print("NATGW found: " + natgwId)
                        natgw = NATGateway(natgwId, ec2client, cwclient)
                        if natgw.inUse() == False:
                            natgwSavings = natgw.getSavings()
                            write_to_csv("natgw.csv", account, region['RegionName'], "NATGW", natgwId, natgwSavings['currentType'], natgwSavings['currentPrice'], natgwSavings['newType'], natgwSavings['newPrice'])
                except Exception as error:
                    print(error)
        except Exception as error:
            print(error)
        
        # EFS
        try:
            filesystems = efsclient.describe_file_systems()['FileSystems']
            for fs in filesystems:
                try:
                    print("FileSystem found: " + fs['FileSystemId'])
                    i = EFSFileSystem(fs['FileSystemId'], efsclient, cwclient)
                    if i.isUsed() == False:
                        efsSavings = i.getSavings()
                        write_to_csv("efs.csv", account, region['RegionName'], "EFSFileSystem", fs['FileSystemId'], efsSavings['currentType'], efsSavings['currentPrice'], efsSavings['newType'], efsSavings['newPrice'])
                except Exception as error:
                    print(error)
        except Exception as error:
            print(error)


        dbs = rdsclient.describe_db_instances()
        for db in dbs['DBInstances']:
            try:
                if db['DBInstanceStatus'] == 'available':
                    try:
                        dbId = db['DBInstanceIdentifier']
                        print("DB found: " + dbId)
                        dbi = DatabaseInstance(dbId, region, cwclient, rdsclient)
                        if dbi.isIdle():
                            computeSavings = dbi.rightsizeCompute()
                            storageSavings = dbi.rightsizeStorage()
                            write_to_csv("rds.csv", account, region['RegionName'], "RDSInstance", dbId, computeSavings['currentInstanceType'], computeSavings['currentInstancePrice'], computeSavings['newInstanceType'], computeSavings['newInstancePrice'])
                            write_to_csv("rds.csv", account, region['RegionName'], "RDSStorageVolume", dbId, storageSavings['currentType'], storageSavings['currentPrice'], storageSavings['newType'], storageSavings['newPrice'])
                    except Exception as error:
                        print(error)
            except Exception as error:
                print(error)

if args.s3 != None:
    storeInBucket = args.s3
    try:
        file_list = ["ebs.csv", "eip.csv", "elb.csv", "natgw.csv", "efs.csv", "rds.csv"]
        for file in file_list:
            if os.path.exists(file):
                upload_file(file, storeInBucket)
    except Exception as error:
        print(error)