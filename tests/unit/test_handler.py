import datetime
import json
import os

import pytest
import boto3
from botocore.stub import Stubber

from ec2_terminator import app


@pytest.fixture()
def stub_ec2_client(mocker):
    """A single client for all stubbers"""
    env_vars = {
        'AWS_DEFAULT_REGION': 'test-region',
    }
    mocker.patch.dict(os.environ, env_vars)
    client = boto3.client('ec2')
    return client


@pytest.fixture()
def mock_region_response():
    return {
        'Regions': [
            {
                'RegionName': 'test-region',
            }
        ]
    }


@pytest.fixture()
def mock_instance_response():
    return {
        'Reservations': [
            {
                'Instances': [
                    {
                        'InstanceId': 'test-instance',
                        'State': {'Name': 'running'},
                    }
                ]
            }
        ]
    }


@pytest.fixture()
def mock_ignore_tag_response():
    return {
        'Reservations': [
            {
                'Instances': [
                    {
                        'InstanceId': 'ignore-instance',
                        'State': {'Name': 'running'},
                        'Tags': [{
                            'Key': app.IGNORE_TAG_KEY,
                            'Value': app.IGNORE_TAG_VALUE,
                        }]
                    }
                ]
            }
        ]
    }



@pytest.fixture()
def mock_ignore_age_response():
    return {
        'Reservations': [
            {
                'Instances': [
                    {
                        'InstanceId': 'ignore-instance',
                        'State': {'Name': 'running'},
                        'LaunchTime': datetime.datetime.now()
                    }
                ]
            }
        ]
    }


@pytest.fixture()
def mock_no_instances_response():
    return {
        'Reservations': [],
    }


@pytest.fixture()
def mock_stop_response():
    return {
        'StoppingInstances': [
            {
                'InstanceId': 'test-instance',
            }
        ]
    }


@pytest.fixture()
def mock_terminate_response():
    return {
        'TerminatingInstances': [
            {
                'InstanceId': 'test-instance',
            }
        ]
    }


@pytest.fixture()
def mock_terminate_failed_response():
    return {
        'TerminatingInstances': [],
    }


def test_stop(mocker,
              stub_ec2_client,
              mock_region_response,
              mock_instance_response,
              mock_stop_response):
    """Test stopping instances"""

    env_vars = {
        'EC2_ACTION': '',
    }
    mocker.patch.dict(os.environ, env_vars)

    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_instance_response)
        stubber.add_response('stop_instances', mock_stop_response)

        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "Instances stopped: ['test-instance']"


def test_terminate(mocker,
                   stub_ec2_client,
                   mock_region_response,
                   mock_instance_response,
                   mock_terminate_response):
    """Test terminating instances"""

    env_vars = {
        'EC2_ACTION': 'TeRmInAtE',
    }
    mocker.patch.dict(os.environ, env_vars)

    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_instance_response)
        stubber.add_response('terminate_instances', mock_terminate_response)

        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "Instances terminated: ['test-instance']"


def test_no_instances(mocker,
                      stub_ec2_client,
                      mock_region_response,
                      mock_no_instances_response):
    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_no_instances_response)
        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "No running or stopped instances found"


def test_ignore_tag_instance(mocker,
                             stub_ec2_client,
                             mock_region_response,
                             mock_ignore_tag_response):
    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_ignore_tag_response)
        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "No running or stopped instances found"


def test_ignore_age_instance(mocker,
                             stub_ec2_client,
                             mock_region_response,
                             mock_ignore_age_response):
    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_ignore_age_response)
        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert "message" in ret["body"]
    assert data["message"] == "No running or stopped instances found"


def test_terminate_failed(mocker,
                          stub_ec2_client,
                          mock_region_response,
                          mock_instance_response,
                          mock_terminate_failed_response):

    env_vars = {
        'EC2_ACTION': 'TERMINATE',
    }
    mocker.patch.dict(os.environ, env_vars)

    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', mock_region_response)
        stubber.add_response('describe_instances', mock_instance_response)
        stubber.add_response('terminate_instances', mock_terminate_failed_response)
        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 500
    assert "message" in ret["body"]
    assert data["message"] == "Some instances failed to stop or terminate"


def test_client_exception(mocker):
    mocker.patch("boto3.client", side_effect=Exception('TestClientException'))

    ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 500
    assert "message" in ret["body"]
    assert data["message"] == "TestClientException"


def test_regions_exception(mocker, stub_ec2_client):
    magic_client = mocker.MagicMock(return_value=stub_ec2_client)
    mocker.patch('boto3.client', magic_client)

    no_regions = {
        "Regions": [],
    }

    with Stubber(stub_ec2_client) as stubber:
        stubber.add_response('describe_regions', no_regions)
        ret = app.lambda_handler(None, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 500
    assert "message" in ret["body"]
    assert data["message"] == "No available regions"
