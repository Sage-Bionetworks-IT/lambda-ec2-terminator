import datetime
import json
import logging
import os

import boto3


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)


IGNORE_TAG_KEY = 'ec2-terminator:ignore'
IGNORE_TAG_VALUE= 'ignore'


def list_regions():
    client = boto3.client('ec2')

    region_desc = client.describe_regions()
    regions = [region['RegionName'] for region in region_desc['Regions']]

    LOG.debug(f"Regions: {regions}")
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
                LOG.debug(f"EC2: {ec2}")

                # check for ignore tag
                ignore = False
                if 'Tags' in ec2:
                    for tag in ec2['Tags']:
                        if tag['Key'] == IGNORE_TAG_KEY \
                                and tag['Value'] == IGNORE_TAG_VALUE:
                            ignore = True
                            break

                # also skip instances less than an hour old
                if not ignore and 'LaunchTime' in ec2:
                    launch = ec2['LaunchTime']
                    now = datetime.datetime.now(launch.tzinfo)
                    age = now - launch
                    if age < datetime.timedelta(hours=1):
                        ignore = True

                if ignore:
                    LOG.debug(f"Ignoring instance {ec2_id}")
                    continue

                instances.append(ec2_id)

    LOG.debug(f"Instances found: {instances}")
    return instances


def set_instance_state(instances, state, region):
    client = boto3.client('ec2', region_name=region)

    action = ''
    resp_key = None
    function = None
    processed = []

    if state.lower() == 'stop':
        function = client.stop_instances
        resp_key = 'StoppingInstances'
        action = 'Stopped'

    elif state.lower() == 'terminate':
        function = client.terminate_instances
        resp_key = 'TerminatingInstances'
        action = 'Terminated'

    else:
        raise ValueError(f"Unknown instance state: {state}")

    resp = function(InstanceIds=instances)
    if resp[resp_key]:
        processed = [i['InstanceId'] for i in resp[resp_key]]

    LOG.debug(f"{action}: {processed}")
    return processed


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
            LOG.info(f"Region: {region}")
            ec2_instances = list_instances(region)

            # Stop or terminate any instances found
            if ec2_instances:
                found = True
                processed.extend(set_instance_state(ec2_instances,
                                                    ec2_action,
                                                    region))
            else:
                LOG.debug("No instances found")

        # Report results
        if found and not processed:
            raise RuntimeError("Some instances failed to stop or terminate")
        elif not found:
            message = "No running or stopped instances found"
        elif ec2_action == 'terminate':
            message = f"Instances terminated: {processed}"
        else:
            message = f"Instances stopped: {processed}"

        LOG.info(message)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": message,
            })
        }

    except Exception as exc:
        LOG.exception(exc)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": str(exc)
            }),
        }
