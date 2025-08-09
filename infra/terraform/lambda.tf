# CloudWatch Logs group for Lambda
resource "aws_cloudwatch_log_group" "stream_processor" {
  name              = "/aws/lambda/${var.project_name}-stream-processor"
  retention_in_days = 14
}

# Lambda function (zip built locally at build/stream_processor.zip)
resource "aws_lambda_function" "stream_processor" {
  function_name = "${var.project_name}-stream-processor"
  role          = aws_iam_role.stream_processor_role.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  filename      = "${path.module}/../../build/stream_processor.zip"
  timeout       = 15
  memory_size   = 128
  architectures = ["arm64"]

  environment {
    variables = {
      TABLE_NAME = var.table_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.stream_processor]
}

# Event source mapping: DynamoDB Stream -> Lambda
resource "aws_lambda_event_source_mapping" "ddb_stream_to_lambda" {
  event_source_arn  = aws_dynamodb_table.global_catalog.stream_arn
  function_name     = aws_lambda_function.stream_processor.arn
  starting_position = "LATEST"

  batch_size                           = 100
  maximum_batching_window_in_seconds   = 1
  maximum_retry_attempts               = 2
  bisect_batch_on_function_error       = true
  function_response_types              = ["ReportBatchItemFailures"]
}
