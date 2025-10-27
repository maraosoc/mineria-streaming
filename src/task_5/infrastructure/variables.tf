variable "prefix" {
  description = "Prefix for the resources"
  type        = string
  default = "maraosoc"
}

variable "region" {
  type    = string
  default = "us-east-2"
}

variable "profile" {
  type        = string
  description = "Perfil de AWS CLI a usar"
  default     = "maraosoc"
}

variable "owner" {
  type        = string
  description = "Propietario de los recursos"
  default     = "maraosoc"
}

variable "project_name" {
  type    = string
  default = "mineria-benchmark"
}

variable "bucket_name" {
  type = string
  default = "maraosoc-mineria-benchmark"
}

variable "instance_type" {
  type    = string
  default = "m5.2xlarge"
}

variable "source_name" {
  description = "Script initializer path"
  type        = string
}

variable "experiment_name" {
  description = "Experiment name path"
  type        = string
}