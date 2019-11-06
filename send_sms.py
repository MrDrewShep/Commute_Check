import boto3


def send_sms(phone, text_body):
    sns = boto3.client('sns')
    response = sns.publish(
        PhoneNumber=phone,
        Message=text_body,   
        MessageAttributes={
            "AWS.SNS.SMS.SMSType": {
                "DataType": "String",
                "StringValue": "Transactional"
            }
        },
    )

    print("\n", response)
