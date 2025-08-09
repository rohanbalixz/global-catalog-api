data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "stream_processor_role" {
  name               = "${var.project_name}-stream-processor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Minimal permissions: read from DynamoDB Streams, read table metadata, write CloudWatch Logs, and write back to the table for projections/materializations
data "aws_iam_policy_document" "stream_processor_policy" {
  statement {
    sid     = "DynamoDBStreamsRead"
    actions = [
      "dynamodb:DescribeStream",
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:ListStreams"
    ]
    resources = ["*"] # Streams ARN is distinct per shard; narrow later if needed
  }

  statement {
    sid     = "DynamoDBTableRW"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem"
    ]
    resources = [aws_dynamodb_table.global_catalog.arn]
  }

  statement {
    sid     = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "stream_processor_policy" {
  name   = "${var.project_name}-stream-processor-policy"
  policy = data.aws_iam_policy_document.stream_processor_policy.json
}

resource "aws_iam_role_policy_attachment" "attach_stream_processor" {
  role       = aws_iam_role.stream_processor_role.name
  policy_arn = aws_iam_policy.stream_processor_policy.arn
}
