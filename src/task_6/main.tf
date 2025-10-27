terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.44"
    }
  }
}

# =============================
# 🧩 VPC y Subnets
# =============================
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  subnet_id = var.default_subnet_id != "" ? var.default_subnet_id : data.aws_subnets.default.ids[0]
}

# =============================
# 🔐 Security Group
# =============================
resource "aws_security_group" "sg_emr_cluster" {
  name        = "allow_tls_sg_emr_cluster"
  description = "Allow TLS inbound traffic and all outbound traffic"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_egress_rule" "sg_emr_cluster" {
  security_group_id = aws_security_group.sg_emr_cluster.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# =============================
# 🪣 Bucket para logs
# =============================
resource "aws_s3_bucket" "logs" {
  bucket        = "${var.cluster_name}-logs"
  force_destroy = true
}

# =============================
# ⚙️ Roles IAM (EMR y EC2)
# =============================

# EMR service role
resource "aws_iam_role" "emr_service_role" {
  name = "${var.cluster_name}-emr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "elasticmapreduce.amazonaws.com" },
      Action   = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_service_managed" {
  role       = aws_iam_role.emr_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceRole"
}

# EC2 role (para nodos del cluster)
resource "aws_iam_role" "emr_ec2" {
  name = "${var.cluster_name}-emr-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action   = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_ec2_managed" {
  role       = aws_iam_role.emr_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.emr_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "emr_ec2_profile" {
  name = "${var.cluster_name}-ec2-profile"
  role = aws_iam_role.emr_ec2.name
}

# =============================
# 📦 Política para acceso S3 (scripts y datos)
# =============================
resource "aws_iam_policy" "s3_read" {
  name        = "s3-read-policy-s3"
  description = "Allows EMR EC2 instances to read/write from S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::cebaezc1-3026ce8df4f9e9a6",
          "arn:aws:s3:::cebaezc1-3026ce8df4f9e9a6/*"
        ]
      }
    ]
  })
}

# Adjuntar la política al rol EC2 del cluster
resource "aws_iam_role_policy_attachment" "emr_s3_read_attach" {
  role       = aws_iam_role.emr_ec2.name
  policy_arn = aws_iam_policy.s3_read.arn
}

# =============================
# ☁️ EMR Cluster
# =============================
module "cluster" {
  source  = "terraform-aws-modules/emr/aws"
  version = "~> 2.4"

  name          = var.cluster_name
  release_label = var.release_label
  applications  = ["Hadoop", "Spark"]

  create_service_iam_role = false
  service_iam_role_arn    = aws_iam_role.emr_service_role.arn

  create_iam_instance_profile = false
  iam_instance_profile_name   = aws_iam_instance_profile.emr_ec2_profile.name

  ec2_attributes = {
    subnet_id                         = local.subnet_id
    instance_profile                  = aws_iam_instance_profile.emr_ec2_profile.name
    additional_master_security_groups = aws_security_group.sg_emr_cluster.id
    additional_slave_security_groups  = aws_security_group.sg_emr_cluster.id
  }

  master_instance_group = {
    instance_type  = var.master_instance_type
    instance_count = 1
  }

  core_instance_group = {
    instance_type  = var.core_instance_type
    instance_count = 2
  }

  is_private_cluster = false
  vpc_id             = data.aws_vpc.default.id

  log_uri = "s3://${aws_s3_bucket.logs.bucket}/logs/"
}

# =============================
# 🔍 Master Node (para conexión SSM)
# =============================
data "aws_instances" "master_group" {
  instance_tags = {
    "aws:elasticmapreduce:job-flow-id"         = module.cluster.cluster_id
    "aws:elasticmapreduce:instance-group-role" = "MASTER"
  }
  filter {
    name   = "instance-state-name"
    values = ["pending", "running"]
  }
  depends_on = [module.cluster]
}

data "aws_instances" "master_fleet" {
  instance_tags = {
    "aws:elasticmapreduce:job-flow-id"        = module.cluster.cluster_id
    "aws:elasticmapreduce:instance-fleet-type" = "MASTER"
  }
  filter {
    name   = "instance-state-name"
    values = ["pending", "running"]
  }
  depends_on = [module.cluster]
}

locals {
  master_ids = length(data.aws_instances.master_group.ids) > 0 ? data.aws_instances.master_group.ids : data.aws_instances.master_fleet.ids
}
