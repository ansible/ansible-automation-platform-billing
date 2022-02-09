Ansible Automation Platform Azure Billing
=========================================

Captures automation usage for reporting to hyperscaler metering system.

# Getting Started

To get started developing against ansible-automation-platform-azure-billing first clone a local copy of the git repository.
```
git clone https://github.com/ansible/ansible-automation-platform-azure-billing.git
```

Change directories to the local repository.
```
cd ansible-automation-platform-azure-billing
```

Create a virtual environement for development and activate the venv.
```
python -m venv aap-billing
source aap-billing/bin/activate
```

Install the required dependencies.
```
pip install .
```

Install devlopment dependencies.
```
pip install tox
pip install -r test-requirements.txt
```

# Linting

Run the linting via tox.
```
tox -e linters
```

# Testing

Run the unit tests via tox.
```
tox -e unittest
```
