from __future__ import unicode_literals

import boto3
import botocore.exceptions
import sure  # noqa
import datetime
import uuid
import json

from botocore.exceptions import ClientError, ParamValidationError
from nose.tools import assert_raises

from moto import mock_ssm, mock_cloudformation


@mock_ssm
def test_delete_parameter():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="String"
    )

    response = client.get_parameters(Names=["test"])
    len(response["Parameters"]).should.equal(1)

    client.delete_parameter(Name="test")

    response = client.get_parameters(Names=["test"])
    len(response["Parameters"]).should.equal(0)


@mock_ssm
def test_delete_parameters():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="String"
    )

    response = client.get_parameters(Names=["test"])
    len(response["Parameters"]).should.equal(1)

    result = client.delete_parameters(Names=["test", "invalid"])
    len(result["DeletedParameters"]).should.equal(1)
    len(result["InvalidParameters"]).should.equal(1)

    response = client.get_parameters(Names=["test"])
    len(response["Parameters"]).should.equal(0)


@mock_ssm
def test_get_parameters_by_path():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="/foo/name1", Description="A test parameter", Value="value1", Type="String"
    )

    client.put_parameter(
        Name="/foo/name2", Description="A test parameter", Value="value2", Type="String"
    )

    client.put_parameter(
        Name="/bar/name3", Description="A test parameter", Value="value3", Type="String"
    )

    client.put_parameter(
        Name="/bar/name3/name4",
        Description="A test parameter",
        Value="value4",
        Type="String",
    )

    client.put_parameter(
        Name="/baz/name1",
        Description="A test parameter (list)",
        Value="value1,value2,value3",
        Type="StringList",
    )

    client.put_parameter(
        Name="/baz/name2", Description="A test parameter", Value="value1", Type="String"
    )

    client.put_parameter(
        Name="/baz/pwd",
        Description="A secure test parameter",
        Value="my_secret",
        Type="SecureString",
        KeyId="alias/aws/ssm",
    )

    client.put_parameter(
        Name="foo", Description="A test parameter", Value="bar", Type="String"
    )

    client.put_parameter(
        Name="baz", Description="A test parameter", Value="qux", Type="String"
    )

    response = client.get_parameters_by_path(Path="/", Recursive=False)
    len(response["Parameters"]).should.equal(2)
    {p["Value"] for p in response["Parameters"]}.should.equal(set(["bar", "qux"]))

    response = client.get_parameters_by_path(Path="/", Recursive=True)
    len(response["Parameters"]).should.equal(9)

    response = client.get_parameters_by_path(Path="/foo")
    len(response["Parameters"]).should.equal(2)
    {p["Value"] for p in response["Parameters"]}.should.equal(set(["value1", "value2"]))

    response = client.get_parameters_by_path(Path="/bar", Recursive=False)
    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Value"].should.equal("value3")

    response = client.get_parameters_by_path(Path="/bar", Recursive=True)
    len(response["Parameters"]).should.equal(2)
    {p["Value"] for p in response["Parameters"]}.should.equal(set(["value3", "value4"]))

    response = client.get_parameters_by_path(Path="/baz")
    len(response["Parameters"]).should.equal(3)

    filters = [{"Key": "Type", "Option": "Equals", "Values": ["StringList"]}]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(1)
    {p["Name"] for p in response["Parameters"]}.should.equal(set(["/baz/name1"]))

    # note: 'Option' is optional (default: 'Equals')
    filters = [{"Key": "Type", "Values": ["StringList"]}]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(1)
    {p["Name"] for p in response["Parameters"]}.should.equal(set(["/baz/name1"]))

    filters = [{"Key": "Type", "Option": "Equals", "Values": ["String"]}]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(1)
    {p["Name"] for p in response["Parameters"]}.should.equal(set(["/baz/name2"]))

    filters = [
        {"Key": "Type", "Option": "Equals", "Values": ["String", "SecureString"]}
    ]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(2)
    {p["Name"] for p in response["Parameters"]}.should.equal(
        set(["/baz/name2", "/baz/pwd"])
    )

    filters = [{"Key": "Type", "Option": "BeginsWith", "Values": ["String"]}]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(2)
    {p["Name"] for p in response["Parameters"]}.should.equal(
        set(["/baz/name1", "/baz/name2"])
    )

    filters = [{"Key": "KeyId", "Option": "Equals", "Values": ["alias/aws/ssm"]}]
    response = client.get_parameters_by_path(Path="/baz", ParameterFilters=filters)
    len(response["Parameters"]).should.equal(1)
    {p["Name"] for p in response["Parameters"]}.should.equal(set(["/baz/pwd"]))


@mock_ssm
def test_put_parameter():
    client = boto3.client("ssm", region_name="us-east-1")

    response = client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="String"
    )

    response["Version"].should.equal(1)

    response = client.get_parameters(Names=["test"], WithDecryption=False)

    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("value")
    response["Parameters"][0]["Type"].should.equal("String")
    response["Parameters"][0]["Version"].should.equal(1)

    try:
        client.put_parameter(
            Name="test", Description="desc 2", Value="value 2", Type="String"
        )
        raise RuntimeError("Should fail")
    except botocore.exceptions.ClientError as err:
        err.operation_name.should.equal("PutParameter")
        err.response["Error"]["Message"].should.equal("Parameter test already exists.")

    response = client.get_parameters(Names=["test"], WithDecryption=False)

    # without overwrite nothing change
    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("value")
    response["Parameters"][0]["Type"].should.equal("String")
    response["Parameters"][0]["Version"].should.equal(1)

    response = client.put_parameter(
        Name="test",
        Description="desc 3",
        Value="value 3",
        Type="String",
        Overwrite=True,
    )

    response["Version"].should.equal(2)

    response = client.get_parameters(Names=["test"], WithDecryption=False)

    # without overwrite nothing change
    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("value 3")
    response["Parameters"][0]["Type"].should.equal("String")
    response["Parameters"][0]["Version"].should.equal(2)


@mock_ssm
def test_put_parameter_china():
    client = boto3.client("ssm", region_name="cn-north-1")

    response = client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="String"
    )

    response["Version"].should.equal(1)


@mock_ssm
def test_get_parameter():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="String"
    )

    response = client.get_parameter(Name="test", WithDecryption=False)

    response["Parameter"]["Name"].should.equal("test")
    response["Parameter"]["Value"].should.equal("value")
    response["Parameter"]["Type"].should.equal("String")


@mock_ssm
def test_get_nonexistant_parameter():
    client = boto3.client("ssm", region_name="us-east-1")

    try:
        client.get_parameter(Name="test_noexist", WithDecryption=False)
        raise RuntimeError("Should of failed")
    except botocore.exceptions.ClientError as err:
        err.operation_name.should.equal("GetParameter")
        err.response["Error"]["Message"].should.equal(
            "Parameter test_noexist not found."
        )


@mock_ssm
def test_describe_parameters():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test",
        Description="A test parameter",
        Value="value",
        Type="String",
        AllowedPattern=r".*",
    )

    response = client.describe_parameters()

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("test")
    parameters[0]["Type"].should.equal("String")
    parameters[0]["AllowedPattern"].should.equal(r".*")


@mock_ssm
def test_describe_parameters_paging():
    client = boto3.client("ssm", region_name="us-east-1")

    for i in range(50):
        client.put_parameter(Name="param-%d" % i, Value="value-%d" % i, Type="String")

    response = client.describe_parameters()
    response["Parameters"].should.have.length_of(10)
    response["NextToken"].should.equal("10")

    response = client.describe_parameters(NextToken=response["NextToken"])
    response["Parameters"].should.have.length_of(10)
    response["NextToken"].should.equal("20")

    response = client.describe_parameters(NextToken=response["NextToken"])
    response["Parameters"].should.have.length_of(10)
    response["NextToken"].should.equal("30")

    response = client.describe_parameters(NextToken=response["NextToken"])
    response["Parameters"].should.have.length_of(10)
    response["NextToken"].should.equal("40")

    response = client.describe_parameters(NextToken=response["NextToken"])
    response["Parameters"].should.have.length_of(10)
    response["NextToken"].should.equal("50")

    response = client.describe_parameters(NextToken=response["NextToken"])
    response["Parameters"].should.have.length_of(0)
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_filter_names():
    client = boto3.client("ssm", region_name="us-east-1")

    for i in range(50):
        p = {"Name": "param-%d" % i, "Value": "value-%d" % i, "Type": "String"}
        if i % 5 == 0:
            p["Type"] = "SecureString"
            p["KeyId"] = "a key"
        client.put_parameter(**p)

    response = client.describe_parameters(
        Filters=[{"Key": "Name", "Values": ["param-22"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("param-22")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_filter_type():
    client = boto3.client("ssm", region_name="us-east-1")

    for i in range(50):
        p = {"Name": "param-%d" % i, "Value": "value-%d" % i, "Type": "String"}
        if i % 5 == 0:
            p["Type"] = "SecureString"
            p["KeyId"] = "a key"
        client.put_parameter(**p)

    response = client.describe_parameters(
        Filters=[{"Key": "Type", "Values": ["SecureString"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(10)
    parameters[0]["Type"].should.equal("SecureString")
    response.should.have.key("NextToken").which.should.equal("10")


@mock_ssm
def test_describe_parameters_filter_keyid():
    client = boto3.client("ssm", region_name="us-east-1")

    for i in range(50):
        p = {"Name": "param-%d" % i, "Value": "value-%d" % i, "Type": "String"}
        if i % 5 == 0:
            p["Type"] = "SecureString"
            p["KeyId"] = "key:%d" % i
        client.put_parameter(**p)

    response = client.describe_parameters(
        Filters=[{"Key": "KeyId", "Values": ["key:10"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("param-10")
    parameters[0]["Type"].should.equal("SecureString")
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_with_parameter_filters_keyid():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="secure-param", Value="secure-value", Type="SecureString")
    client.put_parameter(
        Name="custom-secure-param",
        Value="custom-secure-value",
        Type="SecureString",
        KeyId="alias/custom",
    )
    client.put_parameter(Name="param", Value="value", Type="String")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "KeyId", "Values": ["alias/aws/ssm"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("secure-param")
    parameters[0]["Type"].should.equal("SecureString")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "KeyId", "Values": ["alias/custom"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("custom-secure-param")
    parameters[0]["Type"].should.equal("SecureString")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "KeyId", "Option": "BeginsWith", "Values": ["alias"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(2)
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_with_parameter_filters_name():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="param", Value="value", Type="String")
    client.put_parameter(Name="/param-2", Value="value-2", Type="String")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Values": ["param"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("param")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Values": ["/param"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("param")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Values": ["param-2"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("/param-2")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": ["param"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(2)
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_with_parameter_filters_path():
    client = boto3.client("ssm", region_name="us-east-1")
    client.put_parameter(Name="/foo/name1", Value="value1", Type="String")

    client.put_parameter(Name="/foo/name2", Value="value2", Type="String")

    client.put_parameter(Name="/bar/name3", Value="value3", Type="String")

    client.put_parameter(Name="/bar/name3/name4", Value="value4", Type="String")

    client.put_parameter(Name="foo", Value="bar", Type="String")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Values": ["/fo"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(0)
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Values": ["/"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("foo")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Values": ["/", "/foo"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(3)
    {parameter["Name"] for parameter in response["Parameters"]}.should.equal(
        {"/foo/name1", "/foo/name2", "foo"}
    )
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Values": ["/foo/"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(2)
    {parameter["Name"] for parameter in response["Parameters"]}.should.equal(
        {"/foo/name1", "/foo/name2"}
    )
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[
            {"Key": "Path", "Option": "OneLevel", "Values": ["/bar/name3"]}
        ]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("/bar/name3/name4")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Option": "Recursive", "Values": ["/fo"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(0)
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Option": "Recursive", "Values": ["/"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(5)
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[
            {"Key": "Path", "Option": "Recursive", "Values": ["/foo", "/bar"]}
        ]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(4)
    {parameter["Name"] for parameter in response["Parameters"]}.should.equal(
        {"/foo/name1", "/foo/name2", "/bar/name3", "/bar/name3/name4"}
    )
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[{"Key": "Path", "Option": "Recursive", "Values": ["/foo/"]}]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(2)
    {parameter["Name"] for parameter in response["Parameters"]}.should.equal(
        {"/foo/name1", "/foo/name2"}
    )
    response.should_not.have.key("NextToken")

    response = client.describe_parameters(
        ParameterFilters=[
            {"Key": "Path", "Option": "Recursive", "Values": ["/bar/name3"]}
        ]
    )

    parameters = response["Parameters"]
    parameters.should.have.length_of(1)
    parameters[0]["Name"].should.equal("/bar/name3/name4")
    parameters[0]["Type"].should.equal("String")
    response.should_not.have.key("NextToken")


@mock_ssm
def test_describe_parameters_invalid_parameter_filters():
    client = boto3.client("ssm", region_name="us-east-1")

    client.describe_parameters.when.called_with(
        Filters=[{"Key": "Name", "Values": ["test"]}],
        ParameterFilters=[{"Key": "Name", "Values": ["test"]}],
    ).should.throw(
        ClientError,
        "You can use either Filters or ParameterFilters in a single request.",
    )

    client.describe_parameters.when.called_with(ParameterFilters=[{}]).should.throw(
        ParamValidationError,
        'Parameter validation failed:\nMissing required parameter in ParameterFilters[0]: "Key"',
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "key"}]
    ).should.throw(
        ClientError,
        '1 validation error detected: Value "key" at "parameterFilters.1.member.key" failed to satisfy constraint: '
        "Member must satisfy regular expression pattern: tag:.+|Name|Type|KeyId|Path|Label|Tier",
    )

    long_key = "tag:" + "t" * 129
    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": long_key}]
    ).should.throw(
        ClientError,
        '1 validation error detected: Value "{value}" at "parameterFilters.1.member.key" failed to satisfy constraint: '
        "Member must have length less than or equal to 132".format(value=long_key),
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Option": "over 10 chars"}]
    ).should.throw(
        ClientError,
        '1 validation error detected: Value "over 10 chars" at "parameterFilters.1.member.option" failed to satisfy constraint: '
        "Member must have length less than or equal to 10",
    )

    many_values = ["test"] * 51
    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Values": many_values}]
    ).should.throw(
        ClientError,
        '1 validation error detected: Value "{value}" at "parameterFilters.1.member.values" failed to satisfy constraint: '
        "Member must have length less than or equal to 50".format(value=many_values),
    )

    long_value = ["t" * 1025]
    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Values": long_value}]
    ).should.throw(
        ClientError,
        '1 validation error detected: Value "{value}" at "parameterFilters.1.member.values" failed to satisfy constraint: '
        "[Member must have length less than or equal to 1024, Member must have length greater than or equal to 1]".format(
            value=long_value
        ),
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Option": "over 10 chars"}, {"Key": "key"}]
    ).should.throw(
        ClientError,
        "2 validation errors detected: "
        'Value "over 10 chars" at "parameterFilters.1.member.option" failed to satisfy constraint: '
        "Member must have length less than or equal to 10; "
        'Value "key" at "parameterFilters.2.member.key" failed to satisfy constraint: '
        "Member must satisfy regular expression pattern: tag:.+|Name|Type|KeyId|Path|Label|Tier",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Label"}]
    ).should.throw(
        ClientError,
        "The following filter key is not valid: Label. Valid filter keys include: [Path, Name, Type, KeyId, Tier].",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name"}]
    ).should.throw(
        ClientError,
        "The following filter values are missing : null for filter key Name.",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Values": []}]
    ).should.throw(
        ParamValidationError,
        "Invalid length for parameter ParameterFilters[0].Values, value: 0, valid range: 1-inf",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[
            {"Key": "Name", "Values": ["test"]},
            {"Key": "Name", "Values": ["test test"]},
        ]
    ).should.throw(
        ClientError,
        "The following filter is duplicated in the request: Name. A request can contain only one occurrence of a specific filter.",
    )

    for value in ["/###", "//", "test"]:
        client.describe_parameters.when.called_with(
            ParameterFilters=[{"Key": "Path", "Values": [value]}]
        ).should.throw(
            ClientError,
            'The parameter doesn\'t meet the parameter name requirements. The parameter name must begin with a forward slash "/". '
            'It can\'t be prefixed with "aws" or "ssm" (case-insensitive). '
            "It must use only letters, numbers, or the following symbols: . (period), - (hyphen), _ (underscore). "
            'Special characters are not allowed. All sub-paths, if specified, must use the forward slash symbol "/". '
            "Valid example: /get/parameters2-/by1./path0_.",
        )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Path", "Values": ["/aws", "/ssm"]}]
    ).should.throw(
        ClientError,
        'Filters for common parameters can\'t be prefixed with "aws" or "ssm" (case-insensitive). '
        "When using global parameters, please specify within a global namespace.",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Path", "Option": "Equals", "Values": ["test"]}]
    ).should.throw(
        ClientError,
        "The following filter option is not valid: Equals. Valid options include: [Recursive, OneLevel].",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Tier", "Values": ["test"]}]
    ).should.throw(
        ClientError,
        "The following filter value is not valid: test. Valid values include: [Standard, Advanced, Intelligent-Tiering]",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Type", "Values": ["test"]}]
    ).should.throw(
        ClientError,
        "The following filter value is not valid: test. Valid values include: [String, StringList, SecureString]",
    )

    client.describe_parameters.when.called_with(
        ParameterFilters=[{"Key": "Name", "Option": "option", "Values": ["test"]}]
    ).should.throw(
        ClientError,
        "The following filter option is not valid: option. Valid options include: [BeginsWith, Equals].",
    )


@mock_ssm
def test_describe_parameters_attributes():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="aa", Value="11", Type="String", Description="my description"
    )

    client.put_parameter(Name="bb", Value="22", Type="String")

    response = client.describe_parameters()

    parameters = response["Parameters"]
    parameters.should.have.length_of(2)

    parameters[0]["Description"].should.equal("my description")
    parameters[0]["Version"].should.equal(1)
    parameters[0]["LastModifiedDate"].should.be.a(datetime.date)
    parameters[0]["LastModifiedUser"].should.equal("N/A")

    parameters[1].should_not.have.key("Description")
    parameters[1]["Version"].should.equal(1)


@mock_ssm
def test_get_parameter_invalid():
    client = client = boto3.client("ssm", region_name="us-east-1")
    response = client.get_parameters(Names=["invalid"], WithDecryption=False)

    len(response["Parameters"]).should.equal(0)
    len(response["InvalidParameters"]).should.equal(1)
    response["InvalidParameters"][0].should.equal("invalid")


@mock_ssm
def test_put_parameter_secure_default_kms():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test", Description="A test parameter", Value="value", Type="SecureString"
    )

    response = client.get_parameters(Names=["test"], WithDecryption=False)

    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("kms:alias/aws/ssm:value")
    response["Parameters"][0]["Type"].should.equal("SecureString")

    response = client.get_parameters(Names=["test"], WithDecryption=True)

    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("value")
    response["Parameters"][0]["Type"].should.equal("SecureString")


@mock_ssm
def test_put_parameter_secure_custom_kms():
    client = boto3.client("ssm", region_name="us-east-1")

    client.put_parameter(
        Name="test",
        Description="A test parameter",
        Value="value",
        Type="SecureString",
        KeyId="foo",
    )

    response = client.get_parameters(Names=["test"], WithDecryption=False)

    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("kms:foo:value")
    response["Parameters"][0]["Type"].should.equal("SecureString")

    response = client.get_parameters(Names=["test"], WithDecryption=True)

    len(response["Parameters"]).should.equal(1)
    response["Parameters"][0]["Name"].should.equal("test")
    response["Parameters"][0]["Value"].should.equal("value")
    response["Parameters"][0]["Type"].should.equal("SecureString")


@mock_ssm
def test_add_remove_list_tags_for_resource():
    client = boto3.client("ssm", region_name="us-east-1")

    client.add_tags_to_resource(
        ResourceId="test",
        ResourceType="Parameter",
        Tags=[{"Key": "test-key", "Value": "test-value"}],
    )

    response = client.list_tags_for_resource(
        ResourceId="test", ResourceType="Parameter"
    )
    len(response["TagList"]).should.equal(1)
    response["TagList"][0]["Key"].should.equal("test-key")
    response["TagList"][0]["Value"].should.equal("test-value")

    client.remove_tags_from_resource(
        ResourceId="test", ResourceType="Parameter", TagKeys=["test-key"]
    )

    response = client.list_tags_for_resource(
        ResourceId="test", ResourceType="Parameter"
    )
    len(response["TagList"]).should.equal(0)


@mock_ssm
def test_send_command():
    ssm_document = "AWS-RunShellScript"
    params = {"commands": ["#!/bin/bash\necho 'hello world'"]}

    client = boto3.client("ssm", region_name="us-east-1")
    # note the timeout is determined server side, so this is a simpler check.
    before = datetime.datetime.now()

    response = client.send_command(
        InstanceIds=["i-123456"],
        DocumentName=ssm_document,
        Parameters=params,
        OutputS3Region="us-east-2",
        OutputS3BucketName="the-bucket",
        OutputS3KeyPrefix="pref",
    )
    cmd = response["Command"]

    cmd["CommandId"].should_not.be(None)
    cmd["DocumentName"].should.equal(ssm_document)
    cmd["Parameters"].should.equal(params)

    cmd["OutputS3Region"].should.equal("us-east-2")
    cmd["OutputS3BucketName"].should.equal("the-bucket")
    cmd["OutputS3KeyPrefix"].should.equal("pref")

    cmd["ExpiresAfter"].should.be.greater_than(before)

    # test sending a command without any optional parameters
    response = client.send_command(DocumentName=ssm_document)

    cmd = response["Command"]

    cmd["CommandId"].should_not.be(None)
    cmd["DocumentName"].should.equal(ssm_document)


@mock_ssm
def test_list_commands():
    client = boto3.client("ssm", region_name="us-east-1")

    ssm_document = "AWS-RunShellScript"
    params = {"commands": ["#!/bin/bash\necho 'hello world'"]}

    response = client.send_command(
        InstanceIds=["i-123456"],
        DocumentName=ssm_document,
        Parameters=params,
        OutputS3Region="us-east-2",
        OutputS3BucketName="the-bucket",
        OutputS3KeyPrefix="pref",
    )

    cmd = response["Command"]
    cmd_id = cmd["CommandId"]

    # get the command by id
    response = client.list_commands(CommandId=cmd_id)

    cmds = response["Commands"]
    len(cmds).should.equal(1)
    cmds[0]["CommandId"].should.equal(cmd_id)

    # add another command with the same instance id to test listing by
    # instance id
    client.send_command(InstanceIds=["i-123456"], DocumentName=ssm_document)

    response = client.list_commands(InstanceId="i-123456")

    cmds = response["Commands"]
    len(cmds).should.equal(2)

    for cmd in cmds:
        cmd["InstanceIds"].should.contain("i-123456")

    # test the error case for an invalid command id
    with assert_raises(ClientError):
        response = client.list_commands(CommandId=str(uuid.uuid4()))


@mock_ssm
def test_get_command_invocation():
    client = boto3.client("ssm", region_name="us-east-1")

    ssm_document = "AWS-RunShellScript"
    params = {"commands": ["#!/bin/bash\necho 'hello world'"]}

    response = client.send_command(
        InstanceIds=["i-123456", "i-234567", "i-345678"],
        DocumentName=ssm_document,
        Parameters=params,
        OutputS3Region="us-east-2",
        OutputS3BucketName="the-bucket",
        OutputS3KeyPrefix="pref",
    )

    cmd = response["Command"]
    cmd_id = cmd["CommandId"]

    instance_id = "i-345678"
    invocation_response = client.get_command_invocation(
        CommandId=cmd_id, InstanceId=instance_id, PluginName="aws:runShellScript"
    )

    invocation_response["CommandId"].should.equal(cmd_id)
    invocation_response["InstanceId"].should.equal(instance_id)

    # test the error case for an invalid instance id
    with assert_raises(ClientError):
        invocation_response = client.get_command_invocation(
            CommandId=cmd_id, InstanceId="i-FAKE"
        )

    # test the error case for an invalid plugin name
    with assert_raises(ClientError):
        invocation_response = client.get_command_invocation(
            CommandId=cmd_id, InstanceId=instance_id, PluginName="FAKE"
        )


@mock_ssm
@mock_cloudformation
def test_get_command_invocations_from_stack():
    stack_template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Test Stack",
        "Resources": {
            "EC2Instance1": {
                "Type": "AWS::EC2::Instance",
                "Properties": {
                    "ImageId": "ami-test-image-id",
                    "KeyName": "test",
                    "InstanceType": "t2.micro",
                    "Tags": [
                        {"Key": "Test Description", "Value": "Test tag"},
                        {"Key": "Test Name", "Value": "Name tag for tests"},
                    ],
                },
            }
        },
        "Outputs": {
            "test": {
                "Description": "Test Output",
                "Value": "Test output value",
                "Export": {"Name": "Test value to export"},
            },
            "PublicIP": {"Value": "Test public ip"},
        },
    }

    cloudformation_client = boto3.client("cloudformation", region_name="us-east-1")

    stack_template_str = json.dumps(stack_template)

    response = cloudformation_client.create_stack(
        StackName="test_stack",
        TemplateBody=stack_template_str,
        Capabilities=("CAPABILITY_IAM",),
    )

    client = boto3.client("ssm", region_name="us-east-1")

    ssm_document = "AWS-RunShellScript"
    params = {"commands": ["#!/bin/bash\necho 'hello world'"]}

    response = client.send_command(
        Targets=[
            {"Key": "tag:aws:cloudformation:stack-name", "Values": ("test_stack",)}
        ],
        DocumentName=ssm_document,
        Parameters=params,
        OutputS3Region="us-east-2",
        OutputS3BucketName="the-bucket",
        OutputS3KeyPrefix="pref",
    )

    cmd = response["Command"]
    cmd_id = cmd["CommandId"]
    instance_ids = cmd["InstanceIds"]

    invocation_response = client.get_command_invocation(
        CommandId=cmd_id, InstanceId=instance_ids[0], PluginName="aws:runShellScript"
    )
