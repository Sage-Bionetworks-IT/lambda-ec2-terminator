import json
import logging
import os
import time

import boto3


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)


def list_regions():
    client = boto3.client('ec2')

    region_desc = client.describe_regions()
    regions = [region['RegionName'] for region in region_desc['Regions']]

    logging.debug(f"Regions: {regions}")
    return regions


def list_instances(region):
    """Return a list of instance IDs in the given region to stop or terminate"""
    client = boto3.client('ec2', region_name=region)

    # This intentionally reprocesses stopped instances for debugging
    state_filters = [{
        'Name': 'instance-state-name',
        'Values': ['running', 'stopping', 'stopped'],
    }]

    instances = []

    pager = client.get_paginator('describe_instances')
    for page in pager.paginate(Filters=state_filters):
        for rsvp in page['Reservations']:
            for ec2 in rsvp['Instances']:
                ec2_id = ec2['InstanceId']
                logging.debug(f"EC2: {ec2}")
                instances.append(ec2_id)

    logging.debug(f"Instances found: {instances}")
    return instances


def stop_instances(instances, region):
    """Stop all given instances"""
    client = boto3.client(region_name=region)

    stopped = []
    resp = client.stop_instances(InstanceIds=instances)
    if resp['StoppingInstances']:
        stopped = [s['InstanceId'] for s in resp['StoppingInstances']]

    logging.debug(f"Stopped: {stopped}")
    return stopped


def terminate_instances(instances, region):
    """Terminate all given instances"""
    client = boto3.client(region_name=region)

    terminated = []
    resp = client.terminate_instances(InstanceIds=instances)
    if resp['TerminatingInstances']:
        terminated = [t['InstanceId'] for t in resp['TerminatingInstances']]

    logging.debug(f"Terminated :{terminated}")
    return terminated


def lambda_handler(event, context):
    """Lambda function to stop or terminate all EC2 instances in the current  account.

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    try:
        # Are we stopping or terminating instances?
        ec2_action = 'stop'
        if os.environ.get('EC2_ACTION', '') == 'TERMINATE':
            ec2_action = 'terminate'

        # Get the list of regions
        regions = list_regions()
        if not regions:
            raise ValueError("No available regions")

        # List of stopped or terminated instances
        found = False
        processed = []

        # Iterate over every region
        for region in regions:
            logging.info(f"Region: {region}")
            ec2_instances = list_instances(region)

            # Stop or terminate any instances found
            if ec2_instances:
                found = True
                if ec2_action == 'terminate':
                    logging.info(f"Terminating Instances: {ec2_instances}")
                    terminated = terminate_instances(ec2_instances, region)
                    processed.extend(terminated)
                else:
                    logging.info(f"Stopping Instances: {ec2_instances}")
                    stopped = stop_instances(ec2_instances, region)
                    processed.extend(stopped)
            else:
                logging.debug("No instances found")

        # Report results
        if found and not processed:
            raise RuntimeError("Some instances failed to stop or terminate")
        elif not found:
            message = "No running or stopped instances found"
        elif ec2_action == 'terminate':
            message = f"Instances terminated: {processed}"
        else:
            message = f"Instances stopped: {processed}"

        logging.info(message)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": message,
            })
        }

    except Exception as exc:
        logging.exception(exc)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": str(exc)
            }),
        }
