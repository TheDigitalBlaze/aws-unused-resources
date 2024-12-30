## Introduction

This script will identify the following AWS resources that have not been used in the past 14 days and outputs a number of CSV files that contain references to the unused resources:
* Elastic IPs
* EBS volumes
* RDS snapshots
* EIPs
* Load Balancers
* EFS volumes
* NAT Gateways
* RDS instances
* EC2 instances
* DynamoDB tables (checks for unused tables and cost optimization opportunities)

## Installation instructions

Open CloudShell in the (management) account in your organization and run the following commands to download the script and install its requirements:
```
curl -o aws-unused-resources.zip d2hiwsv3z34i6f.cloudfront.net/aws-unused-resources.zip
unzip aws-unused-resources.zip
cd aws-unused-resources
pip3 install -r requirements.txt
```
## Running the script

After installing all nessesary components, you can execute the script by running:
```
python3 main.py
```

### CLI options
#### --org
Scan the full AWS organization. NOTE: this can only be added when running the script from the management account. A role with the name of OrganizationAccountAccessRole has to be available in all member accounts

Options = true || false \
Default = false \
Example: python3 main.py --org true

#### --s3
If the reports have to be uploaded to an S3 bucket, add the name of the bucket here.

Options = [bucket name] \
Default = None \
Example: python3 main.py --s3 mybucketname

#### --region
Only scan a specific region

Options = [region name] \
Default = scan all active regions \
Example: python3 main.py --region eu-west-1