variable "cluster_name" {
     type = string
     default = "data-mining"
}

variable "release_label" {
     type = string
     default = "emr-7.1.0"
}

variable "master_instance_type" {
     type = string
     default = "m5.xlarge"
}

variable "core_instance_type" {
     type = string
     default = "m5.xlarge"
}

variable "default_subnet_id" {
    type = string
    default = "subnet-05be590ba0b3a0d13" 
}