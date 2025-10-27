resource "aws_instance" "this" {
  
  ami                         = data.aws_ami.this.id
  instance_type               = var.instance_type
  vpc_security_group_ids      = [aws_security_group.server.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.this.name
  user_data_replace_on_change = true

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  user_data = templatefile("../user_data.sh", {
    experiment_name = var.experiment_name
    source_name     = var.source_name
    bucket_name     = var.bucket_name
    data_size       = var.data_size
  })

  tags = {
    Name = "${var.prefix}-server"
  }
}

data "aws_vpc" "default" {
  default = true
}



data "aws_ami" "this" {
  most_recent = true

  owners = ["099720109477"] # Canonical

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}


resource "aws_security_group" "server" {
  name        = "${var.prefix}-server"
  vpc_id      = data.aws_vpc.default.id
  description = "Security group for the web server"
}


    
resource "aws_vpc_security_group_egress_rule" "to_all" {
  security_group_id = aws_security_group.server.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1" # -1 means all protocols
  description       = "Allow all outbound traffic"
}


resource "aws_iam_instance_profile" "this" {
  name = "${var.prefix}-ec2-profile"
  role = aws_iam_role.this.name
}


resource "aws_iam_role" "this" {
  name = "${var.prefix}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_read_attach" {
  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.s3_read.arn
}


resource "aws_iam_policy" "s3_read" {
  name        = "s3-read-policy-${var.prefix}"
  description = "Allows EC2 instances to read from specified S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
        ]
        Resource = [
          # specify that you need to read from the deployment bucket
          ## homework:replace:on
          # "arn:aws:s3:::${}",
          "arn:aws:s3:::${var.bucket_name}",
          ## homework:replace:off

          # specify that you need to read all objects in the bucket
          ## homework:replace:on
          # "arn:aws:s3:::${}/*"
          "arn:aws:s3:::${var.bucket_name}/*"
          ## homework:replace:off
        ]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core_attachment" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

