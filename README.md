# Hard Hat Networking: networking lessons

Labs, scripts and notes for the Hard Hat Networking video series. Networking taught from the ground up, with a small automation tool in every lesson.

## Lessons

| Lesson | Topic | Lab | Automation nugget | Video |
| --- | --- | --- | --- | --- |
| [L2-01](lessons/L2-01-mac-learning/) | How a switch learns, forwards, floods and filters | 2 switches, 4 hosts | `mac_locator.py`: find the switch port any MAC lives on | Coming soon |
| [L2-02](lessons/L2-02-vlans/) | VLANs and trunking | 2 switches, 4 hosts in 2 VLANs, a trunk to build | `vlan_audit.py`: find VLAN and trunk mismatches with TextFSM | Coming soon |

## What you need

- [Cisco Modeling Labs (CML)](https://developer.cisco.com/modeling-labs/) 2.x with the `iosvl2`, `iosv` and `ubuntu` images
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.5 or newer

## Build a lesson's lab

Each lesson has its own Terraform environment. Set your CML login as environment variables (never put them in a file):

```bash
export TF_VAR_cml_address=https://<your CML address>
export TF_VAR_cml_username=<your CML user>
read -s -p "CML password: " TF_VAR_cml_password; echo; export TF_VAR_cml_password
```

Then build and remove the lab:

```bash
cd terraform/environments/l2-01-mac-learning
terraform init
terraform apply      # build and start the lab
terraform destroy    # stop and delete it
```

After `apply`, Terraform prints a `test_plan` with the checks for that lesson.

## Repo layout

```
lessons/<lesson>/              notes and scripts for each lesson
terraform/environments/<lab>/  one folder per lab: run terraform here
terraform/modules/<lab>/       the lab topology and its build logic
```

Lab passwords in these files are lab-only defaults. Never reuse them on a real network.
