terraform {
  backend "s3" {
    bucket = "carl-tfstate-403802364021"
    key    = "carl-core/terraform.tfstate"
    region = "us-east-1"
  }
}
